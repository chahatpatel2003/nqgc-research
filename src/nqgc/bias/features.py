"""Feature matrix v1 from the daily table. Every feature for day D uses only: `pre_*` of D (prints < 09:30 ET on D),
`post_*` of RTH sessions strictly before D (via shift), and deterministic calendar facts. Rolling statistics are
computed on the RTH-session frame with an explicit shift(1), so the window ends at the previous RTH session.

Cross-day price differences use the causal continuous price `px − adj(session)` (adj = cumulative roll spread measured
on the basis session before each roll; data_cache/nq_roll_adjust.parquet, Phase 3).
"""
from __future__ import annotations
import datetime as dt

import numpy as np
import polars as pl

from .session import PRE_WINDOWS
from .splits import all_trade_dates

MONTH_CODES = {"H": 3, "M": 6, "U": 9, "Z": 12}


def _third_friday(y: int, m: int) -> dt.date:
    d = dt.date(y, m, 15)
    return d + dt.timedelta(days=(4 - d.weekday()) % 7)


def _expiry_from_symbol(sym: str, d: dt.date) -> dt.date:
    m = MONTH_CODES[sym[2]]
    y = int(sym[3:])
    y = (d.year // 10) * 10 + y
    if y < d.year - 1:
        y += 10
    return _third_friday(y, m)


def _streak(signs: np.ndarray) -> np.ndarray:
    out = np.zeros(signs.size)
    run = 0.0
    for i, s in enumerate(signs):
        if np.isnan(s) or s == 0:
            run = 0.0
        elif run * s > 0:
            run += s
        else:
            run = s
        out[i] = run
    return out


def _calendar_flags(dates: list[dt.date], fronts: list[str]) -> dict[str, list]:
    cal = all_trade_dates()
    pos = {d: i for i, d in enumerate(cal)}
    first, last, ttx, after_hol = [], [], [], []
    for d, f in zip(dates, fronts):
        i = pos[d]
        prev_cal = cal[i - 1] if i > 0 else None
        next_cal = cal[i + 1] if i + 1 < len(cal) else None
        first.append(1.0 if prev_cal is None or prev_cal.month != d.month else 0.0)
        last.append(1.0 if next_cal is not None and next_cal.month != d.month else 0.0)
        if f is None:
            ttx.append(float("nan"))
        else:
            exp = _expiry_from_symbol(f, d)
            ttx.append(float(sum(1 for c in cal[i:i + 80] if c < exp)))
        gap = (d - prev_cal).days if prev_cal is not None else 1
        expected = 3 if d.weekday() == 0 else 1
        after_hol.append(1.0 if gap > expected else 0.0)
    return {"f_first_td_month": first, "f_last_td_month": last, "f_days_to_expiry": ttx, "f_after_holiday_gap": after_hol}


def build_features(daily: pl.DataFrame) -> pl.DataFrame:
    """Feature rows for every RTH session in `daily` (eligibility flag carried through)."""
    r = daily.filter(pl.col("is_rth")).sort("date")
    R = pl.col("R20")
    p0929 = pl.col("pre_p0929")
    r = r.with_columns(
        close_cont=pl.col("post_close") - pl.col("adj"), open_cont=pl.col("post_open") - pl.col("adj"),
        high_cont=pl.col("post_high") - pl.col("adj"), low_cont=pl.col("post_low") - pl.col("adj"),
        am_high_cont=pl.col("post_am_high") - pl.col("adj"), am_low_cont=pl.col("post_am_low") - pl.col("adj"),
        settle_cont=pl.col("post_settle") - pl.col("adj"), p0929_cont=p0929 - pl.col("adj"),
        clv=(pl.col("post_close") - pl.col("post_low")) / (pl.col("post_high") - pl.col("post_low")),
        rth_sign=pl.col("post_rth_ret_pts").sign(),
        am_ret_pct=pl.col("post_am_ret_pts") / pl.col("post_open"),
    )
    # previous RTH session (shift 1 on the RTH frame)
    post_cols = [c for c in r.columns if c.startswith("post_")] + ["close_cont", "open_cont", "high_cont", "low_cont", "am_high_cont",
                                                                   "am_low_cont", "settle_cont", "clv", "rth_sign", "am_ret_pct", "adj", "half_day", "date"]
    y_cols = [c for c in r.columns if c.startswith("y_")]
    r = r.with_columns([pl.col(c).shift(1).alias("prev_" + c) for c in post_cols + y_cols])
    r = r.with_columns(prev2_close_cont=pl.col("close_cont").shift(2))
    # gap filled during the AM window (row's own AM range vs previous close) -> only used shifted
    r = r.with_columns(gap_filled=((pl.col("prev_close_cont") >= pl.col("am_low_cont")) & (pl.col("prev_close_cont") <= pl.col("am_high_cont"))).cast(pl.Float64))
    # rolling medians of pre-window activity over the previous 20 RTH sessions
    med = []
    for w in PRE_WINDOWS:
        for k in ("vol", "rv", "n"):
            med.append(pl.col(f"pre_{w}_{k}").shift(1).rolling_median(20, min_samples=10).alias(f"med20_{w}_{k}"))
    med += [pl.col("pre_on_mean_size").shift(1).rolling_median(20, min_samples=10).alias("med20_on_mean_size"),
            pl.col("pre_on_rng").shift(1).rolling_median(20, min_samples=10).alias("med20_on_rng"),
            pl.col("post_pc_vol").shift(1).rolling_median(20, min_samples=10).alias("med20_pc_vol"),
            pl.col("post_rth_vol").shift(1).rolling_median(20, min_samples=10).alias("med20_rth_vol")]
    r = r.with_columns(med)
    # daily returns of the continuous close; sigma20 known at D uses returns of sessions <= D-1
    r = r.with_columns(lr=(pl.col("close_cont") - pl.col("close_cont").shift(1)) / pl.col("post_close").shift(1))
    r = r.with_columns(sigma20=pl.col("lr").shift(1).rolling_std(20, min_samples=10), sigma5=pl.col("lr").shift(1).rolling_std(5, min_samples=5))
    r = r.with_columns(sigma20_prev5=pl.col("sigma20").shift(5),
                       hi20=pl.col("high_cont").shift(1).rolling_max(20, min_samples=10), lo20=pl.col("low_cont").shift(1).rolling_min(20, min_samples=10),
                       hi60=pl.col("high_cont").shift(1).rolling_max(60, min_samples=20), lo60=pl.col("low_cont").shift(1).rolling_min(60, min_samples=20),
                       hi20_before_prev=pl.col("high_cont").shift(2).rolling_max(20, min_samples=10),
                       lo20_before_prev=pl.col("low_cont").shift(2).rolling_min(20, min_samples=10))
    feats: list[pl.Expr] = []
    # ---- pre-open windows
    for w in PRE_WINDOWS:
        c = lambda k, w=w: pl.col(f"pre_{w}_{k}")
        feats += [(c("ret_pts") / R).alias(f"f_{w}_ret_r"), (c("rng") / R).alias(f"f_{w}_rng_r"),
                  (c("rv") / pl.col(f"med20_{w}_rv")).alias(f"f_{w}_rv_ratio"), (c("vol") / pl.col(f"med20_{w}_vol")).alias(f"f_{w}_vol_ratio"),
                  (c("n") / pl.col(f"med20_{w}_n")).alias(f"f_{w}_n_ratio"), c("imb").alias(f"f_{w}_imb"), c("big_imb").alias(f"f_{w}_big_imb"),
                  ((p0929 - c("vwap")) / R).alias(f"f_{w}_vwap_dist_r"), c("nrev").alias(f"f_{w}_nrev")]
    feats += [(pl.col("pre_on_ret_pts") / pl.col("pre_session_start_px")).alias("f_on_ret_pct")]
    # ---- previous session's post-close window (16:00-17:00 ET)
    feats += [(pl.col("prev_post_pc_ret_pts") / R).alias("f_pc_ret_r"), (pl.col("prev_post_pc_vol") / pl.col("med20_pc_vol")).alias("f_pc_vol_ratio"),
              pl.col("prev_post_pc_imb").alias("f_pc_imb")]
    # ---- overnight extras
    on_rng = pl.col("pre_on_high") - pl.col("pre_on_low")
    shock = pl.col("pre_p0835") - pl.col("pre_p0830")
    feats += [
        ((p0929 - pl.col("pre_on_low")) / on_rng).alias("f_on_pos_in_range"),
        pl.col("pre_on_min_since_high").alias("f_on_min_since_high"), pl.col("pre_on_min_since_low").alias("f_on_min_since_low"),
        ((pl.col("pre_on_high") - pl.col("adj") - pl.col("prev_high_cont")) / R).alias("f_on_high_vs_prev_high_r"),
        ((pl.col("pre_on_low") - pl.col("adj") - pl.col("prev_low_cont")) / R).alias("f_on_low_vs_prev_low_r"),
        ((p0929 - pl.col("pre_on_low")) / R).alias("f_on_drawup_r"), ((pl.col("pre_on_high") - p0929) / R).alias("f_on_drawdown_r"),
        pl.col("pre_on_run5").alias("f_on_run5"), (pl.col("pre_on_max5m") / R).alias("f_on_max5m_r"),
        (shock / R).alias("f_shock_0830_r"),
        pl.when(shock.abs() > 0).then(((pl.col("pre_p0835") - p0929) / shock).clip(-3, 3)).otherwise(None).alias("f_shock_retrace"),
        ((pl.col("p0929_cont") - pl.col("prev_close_cont")) / R).alias("f_gap_close_r"),
        ((pl.col("p0929_cont") - pl.col("prev_settle_cont")) / R).alias("f_gap_settle_r"),
        ((pl.col("p0929_cont") - pl.col("prev_close_cont")) / pl.col("prev_post_close")).alias("f_gap_pct"),
        (pl.col("pre_on_rng") / pl.col("prev_post_rng")).alias("f_on_rng_vs_prev_rng"),
        (pl.col("pre_on_ret_pts").sign() * pl.col("prev_post_rth_ret_pts").sign()).alias("f_on_x_prev_sign"),
        pl.col("pre_on_coverage").alias("f_on_coverage"),
        pl.col("pre_on_share_above_ref").alias("f_on_share_above_prev_close"), pl.col("pre_on_share_above_start").alias("f_on_share_above_start"),
        (pl.col("pre_eu_ret_pts").sign() * pl.col("pre_asia_ret_pts").sign()).alias("f_eu_x_asia_sign"),
        (pl.col("pre_last30_ret_pts").sign() * pl.col("pre_on_ret_pts").sign()).alias("f_last30_x_on_sign"),
        ((pl.col("pre_data_vol") + pl.col("pre_last30_vol")) / pl.col("pre_on_vol")).alias("f_on_vol_last_hour_share"),
        (pl.col("pre_on_mean_size") / pl.col("med20_on_mean_size")).alias("f_on_mean_size_ratio"),
        (pl.col("med20_on_rng") / R).alias("f_on_rng_med20_r"),
        (R / p0929).alias("f_R20_pct"),
    ]
    # ---- previous RTH session
    pr = lambda k: pl.col("prev_" + k)
    feats += [
        (pr("post_rth_ret_pts") / pr("post_open")).alias("f_prev_rth_ret_pct"), (pr("post_rth_ret_pts") / R).alias("f_prev_rth_ret_r"),
        pr("clv").alias("f_prev_clv"), (pr("post_rng") / R).alias("f_prev_rng_r"), (pr("post_am_ret_pts") / R).alias("f_prev_am_ret_r"),
        (pr("post_pm_ret_pts") / R).alias("f_prev_pm_ret_r"), (pr("post_last_hour_ret_pts") / R).alias("f_prev_last_hour_ret_r"),
        (pr("post_rth_ret_pts").abs() / pr("post_rng")).alias("f_prev_trend_day"),
        ((pr("open_cont") - pl.col("prev2_close_cont")) / R).alias("f_prev_gap_r"),
        (pr("post_rth_vol") / pl.col("med20_rth_vol")).alias("f_prev_rth_vol_ratio"), pr("post_last_hour_imb").alias("f_prev_last_hour_imb"),
        ((pr("post_settle") - pr("post_close")) / R).alias("f_prev_settle_minus_close_r"), pr("post_rth_up_minute_share").alias("f_prev_up_minute_share"),
        ((pr("post_high") - pr("post_close")) / R).alias("f_prev_dd_from_high_r"),
        (pr("high_cont") >= pl.col("hi20_before_prev")).cast(pl.Float64).alias("f_prev_new20_high"),
        (pr("low_cont") <= pl.col("lo20_before_prev")).cast(pl.Float64).alias("f_prev_new20_low"),
        pr("half_day").cast(pl.Float64).alias("f_prev_half_day"),
        (pr("post_am_ret_pts").sign() * pr("post_pm_ret_pts").sign()).alias("f_prev_am_x_pm_sign"),
    ] + [pr(y).cast(pl.Float64).alias("f_prev_" + y[2:]) for y in y_cols]
    # ---- multi-day context
    cc = pl.col("close_cont")
    pc = pl.col("post_close")
    s20 = pl.col("sigma20")
    feats += [
        ((cc.shift(1) - cc.shift(3)) / pc.shift(1) / s20).alias("f_ret_2d_s"), ((cc.shift(1) - cc.shift(6)) / pc.shift(1) / s20).alias("f_ret_5d_s"),
        ((cc.shift(1) - cc.shift(11)) / pc.shift(1) / s20).alias("f_ret_10d_s"), ((cc.shift(1) - cc.shift(21)) / pc.shift(1) / s20).alias("f_ret_20d_s"),
        ((pl.col("p0929_cont") - pl.col("lo20")) / (pl.col("hi20") - pl.col("lo20"))).alias("f_pos_20d"),
        ((pl.col("p0929_cont") - pl.col("lo60")) / (pl.col("hi60") - pl.col("lo60"))).alias("f_pos_60d"),
        s20.alias("f_rv20"), (s20 / pl.col("sigma20_prev5")).alias("f_rv20_chg"), (pl.col("sigma5") / s20).alias("f_rv5_over_rv20"),
        pl.col("clv").shift(1).rolling_mean(5, min_samples=3).alias("f_mean_clv_5"),
        (pl.col("rth_sign") > 0).cast(pl.Float64).shift(1).rolling_sum(5, min_samples=5).alias("f_n_up_5"),
        (pl.col("rth_sign") > 0).cast(pl.Float64).shift(1).rolling_sum(10, min_samples=10).alias("f_n_up_10"),
        pl.col("gap_filled").shift(1).rolling_mean(10, min_samples=5).alias("f_gap_fill_share_10"),
        pl.col("am_ret_pct").shift(1).rolling_mean(20, min_samples=10).alias("f_am_drift_20"),
        (pl.col("y_T1") > 0).cast(pl.Float64).shift(1).rolling_mean(20, min_samples=10).alias("f_am_upshare_20"),
        pl.rolling_corr(pl.col("am_ret_pct").shift(1), pl.col("am_ret_pct").shift(2), window_size=20, min_samples=15).alias("f_am_autocorr_20"),
        pl.col("date").dt.weekday().cast(pl.Float64).alias("f_dow"), pl.col("date").dt.month().cast(pl.Float64).alias("f_month"),
        ((pl.col("date").dt.weekday() == 5) & (pl.col("date").dt.day() >= 15) & (pl.col("date").dt.day() <= 21)).cast(pl.Float64).alias("f_third_friday"),
        pl.col("roll_day").cast(pl.Float64).alias("f_roll_day"), pl.col("prev_holiday_session").cast(pl.Float64).alias("f_prev_holiday_session"),
    ]
    r = r.with_columns(feats)
    r = r.with_columns(pl.Series("f_streak", _streak(r["rth_sign"].shift(1).fill_null(np.nan).to_numpy().astype(float))))
    cal = _calendar_flags(r["date"].to_list(), r["front"].to_list())
    r = r.with_columns([pl.Series(k, v) for k, v in cal.items()])
    fcols = [c for c in r.columns if c.startswith("f_")]
    return r.select(["date", "year", "eligible", "elig_reason", "R20"] + fcols)


def feature_names(df: pl.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("f_")]


def assert_no_targets(df: pl.DataFrame) -> None:
    bad = [c for c in df.columns if c.startswith("y_") or c.startswith("post_")]
    if bad:
        raise ValueError(f"feature frame contains target / post-open columns: {bad}")
