"""Old leaked fire stream vs causal rebuild: counts, leak share, overlap, and result comparison (P14 cell, base cost)."""
import datetime as dt, json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2"); sys.path.insert(0, "scripts/phase3")
import numpy as np, pandas as pd, polars as pl
from nqgc.paths import RUNS_DIR
OUT = RUNS_DIR / "phase3"; LEV = OUT / "levels"
old = pd.read_parquet("/Volumes/T9/nq data/nq_levels/daily/p14_fire.parquet", columns=["session", "zid", "tap_sec", "tap_ts", "fire_s", "tap_no", "age_min", "ck2_epx", "ck2_eidx", "ck2_up12.5", "ck2_dn30.0", "ck2_endpx"])
old["session"] = old["session"].astype(str); old = old[old.session <= "2026-06-17"]
o3 = old[old.tap_no <= 3]
new = pl.read_parquet(LEV / "base_fires.parquet").filter(pl.col("displacement") == 10.0).to_pandas(); new["session"] = new["session"].astype(str)
n3 = new[new.tap_no <= 3]
res = {"old_fires_all_taps": int(len(old)), "old_fires_tap3": int(len(o3)), "old_tap3_leaked_age_lt_1min": int((o3.age_min < 1).sum()), "old_tap3_leak_share": float((o3.age_min < 1).mean()),
       "new_fires_all_taps": int(len(new)), "new_fires_tap3": int(len(n3)), "new_min_age_min": float(n3.age_min.min())}
res["old_all_leaked_age_lt_1min"] = int((old.age_min < 1).sum())
res["per_year"] = {}
for y in range(2021, 2027):
    o = o3[o3.session.str[:4] == str(y)]; n = n3[n3.session.str[:4] == str(y)]
    mm = o.merge(n, on="tap_ts", suffixes=("_o", "_n"))
    res["per_year"][y] = dict(old=int(len(o)), old_leaked=int((o.age_min < 1).sum()), new=int(len(n)), matched_same_tap_second=int(len(mm)), matched_same_fire=int((mm.fire_s_o == mm.fire_s_n).sum()))
p2 = json.loads((RUNS_DIR / "phase2" / "A_R4" / "results.json").read_text())
p2c = json.loads((RUNS_DIR / "phase2" / "A_R4" / "causal_fix_results.json").read_text())
p3 = json.loads((OUT / "results.json").read_text())
cmp = {}
for ph in ("development", "validation1", "validation2"):
    o = p2["per_cell"]["P14_ck2_S12.5_T30"][ph]
    cmp[ph] = dict(old_evaluator_leaked=o["old"], phase2_replay_base=dict(n=o["new"]["base"]["summary"]["trades"], expR=o["new"]["base"]["summary"]["avg_r"], pf=o["new"]["base"]["summary"]["profit_factor"]),
                   phase2_replay_age_filter=p2c["P14_ck2_S12.5_T30"][ph]["new_base"] if isinstance(p2c["P14_ck2_S12.5_T30"][ph].get("new_base"), dict) else None,
                   phase3_causal_base=p3["cells"]["P14_ck2_S12.5_T30"]["base"][ph])
res["comparison_P14"] = cmp
(OUT / "old_vs_causal.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps({k: v for k, v in res.items() if k != "comparison_P14"}, indent=1))
for ph, c in cmp.items():
    print(ph, "OLD(leaked):", {k: round(v, 3) if isinstance(v, float) else v for k, v in c["old_evaluator_leaked"].items() if k in ("n", "expR", "pf", "wr")}, "| P2 replay base:", c["phase2_replay_base"], "| P2 age>=1:", {k: c["phase2_replay_age_filter"][k] for k in ("n", "expR", "pf")} if c["phase2_replay_age_filter"] else None, "| P3 causal:", {k: c["phase3_causal_base"][k] for k in ("trades", "expR", "pf")})

# ---- where did the Phase-2 'age>=1' residual come from? split OLD tap<=3 fires (age>=1) by presence in the causal universe ----
sys.path.insert(0, "scripts/phase2")
from strat_A_r4 import old_engine, old_summary
o_ok = o3[o3.age_min >= 1].copy()
in_new = o_ok.tap_ts.isin(n3.tap_ts)
split = {}
for lab, sub in (("old_age1_all", o_ok), ("old_age1_in_causal_universe", o_ok[in_new]), ("old_age1_NOT_in_causal_universe", o_ok[~in_new])):
    sub = sub[sub.session >= "2021-01-01"]
    s = old_summary(old_engine(sub, 2, 12.5, 30.0)) if len(sub) else {}
    split[lab] = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items() if k in ("n", "expR", "pf", "wr", "pts")}
    split[lab]["fires"] = int(len(sub))
res["old_age1_split_P14_old_evaluator"] = split
# per-year for the two halves
py = {}
for y in range(2021, 2027):
    a = o_ok[(o_ok.session.str[:4] == str(y)) & in_new]; b = o_ok[(o_ok.session.str[:4] == str(y)) & ~in_new]
    py[y] = {"in_causal": old_summary(old_engine(a, 2, 12.5, 30.0))["expR"] if len(a) > 20 else None, "n_in": int(len(a)),
             "not_in_causal": old_summary(old_engine(b, 2, 12.5, 30.0))["expR"] if len(b) > 20 else None, "n_not": int(len(b))}
res["old_age1_split_by_year"] = py
(OUT / "old_vs_causal.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps(split, indent=1)); print(json.dumps(py, indent=1))
