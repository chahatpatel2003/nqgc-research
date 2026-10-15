"""Build the causal R4 level/tap/fire layers for the original parameters and the diagnostic neighbourhoods.
Variants (all share the same session bars; each is an independent engine instance):
  base           : frozen parameters (scales 0.15/0.35/0.75, hyst 8 ticks, rearm 900 s) — the ONLY one used for the baseline verdict
  nodedup        : base without the universe dedup rule (robustness of the dedup choice)
  thr_x0.8 / x1.2: pivot thresholds scaled (0.12/0.28/0.60, 0.18/0.42/0.90)
  hyst_x0.5/x1.5 : effective re-arm distance max(8 ticks, hw) scaled by 0.5 / 1.5
  rearm_600/1200 : re-arm duration
Displacement grid 8..12 is emitted inside every variant. Output: runs/phase3/levels/<variant>_{zones,taps,fires}.parquet
Phases: development + validation1 + validation2 (all unlocked); the locked window is never read."""
import datetime as dt, json, sys, time
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2"); sys.path.insert(0, "scripts/phase3")
import polars as pl
from common import nq_days, freeze_or_load, OUT
from r4_driver import run_sessions
from nqgc.levels_r4 import R4Engine, DEFAULT_PARAMS
from nqgc.paths import RUNS_DIR, assert_writable_target

SPEC_ID = freeze_or_load("R4_causal", "3.0", "NQ", 1, open("src/nqgc/levels_r4.py").read().split('"""')[1],
                         {k: (list(v) if isinstance(v, tuple) else v) for k, v in DEFAULT_PARAMS.items()}, "H-A3",
                         notes="causal rebuild; zone available only after the confirmation bar completes; causal roll spread; causal first-in-time dedup")
VARIANTS = {
    "base": {},
    "nodedup": {"dedup": False},
    "thr_x0.8": {"scales": (0.12, 0.28, 0.60)},
    "thr_x1.2": {"scales": (0.18, 0.42, 0.90)},
    "hyst_x0.5": {"hyst_mult": 0.5},     # (4-tick / 12-tick floors change nothing: the half-width dominates max(floor, hw))
    "hyst_x1.5": {"hyst_mult": 1.5},
    "rearm_600": {"rearm_s": 600},
    "rearm_1200": {"rearm_s": 1200},
}
if __name__ == "__main__":
    dates = []
    for ph in ("development", "validation1", "validation2"):
        dates += [x["date"] for x in nq_days(ph, SPEC_ID, "phase3 causal R4 level build", exclude_early_close=False)]
    dates = sorted(set(dates))
    engines = {k: R4Engine(v) for k, v in VARIANTS.items()}
    t0 = time.time()
    run_sessions(dates, engines, verbose=True)
    out = assert_writable_target(RUNS_DIR / "phase3" / "levels"); out.mkdir(parents=True, exist_ok=True)
    for k, e in engines.items():
        z, t, f = e.frames()
        z.write_parquet(out / f"{k}_zones.parquet"); t.write_parquet(out / f"{k}_taps.parquet"); f.write_parquet(out / f"{k}_fires.parquet")
        print(k, "zones", z.height, "taps", t.height, "fires", f.height, flush=True)
    json.dump(dict(spec_id=SPEC_ID, variants={k: {kk: (list(vv) if isinstance(vv, tuple) else vv) for kk, vv in v.items()} for k, v in VARIANTS.items()}, n_sessions=len(dates), secs=time.time() - t0),
              open(out / "build_meta.json", "w"), indent=1, default=str)
    print("DONE", round(time.time() - t0), "s")
