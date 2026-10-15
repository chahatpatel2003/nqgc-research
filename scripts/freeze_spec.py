"""Freeze a strategy specification BEFORE validation. Usage: scripts/freeze_spec.py strategies/x.py --hypothesis H-001"""
import argparse, importlib.util, sys
from pathlib import Path
sys.path.insert(0, "src")
import yaml
from nqgc.protocol import StrategySpec, freeze
from nqgc.paths import CONFIG_DIR
ap = argparse.ArgumentParser(); ap.add_argument("strategy_file"); ap.add_argument("--hypothesis", default=""); ap.add_argument("--notes", default="")
a = ap.parse_args()
spec = importlib.util.spec_from_file_location("strat", a.strategy_file); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
splits = yaml.safe_load(open(CONFIG_DIR / "splits.yaml"))
s = StrategySpec(mod.NAME, mod.VERSION, mod.INSTRUMENT, mod.TIMEFRAME_S, mod.RULES, dict(mod.PARAMS), splits[mod.INSTRUMENT], a.hypothesis, notes=a.notes)
p = freeze(s, Path(a.strategy_file))
print("frozen:", p, "spec_id:", s.spec_id, "code_hash:", s.code_hash)
