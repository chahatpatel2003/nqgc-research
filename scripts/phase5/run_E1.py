"""E1 — naive baselines (M0) with the mandatory reporting block, every target, DEVELOPMENT ONLY. No fitting."""
import json, sys
sys.path.insert(0, "src")
import numpy as np, polars as pl
from nqgc.bias.daily import TARGETS
from nqgc.bias.features import build_features
from nqgc.bias.splits import OUT
from nqgc.bias.registry import record, file_hash
from nqgc.bias.report import block, full_report, table, _pct

E0, E1 = OUT / "E0", OUT / "E1"; E1.mkdir(parents=True, exist_ok=True)
daily = pl.read_parquet(E0 / "daily_development.parquet")
f = build_features(daily)
df = f.join(daily.select(["date"] + TARGETS), on="date", how="left").filter(pl.col("eligible"))
sgn = lambda c: pl.col(c).fill_nan(None).sign().fill_null(0).cast(pl.Float64)
RULES = {
    "always_BUY": pl.lit(1.0), "always_SELL": pl.lit(-1.0),
    "prev_RTH_sign": sgn("f_prev_rth_ret_r"), "anti_prev_RTH_sign": -sgn("f_prev_rth_ret_r"),
    "prev_AM_sign": sgn("f_prev_am_ret_r"), "anti_prev_AM_sign": -sgn("f_prev_am_ret_r"),
    "overnight_sign": sgn("f_on_ret_r"), "anti_overnight_sign": -sgn("f_on_ret_r"),
    "last30_sign": sgn("f_last30_ret_r"), "anti_last30_sign": -sgn("f_last30_ret_r"),
    "gap_sign": sgn("f_gap_close_r"), "anti_gap_sign(gap_fade)": -sgn("f_gap_close_r"),
    "shock0830_sign": sgn("f_shock_0830_r"), "anti_shock0830_sign": -sgn("f_shock_0830_r"),
    "am_drift20_sign": sgn("f_am_drift_20"), "ret5d_sign": sgn("f_ret_5d_s"), "anti_ret5d_sign": -sgn("f_ret_5d_s"),
}
df = df.with_columns([v.alias("pred_" + k) for k, v in RULES.items()])
lines = ["# E1 — naive baselines (development 2021–2023, eligible days, no fitting)", "",
         "Every rule predicts on 100% of days (sign = 0 → NO BIAS on that day). Accuracy is judged against always-BUY on the same predicted days.", ""]
res = {}
# matrix: rule x target accuracy (n)
lines += ["## Accuracy by rule × target (correct/decisive, lift vs always-BUY on the same days)", "",
          "| Rule | " + " | ".join(t[2:] for t in TARGETS) + " |", "|" + "---|" * (1 + len(TARGETS))]
for k in RULES:
    cells = []
    for t in TARGETS:
        b = block(df["pred_" + k].to_numpy(), df[t].to_numpy(), df["y_T1"].to_numpy())
        res[f"{k}|{t}"] = b
        cells.append(f"{b['correct']}/{b['correct'] + b['wrong']} {_pct(b['accuracy'])} ({'+' if b['lift_vs_always_buy'] >= 0 else ''}{100 * b['lift_vs_always_buy']:.1f})")
    lines.append(f"| {k} | " + " | ".join(cells) + " |")
lines += ["", "## Full blocks on T1 (net sign), per year and per side", ""]
for k in RULES:
    txt, r = full_report(df, "pred_" + k, "y_T1", f"E1 {k} — target T1 — development")
    lines += ["```", txt, "```", ""]
    res[f"{k}|T1|full"] = r
(E1 / "REPORT.md").write_text("\n".join(lines))
json.dump(res, open(E1 / "blocks.json", "w"), indent=1, default=float)
record("E1", {"phase": "development", "eligible": df.height, "rules": list(RULES), "daily_hash": file_hash(E0 / "daily_development.parquet"),
              "summary": {k: {t: {"acc": res[f'{k}|{t}']["accuracy"], "n": res[f'{k}|{t}']["correct"] + res[f'{k}|{t}']["wrong"], "lift": res[f'{k}|{t}']["lift_vs_always_buy"]} for t in TARGETS} for k in RULES}})
print("\n".join(lines[:len(RULES) + 8]))
