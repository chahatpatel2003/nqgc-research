"""Daily table builder: one row per CME trade date with `meta`, `pre_*` (available at 09:29:59.999 ET), `post_*`
(09:30 → close; usable only as NEXT-day context) and `y_*` labels (from the 09:30–12:00 window).

Labels (design §3). R20 = median 09:30–12:00 range of the previous 20 RTH sessions (known at 09:29 on D).
  T1  net sign                         sign(P1200 − Open)
  T2a/T2b thresholded net              ±1 beyond ±k·R20, k = 0.10 / 0.25, else 0 (FLAT)
  T3  dominant excursion               sign(MFE − MAE), FLAT if |MFE − MAE| < 0.05·R20
  T4a/T4b first-hit                    which of Open ± k·R20 (k = 0.25 / 0.50) is hit first; neither → FLAT
  T5  path trend                       sign of OLS slope of 1-min closes; FLAT if R² < 0.10
  T6  time-in-direction                +1 if ≥ 60% of 1-min closes above Open, −1 if ≤ 40%, else FLAT
  T7  clean directional day            T1 if T1 == T3 == T5 ≠ 0, else FLAT
"""
from __future__ import annotations
import datetime as dt
import math

import numpy as np
import polars as pl

from .session import SEQ_MINUTES, et_ns, load_day, post_stats, pre_stats, pre_keys, post_keys
from .splits import roll_adj, session_days

TARGETS = ["y_T1", "y_T2a", "y_T2b", "y_T3", "y_T4a", "y_T4b", "y_T5", "y_T6", "y_T7"]
MIN_AM_PRINTS = 1000
MIN_ON_COVERAGE = 0.90
R20_WINDOW = 20


def _sgn(v) -> int | None:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return 0 if v == 0 else (1 if v > 0 else -1)


def make_targets(p: dict, R20: float) -> dict:
    ret = p["post_am_ret_pts"]
    y = {k: None for k in TARGETS}
    if ret is None or (isinstance(ret, float) and math.isnan(ret)):
        return y
    y["y_T1"] = _sgn(ret)
    has_r = R20 == R20 and R20 > 0
    for name, k in (("y_T2a", 0.10), ("y_T2b", 0.25)):
        y[name] = (1 if ret >= k * R20 else -1 if ret <= -k * R20 else 0) if has_r else None
    dd = p["post_mfe"] - p["post_mae"]
    y["y_T3"] = (0 if abs(dd) < 0.05 * R20 else _sgn(dd)) if has_r else None
    y["y_T4a"] = int(p["post_fh25"]) if has_r and p["post_fh25"] == p["post_fh25"] else None
    y["y_T4b"] = int(p["post_fh50"]) if has_r and p["post_fh50"] == p["post_fh50"] else None
    r2, sl = p["post_am_r2"], p["post_am_slope"]
    y["y_T5"] = None if r2 != r2 else (0 if r2 < 0.10 else _sgn(sl))
    sh = p["post_am_share_above_open"]
    y["y_T6"] = None if sh != sh else (1 if sh >= 0.60 else -1 if sh <= 0.40 else 0)
    t1, t3, t5 = y["y_T1"], y["y_T3"], y["y_T5"]
    y["y_T7"] = None if None in (t1, t3, t5) else (t1 if (t1 == t3 == t5 and t1 != 0) else 0)
    return y


def build_daily(phase: str, spec_id: str | None = None, purpose: str = "", unlock: str | None = None, verbose: bool = True):
    """Returns (daily DataFrame, seq array [n_days, SEQ_MINUTES-1], list of dates for seq rows)."""
    days = session_days(phase, spec_id, purpose, unlock)
    adj = roll_adj()
    rows, seqs, seq_dates = [], [], []
    am_ranges: list[float] = []      # 09:30–12:00 ranges of RTH sessions, for R20
    last_rth_close_cont = np.nan
    prev_holiday = False
    t0 = dt.datetime.now()
    for i, x in enumerate(days):
        d = x["date"]
        dp = load_day(d)
        a = adj.get(d, np.nan)
        R20 = float(np.median(am_ranges[-R20_WINDOW:])) if len(am_ranges) >= R20_WINDOW else np.nan
        meta = dict(date=d, year=d.year, front=x["front"], roll_day=x["roll_day"], adj=a, early_close=x["early_close"],
                    close_ct=f"{x['close_ct'][0]:02d}:{x['close_ct'][1]:02d}", half_day=x["half_day"], holiday_session=x["holiday_session"],
                    partial=x["partial"], hole=x["hole"], bootstrap=x["bootstrap"], prev_holiday_session=prev_holiday, R20=R20, has_prints=dp is not None)
        is_rth = (not x["holiday_session"]) and (not x["partial"]) and (not x["hole"])
        if dp is None:
            pre = {k: np.nan for k in pre_keys()}
            post = {k: np.nan for k in post_keys()}
            seq = np.zeros(SEQ_MINUTES - 1)
        else:
            ref = last_rth_close_cont + a if last_rth_close_cont == last_rth_close_cont and a == a else np.nan
            pre, seq = pre_stats(dp, d, R20, ref)
            h, m = x["close_ct"]
            close_ns = et_ns(d, h + 1, m)  # CT → ET
            post = post_stats(dp, d, close_ns, R20)
            assert pre["pre_max_ts"] < pre["pre_cutoff_ns"], d
        y = make_targets(post, R20) if dp is not None else {k: None for k in TARGETS}
        n_am = post["post_n_am"]
        is_full_rth = is_rth and not x["early_close"]
        elig_reason = ("no_prints" if dp is None else "bootstrap" if x["bootstrap"] else "partial_or_hole" if (x["partial"] or x["hole"])
                       else "holiday_session" if x["holiday_session"] else "early_close" if x["early_close"]
                       else "thin_am" if not (n_am == n_am and n_am >= MIN_AM_PRINTS)
                       else "overnight_gap" if not (pre["pre_on_coverage"] == pre["pre_on_coverage"] and pre["pre_on_coverage"] >= MIN_ON_COVERAGE)
                       else "no_R20" if R20 != R20 else "ok")
        meta["is_rth"] = is_rth and dp is not None and n_am == n_am and n_am >= 100
        meta["is_full_rth"] = is_full_rth and meta["is_rth"]
        meta["eligible"] = elig_reason == "ok"
        meta["elig_reason"] = elig_reason
        rows.append(meta | pre | post | y)
        seqs.append(seq)
        seq_dates.append(d)
        if meta["is_rth"] and post["post_am_rng"] == post["post_am_rng"]:
            am_ranges.append(float(post["post_am_rng"]))
            last_rth_close_cont = post["post_close"] - a
        prev_holiday = x["holiday_session"]
        if verbose and (i % 50 == 0 or i == len(days) - 1):
            print(f"  {d} {i + 1}/{len(days)} {(dt.datetime.now() - t0).total_seconds():.0f}s", flush=True)
    df = pl.DataFrame(rows).with_columns([pl.col(c).cast(pl.Int8) for c in TARGETS])
    return df, np.vstack(seqs), seq_dates
