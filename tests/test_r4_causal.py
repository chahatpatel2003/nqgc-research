"""Causality proof for the rebuilt R4 level engine.

truncation: for random (session, T) the engine run on data known at T must reproduce EXACTLY the zones with
available_ts <= T, taps known at T (tap_ts + 1 <= T) and fires decided by T (decision_ts <= T) of the full run.
Component tests cover: pivot confirmation timing, ATR from prior sessions only, zone width, zone birth, zone
invalidation (age / tap count), re-arm, first touch, contract roll adjustment and per-session reset.
Requires the tick cache (skipped if absent)."""
import datetime as dt, sys
from pathlib import Path
import numpy as np, polars as pl, pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "phase2"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "phase3"))
from nqgc.levels_r4 import R4Engine, build_session, zigzag_confirmed, Zone, DEFAULT_PARAMS
from nqgc.paths import CACHE_DIR

HAVE_CACHE = (CACHE_DIR / "nq_front_ticks").exists()
pytestmark = pytest.mark.skipif(not HAVE_CACHE, reason="tick cache not present")


def _days(lo, hi):
    from common import nq_days
    return [x["date"] for x in nq_days("development", None, "r4 causality tests", exclude_early_close=False) if lo <= x["date"] <= hi]


def _run(dates, truncate=None, params=None):
    from r4_driver import run_sessions
    e = R4Engine(params); run_sessions(dates, {"e": e}, truncate=truncate)
    return e


def _key_frames(e):
    z, t, f = e.frames()
    zc = ["zid", "session", "scale", "dir", "price", "hw", "pivot_ts", "confirm_ts", "available_ts"]
    tc = ["session", "zid", "tap_ts", "tap_no", "zlo", "zhi", "below"]
    fc = ["session", "zid", "tap_ts", "displacement", "fire_ts", "decision_ts"]
    return (z.select(zc).sort(zc) if not z.is_empty() else z, t.select(tc).sort(tc) if not t.is_empty() else t, f.select(fc).sort(fc) if not f.is_empty() else f)


@pytest.fixture(scope="module")
def full_run():
    dates = _days(dt.date(2021, 1, 4), dt.date(2021, 2, 26))
    return dates, _run(dates)


def test_truncation_random_timestamps(full_run):
    dates, full = full_run
    zf, tf, ff = _key_frames(full)
    rng = np.random.default_rng(20260902)
    fails = []
    for _ in range(12):
        d = dates[int(rng.integers(20, len(dates)))]        # sessions with a valid ATR
        day_t = tf.filter(pl.col("session") == d)
        if day_t.is_empty():
            continue
        T = int(rng.choice(day_t["tap_ts"].to_numpy())) + int(rng.integers(-120, 900))     # around real taps
        part = _run(dates, truncate=(d, T * 1_000_000_000))
        zp, tp, fp = _key_frames(part)
        ez = zf.filter(pl.col("available_ts") <= T); et = tf.filter(pl.col("tap_ts") + 1 <= T); ef = ff.filter(pl.col("decision_ts") <= T)
        ok = (zp.equals(ez) if not zp.is_empty() else ez.is_empty()) and (tp.equals(et) if not tp.is_empty() else et.is_empty()) and (fp.equals(ef) if not fp.is_empty() else ef.is_empty())
        if not ok:
            fails.append((d, T, zp.height, ez.height, tp.height, et.height, fp.height, ef.height))
    assert not fails, f"truncation mismatches: {fails}"


def test_pivot_confirmation_timing_and_availability(full_run):
    _, full = full_run
    z, _, _ = full.frames()
    assert (z["confirm_ts"] >= z["pivot_ts"]).all()
    assert (z["available_ts"] == z["confirm_ts"] + 60).all()
    # synthetic: pivot high at bar 3, reversal threshold 10 crossed at bar 6 -> confirm index 6
    hi = np.array([100, 101, 102, 110, 108, 104, 99.0]); lo = hi - 1
    piv = zigzag_confirmed(hi, lo, 10.0)
    highs = [p_ for p_ in piv if p_[2] == 1]
    assert highs and highs[0][0] == 3 and highs[0][3] == 6      # pivot at bar 3, confirmed at bar 6 (first bar with a >= 10 reversal)


def test_no_tap_before_availability(full_run):
    _, full = full_run
    z, t, f = full.frames()
    av = dict(zip(z["zid"].to_list(), z["available_ts"].to_list()))
    assert all(r["tap_ts"] >= av[r["zid"]] for r in t.iter_rows(named=True))
    assert (f["decision_ts"] > f["tap_ts"]).all() and (f["fire_ts"] - f["tap_ts"] <= DEFAULT_PARAMS["r4_win"]).all()


def test_atr_uses_prior_sessions_only():
    e = R4Engine()
    for r in [100.0, 110, 120, 130, 140, 150, 160]:
        e.rth_hist.append(r)
    # S-2..S-15 mean: excludes the most recent (160): mean(100..150) = 125
    assert abs(e.atr_for_next() - 125.0) < 1e-9
    e2 = R4Engine(); e2.rth_hist += [100.0, 110, 120, 130]
    assert np.isnan(e2.atr_for_next())          # fewer than 5 prior values


def test_zone_width_rule(full_run):
    _, full = full_run
    z, _, _ = full.frames()
    lo_ = np.maximum(DEFAULT_PARAMS["hw_floor"], np.minimum(z["base_range"].to_numpy() / 2, DEFAULT_PARAMS["hw_cap_atr"] * z["atr"].to_numpy()))
    assert np.allclose(z["hw"].to_numpy(), lo_)


def test_zone_invalidation_and_rearm_and_first_touch():
    """Synthetic session: one zone, two contacts separated by an out-of-band close and > 900 s -> 2 taps; a third contact
    without re-arm -> no tap; tap count cap and age cap retire zones."""
    e = R4Engine({"scales": (1000.0,), "dedup": False})      # no synthetic zones are created; only the hand-made one exists
    z = Zone(0, 0, 1, 100.0, 1.0, 0, 0, 60, 0, dt.date(2021, 1, 4), 2.0)
    e.registry[0] = z; e.rth_hist = [10.0] * 8
    n = 4020
    sec_ts = 1_000_020 + np.arange(n)
    cl = np.full(n, 90.0)
    cl[1000] = 100.0            # contact 1 at second 1000 (minute 16)
    cl[1001:2500] = 80.0        # far below -> 1-min closes outside band by > hysteresis
    cl[2500] = 100.0            # contact 2 at second 2500 (> 900 s later, after out-of-band closes) -> tap 2
    cl[2501:3100] = 99.5        # stays inside band -> no re-arm
    cl[3100] = 100.5            # contact 3: not armed -> no tap
    hi = cl.copy(); lo = cl.copy()
    m_ts = sec_ts[::60]; m_hi = hi.reshape(-1, 60).max(1); m_lo = lo.reshape(-1, 60).min(1); m_cl = cl.reshape(-1, 60)[:, -1]; m_op = cl.reshape(-1, 60)[:, 0]
    from nqgc.levels_r4 import SessionData
    sd = SessionData(dt.date(2021, 1, 5), "NQH1", sec_ts, hi, lo, cl, np.ones(n, bool), m_ts, m_hi, m_lo, m_cl, m_op, cl.copy(), 90.0, 10.0, cl[-1])
    e.process_session(sd, 0.0, 1, None, np.nan)
    taps = [r for r in e.taps_out]
    assert [r["tap_sec"] for r in taps] == [1000, 2500] and [r["tap_no"] for r in taps] == [1, 2]
    assert e.registry[0].taps == 2            # (the zone re-arms at session end because later closes are far outside the band)
    # invalidation: age
    z.form_ord = 0; e.process_session(sd, 0.0, 40, None, np.nan); assert 0 not in e.registry
    # invalidation: taps
    e2 = R4Engine({"scales": (1000.0,)}); z2 = Zone(1, 0, 1, 100.0, 1.0, 0, 0, 60, 0, dt.date(2021, 1, 4), 2.0, taps=6); e2.registry[1] = z2; e2.rth_hist = [10.0] * 8
    e2.process_session(sd, 0.0, 1, None, np.nan); assert 1 not in e2.registry


def test_contract_roll_adjustment_is_causal_and_applied():
    """A zone formed at price 100 (adj 0) must be screened at 100 + adj in a later session with adj = 10."""
    e = R4Engine({"scales": (1000.0,)}); e.rth_hist = [10.0] * 8
    z = Zone(0, 0, 1, 100.0, 1.0, 0, 0, 60, 0, dt.date(2021, 1, 4), 2.0); e.registry[0] = z
    n = 2040; sec_ts = 2_000_040 + np.arange(n); cl = np.full(n, 95.0); cl[600] = 110.0; hi = cl.copy(); lo = cl.copy()
    m_ts = sec_ts[::60]; m_hi = hi.reshape(-1, 60).max(1); m_lo = lo.reshape(-1, 60).min(1); m_cl = cl.reshape(-1, 60)[:, -1]; m_op = cl.reshape(-1, 60)[:, 0]
    from nqgc.levels_r4 import SessionData
    sd = SessionData(dt.date(2021, 3, 16), "NQM1", sec_ts, hi, lo, cl, np.ones(n, bool), m_ts, m_hi, m_lo, m_cl, m_op, cl.copy(), 95.0, 10.0, cl[-1])
    e.process_session(sd, 10.0, 5, None, np.nan)
    assert len(e.taps_out) == 1 and abs(e.taps_out[0]["zlo"] - 109.0) < 1e-9 and abs(e.taps_out[0]["zhi"] - 111.0) < 1e-9
    # the roll table itself is built from the basis session only (see scripts/phase3/build_roll_adjust.py); spreads are finite
    p = CACHE_DIR / "nq_roll_adjust.parquet"
    if p.exists():
        t = pl.read_parquet(p).filter(pl.col("spread").is_not_null())
        assert (t["n_pairs"] >= 200).all()


def test_session_reset_no_cross_session_bleed(full_run):
    """Processing sessions A,B and then only A must give identical A outputs (B cannot alter A)."""
    dates, full = full_run
    sub = dates[:30]
    a = _run(sub); b = _run(sub[:-1])
    za, ta, fa = _key_frames(a); zb, tb, fb = _key_frames(b)
    last = sub[-1]
    assert za.filter(pl.col("session") < last).equals(zb) and ta.filter(pl.col("session") < last).equals(tb) and fa.filter(pl.col("session") < last).equals(fb)
