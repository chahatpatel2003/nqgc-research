"""Run one strategy file through the guarded pipeline and save a fully reproducible run.

  .venv/bin/python scripts/run_backtest.py strategies/_template.py --phase development [--start .. --end ..]
  .venv/bin/python scripts/run_backtest.py strategies/x.py --phase validation --spec-id abc123
  .venv/bin/python scripts/run_backtest.py strategies/x.py --phase holdout --spec-id abc123 --unlock "<phrase>" --purpose "..."
"""
import argparse, datetime as dt, importlib.util, json, sys, time
from pathlib import Path
sys.path.insert(0, "src")
import numpy as np, polars as pl, yaml
from nqgc.guard import Access
from nqgc.data import load_nq_trades, load_nq_dbn, load_gc_bars
from nqgc.bars import bars_from_trades, gc_1m_to_bars, resample_bars, check_bar_semantics
from nqgc.engine import Backtester, EngineConfig, TickResolver
from nqgc.execution import CostModel
from nqgc.risk import PropFirmRules
from nqgc.stats import full_report
from nqgc.protocol import RunManifest, new_run_id, load_spec, verify_spec_matches_code
from nqgc.leakage import fills_after_signals
from nqgc.paths import CONFIG_DIR, CACHE_DIR
from nqgc.calendar import load_observed_calendar

ap = argparse.ArgumentParser()
ap.add_argument("strategy_file")
ap.add_argument("--phase", required=True, choices=["development", "validation", "holdout"])
ap.add_argument("--start"); ap.add_argument("--end")
ap.add_argument("--spec-id"); ap.add_argument("--unlock"); ap.add_argument("--purpose", default="")
ap.add_argument("--costs", default=str(CONFIG_DIR / "costs_default.yaml"))
ap.add_argument("--propfirm", default=str(CONFIG_DIR / "propfirm_default.yaml"))
ap.add_argument("--engine", default=str(CONFIG_DIR / "engine_default.yaml"))
ap.add_argument("--no-ticks", action="store_true", help="disable tick resolution even when trades exist")
a = ap.parse_args()

spec = importlib.util.spec_from_file_location("strat", a.strategy_file); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
instrument, tf = mod.INSTRUMENT, mod.TIMEFRAME_S
if a.phase != "development":
    sp = load_spec(a.spec_id); verify_spec_matches_code(sp, Path(a.strategy_file))
    assert sp.instrument == instrument and sp.timeframe_s == tf, "spec/strategy mismatch"
acc = Access(a.phase, instrument, spec_id=a.spec_id, unlock=a.unlock, purpose=a.purpose or f"run {Path(a.strategy_file).name}")
start, end = acc.clip(a.start or "1900-01-01", a.end or "2100-01-01")
eng = yaml.safe_load(open(a.engine)); costs_cfg = yaml.safe_load(open(a.costs)); pf_cfg = yaml.safe_load(open(a.propfirm))
cost = CostModel.from_config(instrument, costs_path=a.costs); rules = PropFirmRules.from_yaml(a.propfirm)
cal = load_observed_calendar(instrument)
t0 = time.time()
root = yaml.safe_load(open(CONFIG_DIR / "instruments.yaml"))[instrument]["price_source_symbol_root"]
resolver = None
if root == "NQ":
    fm = pl.read_parquet(CACHE_DIR / "nq_front_map.parquet")
    fm = fm.filter((pl.col("trade_date") >= start) & (pl.col("trade_date") <= end) & ~pl.col("bootstrap"))
    frames, tick_frames = [], []
    for row in fm.iter_rows(named=True):
        d, sym = row["trade_date"], row["front"]
        loader = load_nq_dbn if d >= dt.date(2026, 6, 18) else load_nq_trades
        tr = loader(acc, d, d) if loader is load_nq_dbn else load_nq_trades(acc, d, d, symbols=[sym])
        tr = tr.filter(pl.col("symbol") == sym)
        if tr.is_empty():
            continue
        b = bars_from_trades(tr, tf, instrument).with_columns(pl.lit(not row["roll_day"]).alias("tradeable"))
        frames.append(b)
        if not a.no_ticks:
            tick_frames.append(tr.select("ts_event", "symbol", "price", "size", "sequence"))
    bars = pl.concat(frames)
    partial = {p["trade_date"] for p in cal.get("partial_sessions", [])} | {h["trade_date"] for h in cal.get("data_holes", [])}
    bars = bars.with_columns((pl.col("tradeable") & ~pl.col("trade_date").cast(pl.Utf8).is_in(list(partial))).alias("tradeable"))
    if tick_frames:
        resolver = TickResolver(pl.concat(tick_frames))
else:
    g = load_gc_bars(acc, start, end)
    bars = gc_1m_to_bars(g, instrument)
    if tf != 60:
        bars = resample_bars(bars, tf, instrument)
    bad = set(cal.get("roll_switch_dates", [])) | set(cal.get("thin_last_days", [])) | {h["trade_date"] for h in cal.get("data_holes", [])}
    bars = bars.with_columns((~pl.col("trade_date").cast(pl.Utf8).is_in(list(bad))).alias("tradeable"))
check_bar_semantics(bars)
ind = mod.build_indicators(bars)
ecfg = EngineConfig(instrument=instrument, execution_lag_bars=eng["execution_lag_bars"], max_trades_per_day=eng.get("max_trades_per_day"), sizing=eng["sizing"])
bt = Backtester(bars, mod.Strategy(), cost, rules, ecfg, ind, resolver)
trades = bt.run()
assert fills_after_signals(trades).is_empty(), "LEAK: fill before signal"
rep = full_report(trades, rules.account_size, n_trade_dates=bars["trade_date"].n_unique())
run_id = new_run_id(f"{mod.NAME}_v{mod.VERSION}_{instrument}_{a.phase}")
man = RunManifest(run_id, a.phase, instrument, a.spec_id, eng["seed"], eng, costs_cfg, pf_cfg)
out = man.save(trades, rep)
print(json.dumps(rep["summary"], indent=1, default=str))
print("saved", out, "elapsed", round(time.time() - t0, 1), "s", "bars", bars.height, "tradeable", int(bars["tradeable"].sum()))
