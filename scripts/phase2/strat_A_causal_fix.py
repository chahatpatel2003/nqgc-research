"""R4 P14 cell + H2 cells with the CHRONOLOGY CORRECTION: exclude fires whose tap occurred inside the zone's confirmation
minute (age_min < 1), because the zigzag confirmation needs that minute's low and the zone is only knowable at the minute's close.
Not an optimisation: a causality filter applied uniformly. Reported per phase at base cost, plus the 2022-26 window."""
import datetime as dt, json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, pandas as pd, polars as pl
from common import *
from nqgc.tick_engine import TickExecutor, Intent
from nqgc.calendar import session_close_utc
from strat_A_r4 import FIRE, SPEC_ID, CELLS, old_engine, old_summary

fire = pd.read_parquet(FIRE); fire["session"] = fire["session"].astype(str)
fire = fire[(fire["tap_no"] <= 3) & (fire["age_min"] >= 1.0)].copy(); fire["date"] = pd.to_datetime(fire["session"]).dt.date
out = {}
for cell, k, S, T in CELLS[:3]:      # P14 cell + first two H2 cells (S15/T30, S15/T40)
    out[cell] = {}
    for phase in NQ_PHASES:
        days = nq_days(phase, SPEC_ID, f"R4 causal-fix {cell}", exclude_early_close=False)
        dset = {x["date"] for x in days}
        f = fire[fire["date"].isin(dset) & fire[f"ck{k}_epx"].notna()]
        old = old_summary(old_engine(f, k, S, T)) if len(f) else {}
        out[cell][phase] = dict(old=old)
        for tier in ("gross", "base", "stress"):
          ex = TickExecutor(cost_for("NQ", tier), "NQ", f"R4fix_{cell}")
          for x in days:
            fd = f[f["date"] == x["date"]]
            if fd.empty:
                continue
            tk = load_day_ticks(x["date"])
            if tk is None:
                continue
            ts, px, sym = tk
            close_ns = int(session_close_utc(x["date"], "NQ").timestamp() * 1e9)
            ex.run_day(x["date"], sym, ts, px, [Intent(int((r.tap_ts + r.fire_s + 1 + k) * 1e9), -1, 1, stop_offset=S, target_offset=T, exit_ts_ns=close_ns, tag=cell) for r in fd.itertuples()])
          led = ex.ledger(); s = summary(led, ACCOUNT, n_trade_dates=len(days))
          from nqgc.diagnostics import bootstrap_mean_ci
          m, lo, hi = bootstrap_mean_ci(led["r_multiple"].to_numpy()) if not led.is_empty() else (None, None, None)
          ev = evaluate(led, [x["date"] for x in days], daily_ctx_nq(days) if tier == "base" else pl.DataFrame())
          out[cell][phase][f"new_{tier}"] = dict(n=s["trades"], expR=s["avg_r"], ci=[lo, hi], pf=s["profit_factor"], wr=s["win_rate"], net=s["net_pnl"], maxdd=s["max_drawdown_usd"], sharpe=s["sharpe_daily_ann"], full=ev)
          led.write_parquet(OUT / "A_R4" / f"trades_causalfix_{cell}_{phase}_{tier}.parquet")
          print(cell, phase, tier, "OLD(age>=1)", {k_: (round(v, 3) if isinstance(v, float) else v) for k_, v in old.items() if k_ in ("n", "expR", "pf", "wr")}, "NEW", {k_: (round(v, 3) if isinstance(v, float) else v) for k_, v in out[cell][phase][f"new_{tier}"].items() if k_ not in ("ci", "full")}, flush=True)
(OUT / "A_R4" / "causal_fix_results.json").write_text(json.dumps(out, indent=1, default=str))
print("DONE")
