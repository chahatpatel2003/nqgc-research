"""Phase-4 master table, verdicts (pre-declared), outlier dependence, cost robustness, D faithful-vs-corrected, equal-risk bucket."""
import json, math, sys, datetime as dt
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl
from nqgc.paths import RUNS_DIR, DOCS_DIR
from nqgc import diagnostics as dg
from common import nq_days, NQ_PHASES
OUT = RUNS_DIR / "phase4"
A = json.loads((OUT / "A_NQ_NoiseLong" / "results.json").read_text())["phases"]
D = json.loads((OUT / "D_NQ_ORB_retrace" / "results.json").read_text())
F = json.loads((OUT / "F_GC" / "results.json").read_text())["phases"]
G = json.loads((OUT / "G_GC" / "results.json").read_text())["phases"]


def f(v, nd=2):
    return "n/a" if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else (f"{v:,.{nd}f}" if isinstance(v, float) else str(v))


def verdict(dev, oos_list, pooled_led, stress_oos_net):
    """PASS: base net>0 in dev and every OOS phase, PF>=1.15 each OOS, pooled-OOS CI>0, >=100 OOS trades, stress OOS net>0,
    OOS net still >0 after removing top-3 winners. MARGINAL: pooled OOS base net>0 but a condition fails. FAIL otherwise."""
    if dev.get("net_pnl", 0) <= 0 or pooled_led.is_empty() or pooled_led["net_usd"].sum() <= 0:
        return "FAIL"
    ok = all(o.get("net_pnl", 0) > 0 and o.get("profit_factor", 0) >= 1.15 for o in oos_list)
    ok &= pooled_led.height >= 100
    m, lo, hi = dg.bootstrap_mean_ci(pooled_led["net_usd"].to_numpy()); ok &= lo > 0
    ok &= (stress_oos_net is not None and stress_oos_net > 0)
    od = dg.outlier_dependence(pooled_led); ok &= od["excl_top3"] > 0
    return "PASS" if ok else "MARGINAL"


rows = []; bucket_series = {}; details = {}
days_all = {ph: [x["date"] for x in nq_days(ph, "agg" if ph != "development" else None, "phase4 aggregate", exclude_early_close=True)] for ph in NQ_PHASES}
oos_days = days_all["validation1"] + days_all["validation2"]
# ---- A ----
led = {ph: pl.read_parquet(OUT / "A_NQ_NoiseLong" / f"trades_{ph}_base.parquet") for ph in NQ_PHASES}
pooled = pl.concat([led["validation1"], led["validation2"]]); st = pl.concat([pl.read_parquet(OUT / "A_NQ_NoiseLong" / f"trades_{ph}_stress.parquet") for ph in ("validation1", "validation2")])
v = verdict(A["development"]["base"]["summary"], [A[p]["base"]["summary"] for p in ("validation1", "validation2")], pooled, float(st["net_usd"].sum()))
od = dg.outlier_dependence(pooled); m, lo, hi = dg.bootstrap_mean_ci(pooled["net_usd"].to_numpy())
rows.append(dict(strategy="A NQ Noise-Area long", source="Zarattini/Aziz/Barbon 2024", instrument="NQ", recoverable="yes", trades=f"{A['development']['base']['summary']['trades']}/{A['validation1']['base']['summary']['trades']}/{A['validation2']['base']['summary']['trades']}",
                 dev=A["development"]["base"]["summary"]["expectancy_usd"], val1=A["validation1"]["base"]["summary"]["expectancy_usd"], val2=A["validation2"]["base"]["summary"]["expectancy_usd"],
                 pf=f"{A['development']['base']['summary']['profit_factor']:.2f}/{A['validation1']['base']['summary']['profit_factor']:.2f}/{A['validation2']['base']['summary']['profit_factor']:.2f}",
                 maxdd=f"{A['development']['base']['summary']['max_drawdown_usd']:,.0f}/{A['validation1']['base']['summary']['max_drawdown_usd']:,.0f}/{A['validation2']['base']['summary']['max_drawdown_usd']:,.0f}",
                 sharpe=f"{A['development']['base']['summary']['sharpe_daily_ann']:.2f}/{A['validation1']['base']['summary']['sharpe_daily_ann']:.2f}/{A['validation2']['base']['summary']['sharpe_daily_ann']:.2f}",
                 outlier=f"OOS excl top1/3/5: {od['excl_top1']:,.0f}/{od['excl_top3']:,.0f}/{od['excl_top5']:,.0f} of {od['total']:,.0f}; top1/5/10%: {100*od['share_top1pct']:.0f}/{100*od['share_top5pct']:.0f}/{100*od['share_top10pct']:.0f}%",
                 cost=f"OOS net gross/base/stress/2x: {sum(A[p]['gross']['summary']['net_pnl'] for p in ('validation1','validation2')):,.0f}/{sum(A[p]['base']['summary']['net_pnl'] for p in ('validation1','validation2')):,.0f}/{sum(A[p]['stress']['summary']['net_pnl'] for p in ('validation1','validation2')):,.0f}/{sum(A[p]['stress2x']['summary']['net_pnl'] for p in ('validation1','validation2')):,.0f}",
                 ci=f"[{lo:,.0f}, {hi:,.0f}]", verdict=v, oos_exp=float(pooled["net_usd"].mean())))
details["A"] = {ph: {t: {k: A[ph][t].get(k) for k in ("outliers", "calmar")} | {"summary": {k: A[ph][t]["summary"].get(k) for k in ("trades", "expectancy_usd", "gross_expectancy_usd", "profit_factor", "win_rate", "avg_winner", "avg_loser", "net_pnl", "max_drawdown_usd", "sharpe_daily_ann", "sortino_daily_ann", "avg_hold_minutes", "exposure", "consecutive_losses")}} for t in A[ph]} for ph in A}
if v != "FAIL":
    bucket_series["A_noise_long"] = dg.daily_pnl_series(pl.concat(list(led.values())), sum(days_all.values(), []))
# ---- D cells ----
dcells = {}
for cell, per in D["cells"].items():
    ledc = {ph: (pl.read_parquet(OUT / "D_NQ_ORB_retrace" / f"trades_{cell}_{ph}_corrected_base.parquet") if (OUT / "D_NQ_ORB_retrace" / f"trades_{cell}_{ph}_corrected_base.parquet").exists() else pl.DataFrame()) for ph in NQ_PHASES}
    pooled = pl.concat([x for x in (ledc["validation1"], ledc["validation2"]) if not x.is_empty()]) if any(not x.is_empty() for x in (ledc["validation1"], ledc["validation2"])) else pl.DataFrame()
    stp = [OUT / "D_NQ_ORB_retrace" / f"trades_{cell}_{ph}_corrected_stress.parquet" for ph in ("validation1", "validation2")]
    st = pl.concat([pl.read_parquet(p) for p in stp if p.exists()]) if any(p.exists() for p in stp) else pl.DataFrame()
    s = {ph: per[ph]["corrected_base"]["summary"] for ph in NQ_PHASES}
    v = verdict(s["development"], [s["validation1"], s["validation2"]], pooled, float(st["net_usd"].sum()) if not st.is_empty() else None)
    od = dg.outlier_dependence(pooled) if not pooled.is_empty() else {}
    m, lo, hi = dg.bootstrap_mean_ci(pooled["net_usd"].to_numpy()) if not pooled.is_empty() else (float("nan"),) * 3
    fa = {ph: per[ph]["faithful_zero"]["summary"] for ph in NQ_PHASES}
    dcells[cell] = dict(v=v, s=s, fa=fa, pooled=pooled, od=od, ci=(lo, hi), leds=ledc,
                        gross={ph: per[ph]["corrected_gross"]["summary"]["net_pnl"] for ph in NQ_PHASES}, stress={ph: per[ph]["corrected_stress"]["summary"]["net_pnl"] for ph in NQ_PHASES}, stress2x={ph: per[ph]["corrected_stress2x"]["summary"]["net_pnl"] for ph in NQ_PHASES})
    rows.append(dict(strategy=f"D NQ ORB-retrace VP {cell}", source="dws-data/nas-orb-backtester", instrument="NQ", recoverable="mechanics yes; config/filter no", trades=f"{s['development']['trades']}/{s['validation1']['trades']}/{s['validation2']['trades']}",
                     dev=s["development"]["expectancy_usd"], val1=s["validation1"]["expectancy_usd"], val2=s["validation2"]["expectancy_usd"],
                     pf=f"{s['development']['profit_factor']:.2f}/{s['validation1']['profit_factor']:.2f}/{s['validation2']['profit_factor']:.2f}",
                     maxdd=f"{s['development']['max_drawdown_usd']:,.0f}/{s['validation1']['max_drawdown_usd']:,.0f}/{s['validation2']['max_drawdown_usd']:,.0f}",
                     sharpe=f"{s['development']['sharpe_daily_ann']:.2f}/{s['validation1']['sharpe_daily_ann']:.2f}/{s['validation2']['sharpe_daily_ann']:.2f}",
                     outlier=(f"OOS excl top1/3/5: {od['excl_top1']:,.0f}/{od['excl_top3']:,.0f}/{od['excl_top5']:,.0f} of {od['total']:,.0f}; top1/5/10%: {100*od['share_top1pct']:.0f}/{100*od['share_top5pct']:.0f}/{100*od['share_top10pct']:.0f}%" if od else ""),
                     cost=f"OOS net gross/base/stress/2x: {sum(dcells[cell]['gross'][p] for p in ('validation1','validation2')):,.0f}/{sum(s[p]['net_pnl'] for p in ('validation1','validation2')):,.0f}/{sum(dcells[cell]['stress'][p] for p in ('validation1','validation2')):,.0f}/{sum(dcells[cell]['stress2x'][p] for p in ('validation1','validation2')):,.0f}",
                     ci=f"[{lo:,.0f}, {hi:,.0f}]", verdict=v, oos_exp=float(pooled["net_usd"].mean()) if not pooled.is_empty() else float("nan")))
# D family composite for the bucket: equal-weight average daily P&L over the 15 cells (no selection)
comp = None
for cell, dc in dcells.items():
    ser = dg.daily_pnl_series(pl.concat([x for x in dc["leds"].values() if not x.is_empty()]), sum(days_all.values(), []))
    comp = ser if comp is None else comp.with_columns((pl.col("pnl") + ser["pnl"]).alias("pnl"))
comp = comp.with_columns((pl.col("pnl") / len(dcells)).alias("pnl"))
comp_oos = comp.filter(pl.col("trade_date").is_in(oos_days))
if float(comp_oos["pnl"].sum()) > 0:
    bucket_series["D_orb_retrace_family_avg"] = comp
# ---- F, G ----
for key, R, src, name in (("F", F, "Wen et al. 2020 / Gao et al. 2018", "F GC 5th-half-hour -> last-half-hour"), ("G", G, "Crabel 1990 (oxfordstrat replication)", "G GC Crabel Stretch ORB")):
    ledp = {ph: pl.read_parquet(OUT / f"{key}_GC" / f"trades_{ph}_base.parquet") for ph in ("development", "validation")}
    pooled = ledp["validation"]; st = pl.read_parquet(OUT / f"{key}_GC" / "trades_validation_stress.parquet")
    v = verdict(R["development"]["base"]["summary"], [R["validation"]["base"]["summary"]], pooled, float(st["net_usd"].sum()))
    od = dg.outlier_dependence(pooled); m, lo, hi = dg.bootstrap_mean_ci(pooled["net_usd"].to_numpy())
    s = {ph: R[ph]["base"]["summary"] for ph in ("development", "validation")}
    rows.append(dict(strategy=name, source=src, instrument="GC", recoverable="yes (ETF->futures mapping caveat)" if key == "F" else "yes", trades=f"{s['development']['trades']}/{s['validation']['trades']}/locked",
                     dev=s["development"]["expectancy_usd"], val1=s["validation"]["expectancy_usd"], val2=None, pf=f"{s['development']['profit_factor']:.2f}/{s['validation']['profit_factor']:.2f}",
                     maxdd=f"{s['development']['max_drawdown_usd']:,.0f}/{s['validation']['max_drawdown_usd']:,.0f}", sharpe=f"{s['development']['sharpe_daily_ann']:.2f}/{s['validation']['sharpe_daily_ann']:.2f}",
                     outlier=f"val excl top1/3/5: {od['excl_top1']:,.0f}/{od['excl_top3']:,.0f}/{od['excl_top5']:,.0f} of {od['total']:,.0f}; top1/5/10%: {100*od['share_top1pct']:.0f}/{100*od['share_top5pct']:.0f}/{100*od['share_top10pct']:.0f}%",
                     cost=f"val net gross/base/stress/2x: {R['validation']['gross']['summary']['net_pnl']:,.0f}/{R['validation']['base']['summary']['net_pnl']:,.0f}/{R['validation']['stress']['summary']['net_pnl']:,.0f}/{R['validation']['stress2x']['summary']['net_pnl']:,.0f}",
                     ci=f"[{lo:,.0f}, {hi:,.0f}]", verdict=v, oos_exp=float(pooled["net_usd"].mean())))
for name, src, ins in (("B Early-Bird intraday trend", "Turc/Gava/McNeal 2021", "NQ"), ("C S/R first-touch rejection", "unidentified repository", "NQ"), ("E opening-gap reversal", "Fung/Mok/Lam 2000; Grant/Wolf/Yu 2005", "NQ"), ("H GC mean reversion", "no exact public spec", "GC")):
    rows.append(dict(strategy=name, source=src, instrument=ins, recoverable="SPEC_NOT_RECOVERABLE", trades="", dev=None, val1=None, val2=None, pf="", maxdd="", sharpe="", outlier="", cost="", ci="", verdict="NOT TESTED", oos_exp=float("-inf")))
rows.sort(key=lambda r: -(r["oos_exp"] if r["oos_exp"] == r["oos_exp"] else -1e9))
L = ["# PHASE 4 — master table (BASE cost unless stated; expectancy = net $/trade on 1 contract; dev/val1/val2)", "",
     "| # | strategy | source | instr | rule recoverable | trades | dev exp $ | val1 exp $ | val2 exp $ | PF | max DD $ | Sharpe | outlier dependence | cost robustness | pooled-OOS mean [95% CI] | verdict |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for i, r in enumerate(rows, 1):
    L.append(f"| {i} | {r['strategy']} | {r['source']} | {r['instrument']} | {r['recoverable']} | {r['trades']} | {f(r['dev'],1)} | {f(r['val1'],1)} | {f(r['val2'],1)} | {r['pf']} | {r['maxdd']} | {r['sharpe']} | {r['outlier']} | {r['cost']} | {r['ci']} | **{r['verdict']}** |")
# D faithful vs corrected
L += ["", "## D — repository-faithful (touch fills, zero cost) vs corrected (through fills, base cost), expR / n", "| cell | dev faithful | dev corrected | val1 faithful | val1 corrected | val2 faithful | val2 corrected |", "|---|---|---|---|---|---|---|"]
for cell, dc in dcells.items():
    L.append(f"| {cell} | " + " | ".join(f"{f(dc['fa'][ph]['avg_r'],3)} / {dc['fa'][ph]['trades']} | {f(dc['s'][ph]['avg_r'],3)} / {dc['s'][ph]['trades']}" for ph in NQ_PHASES) + " |")
# bucket
if len(bucket_series) >= 2:
    ba = dg.bucket_analysis({k: v.filter(pl.col("trade_date").is_in(oos_days)) for k, v in bucket_series.items()})
    ba_all = dg.bucket_analysis(bucket_series)
    L += ["", "## Equal-risk bucket (strategies profitable after BASE cost; D enters as the equal-weight average of its 15 cells — no cell selected)", "",
          f"Members: {ba['names']}. Out-of-sample (2024 + 2025-2026H1) daily corr = {np.round(ba['daily_corr'],2).tolist()}, monthly corr = {np.round(ba['monthly_corr'],2).tolist()}, pairwise both-lose share = {ba['pairwise_both_lose']}, all-lose share = {ba['all_lose_share']:.3f}, equal-risk weights = {ba['equal_risk_weights']}, portfolio (weights sum to 1) max DD ${ba['portfolio_max_dd_usd_weighted']:,.0f}, Sharpe {ba['portfolio_sharpe']:.2f}, total ${ba['portfolio_total_weighted']:,.0f} over {ba['n_days']} days.",
          f"Full sample (dev+OOS): daily corr = {np.round(ba_all['daily_corr'],2).tolist()}, monthly corr = {np.round(ba_all['monthly_corr'],2).tolist()}, portfolio Sharpe {ba_all['portfolio_sharpe']:.2f}, max DD ${ba_all['portfolio_max_dd_usd_weighted']:,.0f}."]
    json.dump({"oos": ba, "all": ba_all}, open(OUT / "bucket_analysis.json", "w"), indent=1, default=str)
# D per-cell corr with A (OOS)
if "A_noise_long" in bucket_series:
    a = bucket_series["A_noise_long"].filter(pl.col("trade_date").is_in(oos_days))["pnl"].to_numpy()
    cors = {}
    for cell, dc in dcells.items():
        ser = dg.daily_pnl_series(pl.concat([x for x in dc["leds"].values() if not x.is_empty()]), sum(days_all.values(), [])).filter(pl.col("trade_date").is_in(oos_days))["pnl"].to_numpy()
        cors[cell] = float(np.corrcoef(a, ser)[0, 1])
    L += ["", "D cells vs A, OOS daily P&L correlation: " + ", ".join(f"{k} {v:.2f}" for k, v in cors.items())]
(DOCS_DIR / "phase4").mkdir(exist_ok=True)
(DOCS_DIR / "phase4" / "MASTER_TABLE.md").write_text("\n".join(L))
json.dump(dict(rows=rows, details=details), open(OUT / "master.json", "w"), indent=1, default=str)
print("\n".join(L))
