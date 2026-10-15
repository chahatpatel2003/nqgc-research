"""STRATEGY A — R4 'tap-and-go' (frozen nq-levels R4v10 continuation), replayed through the new tick engine.

Signal stream = the FROZEN fire dataset (/Volumes/T9/nq data/nq_levels/daily/p14_fire.parquet, sha256 verified against
HOLDOUT_FREEZE_MANIFEST.json; 299/299 sampled fires reproduced from raw ticks). Rules ported verbatim:
  * resistance-role taps only (approach from below), tap_no <= 3, n_fwd >= 1800 s, zone lifecycle per frozen zones.py/interactions.py
  * R4v10: first second f <= t+60 whose LOW is >= 10.0 pts below the zone's near (lower) edge; decision at the end of second f
  * entry SHORT at the next executable print after the decision boundary (+k seconds for checkpoint k), slippage per tier
  * bracket relative to the actual fill: stop = fill + S, target = fill - T; exit at the session end (16:00 CT) otherwise
  * one open trade at a time (chronological portfolio rule)
Cells: P14 baseline (ck2, S12.5/T30) and the 8 H2 tap<=3 cells (ck0, S in {15,17.5,20,25} x T in {30,40}). No selection is made.
OLD-engine numbers are recomputed with the frozen evaluator logic on the same fire rows (1-s first-passage grids, flat 1.0 pt RT).
"""
import datetime as dt, json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, pandas as pd, polars as pl
from common import *
from common import _fmt
from nqgc.tick_engine import TickExecutor, Intent
from nqgc.calendar import session_close_utc

FIRE = "/Volumes/T9/nq data/nq_levels/daily/p14_fire.parquet"
CELLS = [("P14_ck2_S12.5_T30", 2, 12.5, 30.0)] + [(f"H2_ck0_S{s}_T{int(t)}", 0, s, t) for s in (15.0, 17.5, 20.0, 25.0) for t in (30.0, 40.0)]
RULES = open(__file__).read().split('"""')[1]
SPEC_ID = freeze_or_load("R4_tapandgo", "1.0-frozen-nqlevels", "NQ", 1, RULES,
                         dict(r4_pts=10.0, window_s=60, tap_max=3, n_fwd_min=1800, cells=[c[0] for c in CELLS], one_open=True, exit="session_end_16:00CT"),
                         "H-A", notes="signal stream = frozen p14_fire.parquet; execution re-done at tick level")


def old_engine(f: pd.DataFrame, k: int, S: float, T: float, cost_pts: float = 1.0) -> pd.DataFrame:
    """Verbatim port of run_p18_stageb.h2_eval / run_p14_final.trades_for (frozen code)."""
    d = f[f[f"ck{k}_epx"].notna()].copy()
    up = d[f"ck{k}_up{S}"].fillna(-1).to_numpy(); dn = d[f"ck{k}_dn{T}"].fillna(-1).to_numpy()
    win = (dn >= 0) & ((up < 0) | (dn < up)); loss = (up >= 0) & ~win
    end = (d[f"ck{k}_epx"] - d[f"ck{k}_endpx"]).to_numpy() / 4.0
    d["pnl"] = np.where(win, T, np.where(loss, -S, end)) - cost_pts
    d["t_open"] = d[f"ck{k}_eidx"]; d["t_close"] = d["t_open"] + np.where(win, dn, np.where(loss, up, 10 ** 9))
    d = d.sort_values(["session", "t_open", "zid", "tap_sec"], kind="stable")
    keep, cs, cc = [], None, -1
    for r in d.itertuples():
        ok = r.session != cs or r.t_open >= cc
        keep.append(ok)
        if ok:
            cs, cc = r.session, r.t_close
    d = d[np.array(keep)].copy(); d["R"] = d["pnl"] / S; d["win"] = win[np.array(keep)]
    d["res"] = np.where(d["win"], "target", np.where(loss[np.array(keep)], "stop", "end"))
    return d


def old_summary(d: pd.DataFrame) -> dict:
    pnl = d["pnl"].to_numpy()
    w = pnl[pnl > 0]; l = pnl[pnl < 0]
    eq = np.cumsum(d["R"].to_numpy()); dd = float(np.max(np.maximum.accumulate(np.concatenate([[0], eq])) - np.concatenate([[0], eq])))
    return dict(n=int(len(d)), expR=float(d["R"].mean()), pf=float(w.sum() / -l.sum()) if len(l) else float("inf"), wr=float((pnl > 0).mean()),
                pts=float(pnl.sum()), usd_at_20=float(pnl.sum() * 20), maxdd_R=dd, stop=int((d["res"] == "stop").sum()), target=int((d["res"] == "target").sum()), end=int((d["res"] == "end").sum()))


def main():
    fire = pd.read_parquet(FIRE); fire["session"] = fire["session"].astype(str)
    fire = fire[(fire["tap_no"] <= 3)].copy()
    fire["date"] = pd.to_datetime(fire["session"]).dt.date
    spec = dict(name="R4_tapandgo", version="1.0-frozen-nqlevels", spec_id=SPEC_ID, cells=CELLS, source_files=[
        "nq-levels/src/nqlevels/features/zones.py (zone universe, band, confirmation)", "nq-levels/src/nqlevels/features/interactions.py (tap engine, re-arm, tap_no, side)",
        "nq-levels/scripts/p14_common.py (R4v10 fire rule, checkpoints, entry convention, S/T grids)", "nq-levels/scripts/build_p14_fire.py (fire dataset: resistance role, n_fwd>=1800)",
        "nq-levels/scripts/run_p18_stageb.py (H2 cells, one-open-trade rule, 1.0 pt cost)", "nq-levels/scripts/run_p14_final.py (P14 baseline cell ck2 S12.5/T30)",
        "nq-levels/RESEARCH_PLAN.md §18.2, §20.2, §21.1, §29; EXPERIMENT_LOG.md P13-384, P14-392, P18-403/404, P24"])
    notes = ["OLD = frozen evaluator on 1-s bars (stop on 1-s high touch, target on 1-s low TOUCH, same-second tie = stop, flat 1.0 pt RT). NEW = tick engine (stop on first print at/through + slippage, target requires trade-THROUGH by 1 tick, exact print order).",
             "Legacy tier = NEW gross ledger minus a flat 1.0 pt ($20) per trade, to isolate execution differences from cost differences.",
             "Holdout 2026-06-18..08-14 NOT touched. NOTE: nq-levels Phase 17B already opened that window once for the model-gated Balanced variant (FAIL)."]
    per_cell = {}
    ledgers = {}
    for cell, k, S, T in CELLS:
        per_cell[cell] = {}
        for phase in NQ_PHASES:
            days = nq_days(phase, SPEC_ID, f"R4 replay {cell}", exclude_early_close=False, exclude_roll=False)
            dset = {x["date"] for x in days}
            f = fire[fire["date"].isin(dset) & fire[f"ck{k}_epx"].notna()]
            old = old_summary(old_engine(f, k, S, T)) if len(f) else {}
            tiers = {}
            for tier in ("gross", "base", "stress"):
                cost = cost_for("NQ", tier)
                ex = TickExecutor(cost, "NQ", f"R4_{cell}")
                for x in days:
                    fd = f[f["date"] == x["date"]]
                    if fd.empty:
                        continue
                    tk = load_day_ticks(x["date"])
                    if tk is None:
                        continue
                    ts, px, sym = tk
                    close_ns = int(session_close_utc(x["date"], "NQ").timestamp() * 1e9)
                    intents = [Intent(int((r.tap_ts + r.fire_s + 1 + k) * 1e9), -1, 1, stop_offset=S, target_offset=T, exit_ts_ns=close_ns, tag=cell,
                                      meta=dict(zid=int(r.zid), tap_no=int(r.tap_no))) for r in fd.itertuples()]
                    ex.run_day(x["date"], sym, ts, px, intents)
                led = ex.ledger()
                ledgers[f"{cell}_{phase}_{tier}"] = led
                ctx = daily_ctx_nq(days) if tier == "base" else pl.DataFrame()
                tiers[tier] = evaluate(led, [x["date"] for x in days], ctx)
                tiers[tier]["skipped"] = {w: sum(1 for s_ in ex.skipped if s_["why"] == w) for w in set(s_["why"] for s_ in ex.skipped)}
            g = ledgers[f"{cell}_{phase}_gross"]
            if not g.is_empty():
                leg = g.with_columns((pl.col("net_usd") - 20.0).alias("net_usd"), (pl.col("r_multiple") - 20.0 / (pl.col("init_stop") - pl.col("entry_px")).abs() / 20.0).alias("r_multiple"))
                tiers["legacy_1pt"] = evaluate(leg, [x["date"] for x in days], pl.DataFrame())
            per_cell[cell][phase] = dict(old=old, new=tiers)
            print(cell, phase, "OLD", {k_: (round(v, 3) if isinstance(v, float) else v) for k_, v in old.items()},
                  "| NEW base:", {k_: round(tiers["base"]["summary"].get(k_, float("nan")), 3) for k_ in ("trades", "avg_r", "profit_factor", "win_rate", "net_pnl")}, flush=True)
    d = assert_writable_target(OUT / "A_R4"); d.mkdir(parents=True, exist_ok=True)
    (d / "results.json").write_text(json.dumps(dict(spec=spec, per_cell=per_cell, notes=notes), indent=1, default=str))
    for k_, led in ledgers.items():
        if not led.is_empty():
            led.write_parquet(d / f"trades_{k_}.parquet")
    # markdown: per cell old vs new
    L = [f"# STRATEGY A — R4 tap-and-go (frozen nq-levels R4v10) — old vs new engine", "", "```", json.dumps(spec, indent=1, default=str), "```", ""] + [f"- {n}" for n in notes] + [""]
    for cell in per_cell:
        L.append(f"## {cell}")
        L.append("| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for phase, r in per_cell[cell].items():
            o = r["old"]; n = r["new"]
            def g(t, key): return _fmt(n[t]["summary"].get(key)) if t in n else "n/a"
            L.append(f"| {phase} | {o.get('n','')} | {_fmt(o.get('expR'),3)} | {_fmt(o.get('pf'))} | {_fmt(o.get('wr'))} | {_fmt(o.get('pts'),0)} | {g('legacy_1pt','trades')} | {g('legacy_1pt','avg_r')} | {g('legacy_1pt','profit_factor')} | {g('gross','avg_r')} | {g('gross','profit_factor')} | {g('base','trades')} | {g('base','avg_r')} | {g('base','profit_factor')} | {g('base','win_rate')} | {g('base','net_pnl')} | {g('stress','avg_r')} | {g('stress','profit_factor')} |")
        L.append("")
    (d / "REPORT.md").write_text("\n".join(L))
    # full report for the P14 cell
    c0 = CELLS[0][0]
    (d / "REPORT_P14cell_full.md").write_text(report_md("A — R4 P14 cell (ck2, S12.5/T30)", spec, {ph: per_cell[c0][ph]["new"] for ph in per_cell[c0]}, notes))
    print("saved", d)


if __name__ == "__main__":
    main()
