"""E2 — feature bank v1 (development), feature documentation, matrix hash, leakage audits (pytest) and label-correlation scan."""
import json, subprocess, sys
sys.path.insert(0, "src")
import numpy as np, polars as pl
from nqgc.bias.daily import TARGETS
from nqgc.bias.features import build_features, feature_names, assert_no_targets
from nqgc.bias.splits import OUT
from nqgc.bias.registry import record, file_hash

E0, E2 = OUT / "E0", OUT / "E2"; E2.mkdir(parents=True, exist_ok=True)
daily = pl.read_parquet(E0 / "daily_development.parquet")
f = build_features(daily)
assert_no_targets(f)
f.write_parquet(E2 / "features_development.parquet")
names = feature_names(f)
h = file_hash(E2 / "features_development.parquet")
e = f.filter(pl.col("eligible"))
# coverage / missingness per feature on eligible days
miss = {c: float(e[c].fill_nan(None).null_count() / e.height) for c in names}
# label-correlation scan (audit): |corr| with same-day labels on eligible development days
tg = pl.read_parquet(E0 / "targets_development.parquet").select(["date"] + TARGETS)
ef = e.join(tg, on="date", how="left")
scan = []
for c in names:
    x = ef[c].fill_nan(None).to_numpy().astype(float)
    row = {"feature": c, "missing": miss[c]}
    for t in ("y_T1", "y_T3", "y_T5"):
        y = ef[t].to_numpy().astype(float)
        m = ~np.isnan(x) & ~np.isnan(y) & (y != 0)
        row[t] = float(np.corrcoef(x[m], y[m])[0, 1]) if m.sum() > 50 and np.nanstd(x[m]) > 0 else np.nan
    row["max_abs"] = float(np.nanmax(np.abs([row["y_T1"], row["y_T3"], row["y_T5"]])))
    scan.append(row)
scan_df = pl.DataFrame(scan).sort("max_abs", descending=True)
scan_df.write_parquet(E2 / "label_corr_scan.parquet")
flagged = scan_df.filter(pl.col("max_abs") > 0.30)
# leakage tests
proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "tests/test_bias_leakage.py", "-p", "no:cacheprovider"], capture_output=True, text=True)
passed = proc.returncode == 0
(E2 / "pytest_output.txt").write_text(proc.stdout + proc.stderr)
lines = ["# E2 — feature bank v1 (development), leakage audits", "",
         f"Feature matrix: `runs/phase5/E2/features_development.parquet` sha256[:16] = `{h}`; rows {f.height} (RTH sessions), eligible {e.height}; features {len(names)}.", "",
         f"Leakage test suite (`tests/test_bias_leakage.py`): **{'ALL PASSED' if passed else 'FAILED'}**", "", "```", proc.stdout.strip()[-3000:], "```", "",
         "## Label-correlation audit (|corr| with same-day T1/T3/T5 on eligible development days; flag threshold 0.30)", "",
         f"Flagged features: {flagged.height}" + ("" if flagged.is_empty() else " → " + ", ".join(flagged['feature'].to_list())), "",
         "Largest 15 |corr| (audit view only; NOT a selection step — the walk-forward screen is E3):", "",
         "| feature | corr T1 | corr T3 | corr T5 | missing |", "|---|---|---|---|---|"]
for r in scan_df.head(15).to_dicts():
    lines.append(f"| {r['feature']} | {r['y_T1']:+.3f} | {r['y_T3']:+.3f} | {r['y_T5']:+.3f} | {100 * r['missing']:.1f}% |")
lines += ["", f"Features with > 20% missing on eligible days: " + (", ".join(f"{c} ({100 * miss[c]:.0f}%)" for c in names if miss[c] > 0.2) or "none"), ""]
(E2 / "REPORT.md").write_text("\n".join(lines))
record("E2", {"phase": "development", "features": len(names), "rows": f.height, "eligible": e.height, "matrix_hash": h,
              "daily_hash": file_hash(E0 / "daily_development.parquet"), "tests_passed": passed, "flagged_features": flagged["feature"].to_list(),
              "max_abs_corr": float(scan_df["max_abs"].max())})
print("\n".join(lines))
