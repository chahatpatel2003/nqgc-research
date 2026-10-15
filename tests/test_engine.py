import datetime as dt
import numpy as np
import polars as pl
import pytest
from nqgc.engine import Backtester, EngineConfig, TickResolver, LeakageError
from nqgc.execution import CostModel, InstrumentSpec, Order, OrderType
from nqgc.risk import PropFirmRules
from nqgc.leakage import fills_after_signals, engine_truncation_test
from conftest import make_bars

SPEC = InstrumentSpec("NQ", 0.25, 20.0, 5.0)


def cost(**kw):
    return CostModel(SPEC, fee_per_side=2.0, slippage_ticks={"market": 1, "stop": 1, "limit": 0}, **kw)


def rules(**kw):
    d = dict(account_size=50000, daily_loss_limit=None, trailing_drawdown=None, flatten_by=None, max_contracts={"NQ": 10})
    d.update(kw)
    return PropFirmRules(**d)


class OneShot:
    """Emit one order at a chosen bar index."""
    name = "oneshot"
    def __init__(self, at, order):
        self.at, self.order, self.done = at, order, False
    def on_bar(self, ctx):
        if ctx.i == self.at and not self.done:
            self.done = True
            return [self.order]


def test_market_fills_next_bar_open_plus_slippage(bars3):
    b = bars3
    strat = OneShot(10, Order(side=1, qty=1, stop_offset=20, target_offset=20))
    bt = Backtester(b, strat, cost(), rules(), EngineConfig())
    tr = bt.run()
    assert tr.height == 1
    t = tr.row(0, named=True)
    assert t["signal_ts"] == b["ts_close"][10]
    assert t["entry_ts"] == b["ts_open"][11] and t["entry_ts"] >= t["signal_ts"] and t["entry_idx"] == 11
    assert t["entry_px"] == b["open"][11] + 0.25
    assert fills_after_signals(tr).is_empty()


def test_both_touched_without_resolver_is_stop_and_ambiguous(bars3):
    b = bars3
    i = 20
    o = b["open"][i + 1]
    # force bar i+1 to touch both a 10-pt stop and a 10-pt target after a market entry at its open
    b = b.with_columns(pl.when(pl.arange(0, b.height) == i + 1).then(o + 30).otherwise(pl.col("high")).alias("high"),
                       pl.when(pl.arange(0, b.height) == i + 1).then(o - 30).otherwise(pl.col("low")).alias("low"))
    strat = OneShot(i, Order(side=1, qty=1, stop_offset=10, target_offset=10))
    tr = Backtester(b, strat, cost(), rules(), EngineConfig()).run()
    t = tr.row(0, named=True)
    assert t["exit_reason"] == "stop_ambiguous" and t["ambiguous"] is True
    assert t["net_usd"] < 0


def test_tick_resolver_decides_order(bars3):
    b = bars3
    i = 20
    o = b["open"][i + 1]
    b = b.with_columns(pl.when(pl.arange(0, b.height) == i + 1).then(o + 30).otherwise(pl.col("high")).alias("high"),
                       pl.when(pl.arange(0, b.height) == i + 1).then(o - 30).otherwise(pl.col("low")).alias("low"))
    t0 = b["ts_open"][i + 1]
    # prints: open, then up through target, then down through stop
    prints = [(t0, o), (t0 + dt.timedelta(seconds=5), o + 12), (t0 + dt.timedelta(seconds=40), o - 12)]
    trades = pl.DataFrame({"ts_event": [p[0] for p in prints], "price": [p[1] for p in prints], "symbol": ["NQH4"] * 3, "sequence": [1, 2, 3], "size": [1, 1, 1]})
    res = TickResolver(trades)
    strat = OneShot(i, Order(side=1, qty=1, stop_offset=10, target_offset=10))
    tr = Backtester(b, strat, cost(), rules(), EngineConfig(), resolver=res).run()
    t = tr.row(0, named=True)
    assert t["exit_reason"] == "target" and t["tick_resolved"] is True and not t["ambiguous"]
    assert t["exit_ts"] == prints[1][0]
    # reversed print order -> stop first
    trades2 = trades.with_columns(pl.Series("price", [o, o - 12, o + 12]))
    tr2 = Backtester(b, OneShot(i, Order(side=1, qty=1, stop_offset=10, target_offset=10)), cost(), rules(), EngineConfig(), resolver=TickResolver(trades2)).run()
    assert tr2.row(0, named=True)["exit_reason"] == "stop"


def test_limit_through_rule(bars3):
    b = bars3
    i = 30
    lim = b["low"][i + 1]           # touched exactly, not through
    strat = OneShot(i, Order(side=1, qty=1, type=OrderType.LIMIT, price=lim, stop_offset=50, target_offset=50, tif_bars=1))
    tr = Backtester(b, strat, cost(), rules(), EngineConfig()).run()
    assert tr.height == 0
    lim2 = b["low"][i + 1] + 0.25   # low is one tick through the limit -> fill
    tr2 = Backtester(b, OneShot(i, Order(side=1, qty=1, type=OrderType.LIMIT, price=lim2, stop_offset=50, target_offset=50, tif_bars=1)), cost(), rules(), EngineConfig()).run()
    assert tr2.height == 1 and tr2["entry_px"][0] == lim2 and tr2["entry_type"][0] == "limit"


def test_intrabar_entry_target_not_taken_same_bar_without_resolver(bars3):
    b = bars3
    i = 40
    o = b["open"][i + 1]
    stop_px = o + 5
    # bar i+1: high 40 above open (through stop entry and any target), low = open
    b = b.with_columns(pl.when(pl.arange(0, b.height) == i + 1).then(o + 40).otherwise(pl.col("high")).alias("high"),
                       pl.when(pl.arange(0, b.height) == i + 1).then(o).otherwise(pl.col("low")).alias("low"),
                       pl.when(pl.arange(0, b.height) == i + 1).then(o + 20).otherwise(pl.col("close")).alias("close"))
    strat = OneShot(i, Order(side=1, qty=1, type=OrderType.STOP, stop_price=stop_px, stop_offset=10, target_offset=10, max_hold_bars=1))
    tr = Backtester(b, strat, cost(), rules(), EngineConfig()).run()
    t = tr.row(0, named=True)
    assert t["entry_type"] == "stop" and t["entry_px"] == stop_px + 0.25
    assert t["exit_reason"] != "target" or t["exit_idx"] > i + 1


def test_flatten_time_and_no_entries_after(bars3):
    b = bars3
    r = rules(flatten_by="15:55")
    strat = OneShot(100, Order(side=1, qty=1, stop_offset=500, target_offset=500))
    tr = Backtester(b, strat, cost(), r, EngineConfig()).run()
    t = tr.row(0, named=True)
    assert t["exit_reason"] == "flatten"
    exit_ct = t["exit_ts"].astimezone(dt.timezone(dt.timedelta(hours=-6)))
    assert exit_ct.hour == 15 and exit_ct.minute == 55
    late = Backtester(b, OneShot(b.height - 3, Order(side=1, qty=1)), cost(), r, EngineConfig()).run()
    assert late.height == 0


def test_daily_loss_limit_forces_exit_and_blocks(bars3):
    b = bars3
    i = 15
    o = b["open"][i + 1]
    # make price collapse 100 points over bars i+1..i+3
    idx = pl.arange(0, b.height)
    b = b.with_columns(pl.when(idx.is_between(i + 1, i + 3)).then(o - 100).otherwise(pl.col("close")).alias("close"),
                       pl.when(idx.is_between(i + 1, i + 3)).then(o - 100).otherwise(pl.col("low")).alias("low"))
    class Twice:
        name = "twice"
        def on_bar(self, ctx):
            if ctx.i in (i, i + 5):
                return [Order(side=1, qty=1, stop_offset=500, target_offset=500)]
    tr = Backtester(b, Twice(), cost(), rules(daily_loss_limit=1000), EngineConfig()).run()
    assert tr.height == 1 and tr["exit_reason"][0].startswith("breach_daily_loss_limit")


def test_max_trades_per_day(bars3):
    class Always:
        name = "always"
        def on_bar(self, ctx):
            if ctx.position is None:
                return [Order(side=1, qty=1, max_hold_bars=2)]
    tr = Backtester(bars3, Always(), cost(), rules(), EngineConfig(max_trades_per_day=3)).run()
    per_day = tr.group_by("trade_date").len()["len"].to_list()
    assert max(per_day) == 3


def test_deterministic_and_truncation_invariant(bars3):
    class Always:
        name = "always"
        def on_bar(self, ctx):
            if ctx.position is None and ctx.i % 7 == 0:
                return [Order(side=1 if ctx.i % 2 else -1, qty=1, stop_offset=15, target_offset=15, max_hold_bars=10)]
    run = lambda bb: Backtester(bb, Always(), cost(), rules(), EngineConfig()).run()
    a, b2 = run(bars3), run(bars3)
    assert a.equals(b2)
    ok, msg = engine_truncation_test(run, bars3, bars3.height // 2)
    assert ok, msg


def test_strategy_cannot_see_future(bars3):
    seen = {}
    class Peek:
        name = "peek"
        def on_bar(self, ctx):
            seen[ctx.i] = ctx.bars.height
    Backtester(bars3, Peek(), cost(), rules(), EngineConfig()).run()
    assert all(v == i + 1 for i, v in seen.items())


def test_no_overnight_by_default_and_roll_exit():
    b = make_bars([dt.date(2023, 3, 6), dt.date(2023, 3, 7)])
    strat = OneShot(50, Order(side=1, qty=1, stop_offset=5000, target_offset=5000))
    tr = Backtester(b, strat, cost(), rules(), EngineConfig()).run()
    assert tr["exit_reason"][0] == "session_end" and tr["trade_date"][0] == dt.date(2023, 3, 6)
