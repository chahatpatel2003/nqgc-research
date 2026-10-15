"""Multi-session driver for the causal R4 engine (shared by the builder, the truncation tests and the diagnostics)."""
from __future__ import annotations
import datetime as dt, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl
from common import load_day_ticks_full, nq_front_map
from nqgc.calendar import ct_wallclock_to_utc, session_close_utc
from nqgc.levels_r4 import R4Engine, build_session, DEFAULT_PARAMS
from nqgc.paths import CACHE_DIR


def roll_adj_table() -> dict:
    p = CACHE_DIR / "nq_roll_adjust.parquet"
    if not p.exists():
        return {}
    t = pl.read_parquet(p)
    return {r["session"]: float(r["adj"]) for r in t.iter_rows(named=True)}


def rth_utc(d: dt.date) -> tuple[int, int]:
    a = ct_wallclock_to_utc(d, "08:30", "NQ"); b = ct_wallclock_to_utc(d, "15:00", "NQ")
    return int(a.timestamp()), int(b.timestamp())


def run_sessions(dates: list[dt.date], engines: dict[str, R4Engine], truncate: tuple[dt.date, int] | None = None, verbose: bool = False):
    """Process sessions in order. truncate=(date, T_ns): that session sees only data known at T (complete seconds/minutes,
    taps known at t+1, fires decided by f+1); later sessions are not processed. Sessions before it are processed fully."""
    adj = roll_adj_table(); fm = nq_front_map()
    from common import nq_cal
    early = set(nq_cal().get("early_closes", {}).keys())
    closes = []
    for i, d in enumerate(dates):
        T = None
        if truncate is not None and d == truncate[0]:
            T = truncate[1]
        elif truncate is not None and d > truncate[0]:
            break
        if str(d) in early:          # frozen pipeline built no bars/zones/ATR for holiday (early-close) sessions
            continue
        tk = load_day_ticks_full(d)
        if tk is None:
            continue
        ts, px, sz, sym = tk
        sd = build_session(d, sym, ts, px, sz, truncate_ns=T, rth_utc=rth_utc(d), close_ts=int(session_close_utc(d, "NQ").timestamp()))
        if sd is None:
            continue
        # trend regime from PRIOR closes only; ATR percentile from prior ATRs
        trend_up = None
        if len(closes) >= 20:
            trend_up = bool(closes[-1] > float(np.mean(closes[-20:])))
        for name, eng in engines.items():
            atr_now = eng.atr_for_next()
            hist = [x for x in eng._atr_hist[-252:]] if hasattr(eng, "_atr_hist") else []
            atr_pct = float(np.mean(np.array(hist) <= atr_now)) if (len(hist) >= 60 and np.isfinite(atr_now)) else np.nan
            eng.process_session(sd, adj.get(d, 0.0), i, trend_up, atr_pct, T_known=(T // 1_000_000_000) if T is not None else None)
            if T is None:
                eng.end_session(sd)
                if not hasattr(eng, "_atr_hist"):
                    eng._atr_hist = []
                if np.isfinite(atr_now):
                    eng._atr_hist.append(atr_now)
        if T is None:
            closes.append(sd.close_px)
        if verbose and i % 50 == 0:
            print(d, {k: (len(e.zones_out), len(e.taps_out), len(e.fires_out)) for k, e in engines.items()}, flush=True)
        if T is not None:
            break
