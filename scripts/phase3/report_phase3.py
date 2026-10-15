import json, math, sys
sys.path.insert(0, "src")
from nqgc.paths import RUNS_DIR, DOCS_DIR
R = json.loads((RUNS_DIR / "phase3" / "results.json").read_text())
OV = json.loads((RUNS_DIR / "phase3" / "old_vs_causal.json").read_text()) if (RUNS_DIR / "phase3" / "old_vs_causal.json").exists() else {}
def f(v, nd=3):
    return "n/a" if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))) else (f"{v:,.{nd}f}" if isinstance(v, float) else str(v))
WIN = ["2021", "2022", "2023", "2024", "2025", "2026H1", "development", "validation1", "validation2", "full"]
L = ["# PHASE 3 — causal R4 rebuild: results tables", ""]
L += ["## Cost tiers (NQ, 1 contract, round trip)", "| tier | fees $ | slippage ticks/side | total $ RT | total pts RT |", "|---|---|---|---|---|"]
for t, c in R["cost_tiers"].items():
    L.append(f"| {t} | {c['fees_usd_rt']:.2f} | {c['slip_ticks_side']} | {c['total_usd_rt']:.2f} | {c['total_pts_rt']:.2f} |")
L.append("")
for cell, tiers in R["cells"].items():
    L.append(f"## {cell}")
    for tier in ("zero", "base", "stress", "stress2x"):
        per = tiers[tier]
        L.append(f"### {cell} — {tier} cost")
        L.append("| window | trades | WR | expR | 95% CI | PF | gross R | net R | net $ | maxDD R | avg win $ | avg loss $ | max win $ | max loss $ | Sharpe | Sortino | hold min | worst streak | %m/%q/%y | MC DD R p50/p90/p95/p99 |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for w in WIN:
            m = per[w]
            if m.get("trades", 0) == 0:
                L.append(f"| {w} | 0 | | | | | | | | | | | | | | | | | | |"); continue
            mc = m.get("mc_dd_R") or {}
            L.append(f"| {w} | {m['trades']} | {f(m['win_rate'],3)} | {f(m['expR'],3)} | [{f(m['expR_ci'][0],3)}, {f(m['expR_ci'][1],3)}] | {f(m['pf'],2)} | {f(m['gross_R'],1)} | {f(m['net_R'],1)} | {f(m['net_usd'],0)} | {f(m['maxdd_R'],1)} | {f(m['avg_win'],0)} | {f(m['avg_loss'],0)} | {f(m['max_win'],0)} | {f(m['max_loss'],0)} | {f(m['sharpe'],2)} | {f(m['sortino'],2)} | {f(m['hold_min'],1)} | {m['streak_loss']} | {f(100*m['pct_months'],0)}/{f(100*m['pct_quarters'],0)}/{f(100*m['pct_years'],0)} | {f(mc.get('p50'),1)}/{f(mc.get('p90'),1)}/{f(mc.get('p95'),1)}/{f(mc.get('p99'),1)} |")
        L.append("")
L.append("## Parameter neighbourhoods (BASE cost; expR / PF / n per phase) — diagnostics only, nothing selected")
for cell, kinds in R["neighbourhood"].items():
    for kind, vals in kinds.items():
        L.append(f"### {cell} — {kind}")
        L.append("| value | dev expR / PF / n | val-1 | val-2 | full |"); L.append("|---|---|---|---|---|")
        keys = sorted(vals, key=lambda x: (float(x) if x.replace('.', '', 1).isdigit() else 1e9, x))
        for v in keys:
            m = vals[v]
            L.append(f"| {v} | " + " | ".join(f"{f(m[w]['expR'],3)} / {f(m[w]['pf'],2)} / {m[w]['trades']}" for w in ("development", "validation1", "validation2", "full")) + " |")
        L.append("")
if OV:
    L.append("## Old (leaked) vs causal fire universe")
    L.append(f"Old fires (all taps) {OV['old_fires_all_taps']}, of which tap<=3 {OV['old_fires_tap3']}; tap<=3 fires with the tap inside the confirmation minute (leaked): {OV['old_tap3_leaked_age_lt_1min']} ({100*OV['old_tap3_leak_share']:.1f}%). Causal fires (displacement 10): all taps {OV['new_fires_all_taps']}, tap<=3 {OV['new_fires_tap3']}; minimum zone age at tap {OV['new_min_age_min']:.2f} min.")
    L.append("| year | old tap<=3 | old leaked | causal tap<=3 | same tap second | same fire second |"); L.append("|---|---|---|---|---|---|")
    for y, v in OV["per_year"].items():
        L.append(f"| {y} | {v['old']} | {v['old_leaked']} | {v['new']} | {v['matched_same_tap_second']} | {v['matched_same_fire']} |")
    L.append("")
    L.append("### Old fires with age >= 1 min, split by presence in the causal universe (old 1-s evaluator, P14 cell, 1.0 pt cost)")
    L.append("| subset | fires | trades | expR | PF | WR |"); L.append("|---|---|---|---|---|---|")
    for k, v in OV["old_age1_split_P14_old_evaluator"].items():
        L.append(f"| {k} | {v.get('fires')} | {v.get('n')} | {v.get('expR')} | {v.get('pf')} | {v.get('wr')} |")
    L.append("")
    L.append("| year | in causal universe expR (n) | NOT in causal universe expR (n) |"); L.append("|---|---|---|")
    for y, v in OV["old_age1_split_by_year"].items():
        L.append(f"| {y} | {f(v['in_causal'],3)} ({v['n_in']}) | {f(v['not_in_causal'],3)} ({v['n_not']}) |")
    L.append("")
    L.append("### P14 cell: old evaluator (leaked) -> Phase-2 replay -> Phase-2 age>=1 replay -> Phase-3 causal rebuild (base cost)")
    L.append("| phase | old leaked n / expR / PF | P2 replay n / expR / PF | P2 age>=1 n / expR / PF | P3 causal n / expR / PF |"); L.append("|---|---|---|---|---|")
    for ph, c in OV["comparison_P14"].items():
        o = c["old_evaluator_leaked"]; r = c["phase2_replay_base"]; a = c["phase2_replay_age_filter"]; n = c["phase3_causal_base"]
        L.append(f"| {ph} | {o['n']} / {f(o['expR'],3)} / {f(o['pf'],2)} | {r['n']} / {f(r['expR'],3)} / {f(r['pf'],2)} | {a['n'] if a else ''} / {f(a['expR'],3) if a else ''} / {f(a['pf'],2) if a else ''} | {n['trades']} / {f(n['expR'],3)} / {f(n['pf'],2)} |")
(DOCS_DIR / "phase3").mkdir(exist_ok=True)
(DOCS_DIR / "phase3" / "PHASE3_TABLES.md").write_text("\n".join(L))
print("\n".join(L[:60]))
