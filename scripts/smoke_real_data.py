"""End-to-end smoke test on REAL data inside the development window (mechanics only, no strategy claims)."""
import datetime as dt, sys, time
sys.path.insert(0, "src")
import numpy as np, polars as pl
from nqgc.guard import Access
from nqgc.data import load_nq_trades, load_gc_bars
from nqgc.bars import bars_from_trades, gc_1m_to_bars, resample_bars, check_bar_semantics
from nqgc import indicators as I
from nqgc.engine import Backtester, EngineConfig, TickResolver
from nqgc.execution import CostModel, Order
from nqgc.risk import PropFirmRules
from nqgc.leakage import engine_truncation_test, fills_after_signals, truncation_test

t0 = time.time()
acc = Access("development", "NQ", purpose="smoke")
tr = load_nq_trades(acc, "2023-03-15", "2023-03-16", symbols=["NQM3"])
print("NQ trades loaded", tr.height, tr["ts_event"].min(), tr["ts_event"].max(), "secs", round(time.time() - t0, 1))
assert (tr["trade_date"].unique().sort().to_list()) == [dt.date(2023, 3, 15), dt.date(2023, 3, 16)]
assert ((tr["price"] * 4) % 1 == 0).all(), "off-tick outright print"
b = bars_from_trades(tr, 60, "NQ")
b = b.with_columns(pl.lit(True).alias("tradeable"))
check_bar_semantics(b)
print("bars", b.height, "sessions", b.group_by("session").len().sort("session").to_dicts())
ind = {"atr14": I.atr(b, 14), "vwap": I.session_vwap(b)}
assert truncation_test(lambda x: I.atr(x, 14), b) == []


class RthOpenBracket:
    name = "smoke_rth_bracket"
    def on_bar(self, ctx):
        ts = ctx.last("ts_open").astimezone(dt.timezone(dt.timedelta(hours=-5)))
        if ctx.position is None and ts.hour == 9 and ts.minute == 0:
            return [Order(side=1, qty=1, stop_offset=20, target_offset=20)]


cost = CostModel.from_config("NQ")
rules = PropFirmRules.from_yaml()
res = TickResolver(tr)
run = lambda bb, r=res: Backtester(bb, RthOpenBracket(), cost, rules, EngineConfig(), ind if bb.height == b.height else None, r).run()
trades = run(b)
print(trades.select("signal_ts", "entry_ts", "exit_ts", "entry_px", "exit_px", "exit_reason", "gross_usd", "net_usd", "ambiguous", "tick_resolved"))
assert fills_after_signals(trades).is_empty()
ok, msg = engine_truncation_test(lambda bb: Backtester(bb, RthOpenBracket(), cost, rules, EngineConfig(), None, res).run(), b, b.height // 2)
print("engine truncation on real data:", ok, msg)
# same run without resolver -> conservative path
t2 = Backtester(b, RthOpenBracket(), cost, rules, EngineConfig(), None, None).run()
print("without resolver:", t2.select("exit_reason", "net_usd", "ambiguous").to_dicts())

g = load_gc_bars(Access("development", "GC", purpose="smoke"), "2023-03-13", "2023-03-17")
gb = gc_1m_to_bars(g, "GC").with_columns(pl.lit(True).alias("tradeable"))
check_bar_semantics(gb)
g5 = resample_bars(gb, 300, "GC").with_columns(pl.lit(True).alias("tradeable"))
check_bar_semantics(g5)
print("GC 1m bars", gb.height, "5m bars", g5.height, g5.select("ts_open", "ts_close", "open", "high", "low", "close", "volume", "session").head(3))


class GcOpen:
    name = "smoke_gc"
    def on_bar(self, ctx):
        ts = ctx.last("ts_open").astimezone(dt.timezone(dt.timedelta(hours=-5)))
        if ctx.position is None and ts.hour == 8 and ts.minute == 0:
            return [Order(side=-1, qty=1, stop_offset=5, target_offset=5)]


gt = Backtester(g5, GcOpen(), CostModel.from_config("GC"), rules, EngineConfig(instrument="GC")).run()
print(gt.select("trade_date", "entry_ts", "exit_ts", "entry_px", "exit_px", "exit_reason", "net_usd", "ambiguous"))
print("SMOKE OK", round(time.time() - t0, 1), "s")
