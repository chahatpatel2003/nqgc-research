"""Aggregate Phase-2 results into a ranking with PRE-DECLARED verdict rules (written before all results were seen):
PASS     : base-cost net > 0 in development AND in every out-of-sample phase available, PF >= 1.15 in each OOS phase,
           bootstrap 95% CI of the mean trade > 0 on pooled OOS, >= 100 pooled OOS trades, stress-cost OOS net > 0.
MARGINAL : base-cost net > 0 in development and in at least one OOS phase, but a PASS condition fails.
FAIL     : base-cost net <= 0 in development, or <= 0 in every OOS phase.
Ranking key: pooled-OOS base-cost expectancy in R where defined, else in $ per trade, tie-break by OOS Sharpe."""
import json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl
from common import OUT, evaluate, ACCOUNT

rows = []
def load(name):
    p = OUT / name / "results.json"
    return json.loads(p.read_text()) if p.exists() else None

def pooled_oos(name, phases, tag):
    parts = []
    for ph in phases:
        f = OUT / name / f"trades_{ph}_{tag}.parquet"
        if f.exists():
            parts.append(pl.read_parquet(f))
    return pl.concat(parts) if parts else pl.DataFrame()

def verdict(name, phases_oos, per_phase, oos_base, oos_stress):
    dev = per_phase["development"]["base"]["summary"]
    oos = [per_phase[p]["base"]["summary"] for p in phases_oos if p in per_phase]
    if dev.get("net_pnl", 0) <= 0 or all(o.get("net_pnl", 0) <= 0 for o in oos):
        return "FAIL"
    ok = all(o.get("net_pnl", 0) > 0 and o.get("profit_factor", 0) >= 1.15 for o in oos)
    if oos_base.is_empty() or oos_base.height < 100:
        ok = False
    else:
        from nqgc.diagnostics import bootstrap_mean_ci
        m, lo, hi = bootstrap_mean_ci(oos_base["net_usd"].to_numpy())
        ok = ok and lo > 0
    if oos_stress.is_empty() or oos_stress["net_usd"].sum() <= 0:
        ok = False
    return "PASS" if ok else "MARGINAL"

for name, phases_oos in (("C_NQ_ROD", ["validation1", "validation2"]), ("E_NQ_TORB", ["validation1", "validation2"]), ("F_NQ_NoiseLong", ["validation1", "validation2"]), ("D_GC_ROD", ["validation"])):
    r = load(name)
    if not r:
        continue
    pp = r["phases"]
    ob, os_ = pooled_oos(name, phases_oos, "base"), pooled_oos(name, phases_oos, "stress")
    ev = evaluate(ob, sorted(set(ob["trade_date"].to_list())), pl.DataFrame(), r_defined=False) if not ob.is_empty() else {"summary": {}}
    rows.append(dict(strategy=name, verdict=verdict(name, phases_oos, pp, ob, os_), dev_net=pp["development"]["base"]["summary"].get("net_pnl"),
                     dev_pf=pp["development"]["base"]["summary"].get("profit_factor"),
                     oos_n=ob.height, oos_exp_usd=float(ob["net_usd"].mean()) if ob.height else None, oos_pf=ev["summary"].get("profit_factor"),
                     oos_ci=(ev.get("bootstrap_mean_trade") or {}), oos_stress_net=float(os_["net_usd"].sum()) if os_.height else None,
                     **{f"{p}_net": pp[p]["base"]["summary"].get("net_pnl") for p in phases_oos if p in pp}))
# R4 cells
ra = json.loads((OUT / "A_R4" / "results.json").read_text()) if (OUT / "A_R4" / "results.json").exists() else None
if ra:
    for cell, ph in ra["per_cell"].items():
        pp = {p: ph[p]["new"] for p in ph}
        ob = pl.concat([pl.read_parquet(OUT / "A_R4" / f"trades_{cell}_{p}_base.parquet") for p in ("validation1", "validation2") if (OUT / "A_R4" / f"trades_{cell}_{p}_base.parquet").exists()] or [pl.DataFrame()])
        os_ = pl.concat([pl.read_parquet(OUT / "A_R4" / f"trades_{cell}_{p}_stress.parquet") for p in ("validation1", "validation2") if (OUT / "A_R4" / f"trades_{cell}_{p}_stress.parquet").exists()] or [pl.DataFrame()])
        ev = evaluate(ob, sorted(set(ob["trade_date"].to_list())), pl.DataFrame()) if not ob.is_empty() else {"summary": {}}
        rows.append(dict(strategy=f"A_R4/{cell}", verdict=verdict(cell, ["validation1", "validation2"], pp, ob, os_), dev_net=pp["development"]["base"]["summary"].get("net_pnl"),
                         dev_pf=pp["development"]["base"]["summary"].get("profit_factor"), oos_n=ob.height, oos_exp_usd=float(ob["net_usd"].mean()) if ob.height else None,
                         oos_pf=ev["summary"].get("profit_factor"), oos_ci=(ev.get("bootstrap_mean_trade") or {}), oos_expR=ev["summary"].get("avg_r"),
                         oos_stress_net=float(os_["net_usd"].sum()) if os_.height else None,
                         **{f"{p}_net": pp[p]["base"]["summary"].get("net_pnl") for p in ("validation1", "validation2") if p in pp}))
cf = OUT / "A_R4" / "causal_fix_results.json"
if cf.exists():
    cfr = json.loads(cf.read_text())
    for cell in cfr:
        pp = {ph: {"base": {"summary": {"net_pnl": cfr[cell][ph]["new_base"]["net"], "profit_factor": cfr[cell][ph]["new_base"]["pf"]}}} for ph in cfr[cell]}
        ob = pl.concat([pl.read_parquet(OUT / "A_R4" / f"trades_causalfix_{cell}_{p}_base.parquet") for p in ("validation1", "validation2")])
        ev = evaluate(ob, sorted(set(ob["trade_date"].to_list())), pl.DataFrame())
        os_ = pl.concat([pl.read_parquet(OUT / "A_R4" / f"trades_causalfix_{cell}_{p}_stress.parquet") for p in ("validation1", "validation2")])
        v = verdict(cell, ["validation1", "validation2"], pp, ob, os_)
        rows.append(dict(strategy=f"A_R4-CAUSALFIX/{cell}", verdict=v, dev_net=pp["development"]["base"]["summary"]["net_pnl"], dev_pf=pp["development"]["base"]["summary"]["profit_factor"],
                         oos_n=ob.height, oos_exp_usd=float(ob["net_usd"].mean()), oos_pf=ev["summary"].get("profit_factor"), oos_ci=(ev.get("bootstrap_mean_trade") or {}), oos_expR=ev["summary"].get("avg_r"),
                         oos_stress_net=float(os_["net_usd"].sum()), validation1_net=pp["validation1"]["base"]["summary"]["net_pnl"], validation2_net=pp["validation2"]["base"]["summary"]["net_pnl"]))
rows.sort(key=lambda r: (-(r["oos_exp_usd"] or -1e9)))
L = ["# Phase-2 ranking (pooled out-of-sample, BASE costs) — no optimisation performed", "", "| rank | strategy | verdict | dev net $ | dev PF | OOS n | OOS $/trade [95% CI] | OOS PF | OOS expR | val1 net $ | val2/val net $ | OOS stress net $ |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for i, r in enumerate(rows, 1):
    ci = r["oos_ci"]; cis = f"[{ci.get('ci95_lo', float('nan')):,.0f}, {ci.get('ci95_hi', float('nan')):,.0f}]" if ci else ""
    v2 = r.get("validation2_net", r.get("validation_net"))
    L.append(f"| {i} | {r['strategy']} | **{r['verdict']}** | {r['dev_net']:,.0f} | {r['dev_pf']:.2f} | {r['oos_n']} | {r['oos_exp_usd'] if r['oos_exp_usd'] is None else round(r['oos_exp_usd'],1)} {cis} | {r['oos_pf'] if r['oos_pf'] is None else round(r['oos_pf'],2)} | {r.get('oos_expR') if r.get('oos_expR') is None else round(r['oos_expR'],3)} | {r.get('validation1_net') if r.get('validation1_net') is None else round(r['validation1_net'])} | {v2 if v2 is None else round(v2)} | {r['oos_stress_net'] if r['oos_stress_net'] is None else round(r['oos_stress_net'])} |")
(OUT / "RANKING.md").write_text("\n".join(L)); print("\n".join(L))
