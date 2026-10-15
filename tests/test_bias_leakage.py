"""Phase-5 leakage / alignment tests for the daily table and feature matrix (development build).
Run after scripts/phase5/run_E0.py (needs runs/phase5/E0/daily_development.parquet)."""
import datetime as dt, sys
from pathlib import Path
sys.path.insert(0, "src")
import numpy as np, polars as pl, pytest
from nqgc.bias.daily import TARGETS, make_targets
from nqgc.bias.features import build_features, feature_names, assert_no_targets
from nqgc.bias.session import load_day, pre_stats, post_stats, et_ns, pre_keys, NS_MIN
from nqgc.bias.splits import OUT, roll_adj
from nqgc.paths import RUNS_DIR

E0 = OUT / "E0"
pytestmark = pytest.mark.skipif(not (E0 / "daily_development.parquet").exists(), reason="E0 not built")
RNG = np.random.default_rng(20260902)


@pytest.fixture(scope="module")
def daily():
    return pl.read_parquet(E0 / "daily_development.parquet").sort("date")


@pytest.fixture(scope="module")
def feats(daily):
    return build_features(daily)


def _eq(a, b):
    a = np.asarray(a, dtype=float); b = np.asarray(b, dtype=float)
    return np.array_equal(np.isnan(a), np.isnan(b)) and np.array_equal(a[~np.isnan(a)], b[~np.isnan(b)])


def _sample_days(daily, n=40):
    d = daily.filter(pl.col("eligible"))["date"].to_list()
    return [d[i] for i in sorted(RNG.choice(len(d), size=n, replace=False))]


# 1. every stored pre-open row was computed from prints strictly before the cutoff
def test_max_ts_audit(daily):
    r = daily.filter(pl.col("has_prints"))
    assert (r["pre_max_ts"] < r["pre_cutoff_ns"]).all()
    assert (r["pre_cutoff_ns"] == pl.Series([float(et_ns(d, 9, 30)) for d in r["date"].to_list()])).all()


# 2. print-level truncation: features from a physically truncated day equal the stored row, bit for bit
def test_print_truncation(daily):
    days = _sample_days(daily, 40)
    for d in days:
        row = daily.filter(pl.col("date") == d).to_dicts()[0]
        dp = load_day(d)
        cutoff = et_ns(d, 9, 30)
        trunc = dp.before(cutoff)
        assert trunc.ts.size < dp.ts.size and trunc.ts[-1] < cutoff <= dp.ts[trunc.ts.size]
        ref = row["pre_on_share_above_ref"]
        # recover the reference price used (prev RTH close + adj) from the daily table
        prev = daily.filter((pl.col("date") < d) & pl.col("is_rth")).sort("date").tail(1).to_dicts()[0]
        ref_px = prev["post_close"] - prev["adj"] + row["adj"]
        a, seq_a = pre_stats(trunc, d, row["R20"], ref_px)
        b, seq_b = pre_stats(dp, d, row["R20"], ref_px)
        for k in pre_keys():
            assert _eq([a[k]], [b[k]]), (d, k)
            assert _eq([a[k]], [row[k]]), (d, k, a[k], row[k])
        assert np.array_equal(seq_a, seq_b)


# 3. daily-level truncation: the feature row for D is unchanged when every row after D is removed and D's own
#    post-open columns and labels are blanked
def test_daily_truncation(daily, feats):
    full = feats
    days = _sample_days(daily, 40)
    fn = feature_names(full)
    for d in days:
        i = daily["date"].to_list().index(d)
        cut = daily.head(i + 1)
        post_cols = [c for c in cut.columns if c.startswith("post_")]
        cut = cut.with_columns([pl.when(pl.col("date") == d).then(None).otherwise(pl.col(c)).alias(c) for c in post_cols + TARGETS])
        cut = cut.with_columns([pl.col(c).cast(pl.Float64) for c in post_cols])
        g = build_features(cut).filter(pl.col("date") == d)
        h = full.filter(pl.col("date") == d)
        assert g.height == 1 and h.height == 1
        for c in fn:
            assert _eq(g[c].to_numpy(), h[c].to_numpy()), (d, c, g[c][0], h[c][0])


# 4. schema separation
def test_schema_separation(feats):
    assert_no_targets(feats)
    with pytest.raises(ValueError):
        assert_no_targets(feats.with_columns(pl.lit(1).alias("y_T1")))
    assert not any(c.startswith("y_") or c.startswith("post_") for c in feats.columns)


# 5. alignment: previous-session features equal RTH statistics recomputed independently from D-1's own prints,
#    and D's prev_T1 equals D-1's label
def test_alignment(daily, feats):
    days = _sample_days(daily, 20)
    for d in days:
        row = feats.filter(pl.col("date") == d).to_dicts()[0]
        prev = daily.filter((pl.col("date") < d) & pl.col("is_rth")).sort("date").tail(1).to_dicts()[0]
        dp = load_day(prev["date"])
        o_ns, n_ns = et_ns(prev["date"], 9, 30), et_ns(prev["date"], 12, 0)
        h, m = map(int, prev["close_ct"].split(":"))
        c_ns = et_ns(prev["date"], h + 1, m)
        i0 = int(np.searchsorted(dp.ts, o_ns, "left")); i_noon = int(np.searchsorted(dp.ts, n_ns, "right")); i_c = int(np.searchsorted(dp.ts, c_ns, "right"))
        O, C, P12 = dp.px[i0], dp.px[i_c - 1], dp.px[i_noon - 1]
        assert abs(row["f_prev_am_ret_r"] * row["R20"] - (P12 - O)) < 1e-6
        assert abs(row["f_prev_rth_ret_pct"] - (C - O) / O) < 1e-9
        assert row["f_prev_T1"] == prev["y_T1"] == (0 if P12 == O else (1 if P12 > O else -1))
        assert abs(row["f_prev_rng_r"] * row["R20"] - (dp.px[i0:i_c].max() - dp.px[i0:i_c].min())) < 1e-6


# 6. labels are functions of the >= 09:30 prints only and reproduce from post_stats on the raw day
def test_labels_reproduce(daily):
    for d in _sample_days(daily, 20):
        row = daily.filter(pl.col("date") == d).to_dicts()[0]
        dp = load_day(d)
        post = post_stats(dp, d, et_ns(d, 16, 0), row["R20"])
        y = make_targets(post, row["R20"])
        for t in TARGETS:
            assert y[t] == row[t], (d, t)
        # and the labels do not change if pre-open prints are removed entirely
        i0 = int(np.searchsorted(dp.ts, et_ns(d, 9, 30), "left"))
        from nqgc.bias.session import DayPrints
        dp2 = DayPrints(d, dp.symbol, dp.ts[i0:], dp.px[i0:], dp.size[i0:], dp.sgn[i0:])
        y2 = make_targets(post_stats(dp2, d, et_ns(d, 16, 0), row["R20"]), row["R20"])
        assert y2 == y


# 7. roll days: the continuous-price gap does not carry the roll spread
def test_roll_gap(daily, feats):
    adj = roll_adj()
    r = feats.join(daily.select(["date", "pre_p0929", "adj"]), on="date").filter(pl.col("eligible") & (pl.col("f_roll_day") == 1.0))
    assert r.height >= 8
    prev_close = []
    for d in r["date"].to_list():
        p = daily.filter((pl.col("date") < d) & pl.col("is_rth")).sort("date").tail(1).to_dicts()[0]
        prev_close.append((p["post_close"], p["adj"]))
    raw = np.array([row["pre_p0929"] - pc for row, (pc, _) in zip(r.to_dicts(), prev_close)])
    spread = np.array([row["adj"] - pa for row, (_, pa) in zip(r.to_dicts(), prev_close)])
    adjd = r["f_gap_close_r"].to_numpy() * r["R20"].to_numpy()
    assert np.allclose(adjd, raw - spread, atol=1e-6)
    big = np.abs(spread) >= 20
    if big.sum() >= 3:
        assert np.median(np.abs(adjd[big])) <= np.median(np.abs(raw[big]))


# 8. no data outside development in the E0 / E2 products; no Phase-5 holdout access in the ledger
def test_no_forbidden_dates(daily):
    assert daily["date"].min() >= dt.date(2021, 1, 4) and daily["date"].max() <= dt.date(2023, 12, 31)
    led = RUNS_DIR / "HOLDOUT_LEDGER.md"
    if led.exists():
        for line in led.read_text().splitlines():
            assert "phase5" not in line.lower() and "bias" not in line.lower(), line


# 9. sequence array consistency: sum of 1-min log returns equals log(p0929 / first 18:00 close)
def test_sequence_alignment(daily):
    seq = np.load(E0 / "seq1m_development.npy")
    dates = pl.read_parquet(E0 / "seq1m_dates_development.parquet")["date"].to_list()
    for d in _sample_days(daily, 10):
        i = dates.index(d)
        row = daily.filter(pl.col("date") == d).to_dicts()[0]
        assert abs(seq[i].sum() - row["pre_on_seq_sum"]) < 1e-9
        dp = load_day(d).before(et_ns(d, 9, 30))
        t_open = et_ns(d - dt.timedelta(days=1), 18, 0)
        k = int(np.searchsorted(dp.ts, t_open + NS_MIN, "left")) - 1
        first_close = dp.px[k] if k >= 0 else np.nan
        assert abs(seq[i].sum() - np.log(dp.px[-1] / first_close)) < 1e-9
