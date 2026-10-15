import datetime as dt
import numpy as np
import polars as pl
from nqgc.tick_engine import TickExecutor, Intent
from nqgc.execution import CostModel, InstrumentSpec

SPEC = InstrumentSpec("NQ", 0.25, 20.0, 5.0)
UTC = dt.timezone.utc


def mk(prices, start=dt.datetime(2024, 1, 8, 15, 0, tzinfo=UTC), step_s=1):
    ts = np.array([int((start + dt.timedelta(seconds=i * step_s)).timestamp() * 1e9) for i in range(len(prices))], dtype=np.int64)
    return ts, np.array(prices, dtype=float)


def cost(slip=1):
    return CostModel(SPEC, fee_per_side=2.0, slippage_ticks={"market": slip, "stop": slip, "limit": 0})


def test_entry_strictly_after_signal_and_slippage():
    ts, px = mk([100, 101, 102, 103, 104])
    ex = TickExecutor(cost(), "NQ", "t")
    ex.run_day(dt.date(2024, 1, 8), "NQH4", ts, px, [Intent(ts[1], +1, exit_ts_ns=ts[4])])
    t = ex.ledger().row(0, named=True)
    assert t["entry_px"] == 102.25 and t["entry_ts"].timestamp() * 1e9 == ts[2]      # first print AFTER the signal print
    assert t["exit_reason"] == "time" and t["exit_px"] == 104 - 0.25 and t["gross_pts"] == 1.5


def test_stop_and_target_ordering_and_through_rule():
    ts, px = mk([100, 100, 110, 100.25, 90, 120])
    ex = TickExecutor(cost(0), "NQ", "t")
    # short at first print after ts[0]: entry 100 (idx1); target 90 needs a print <= 89.75 (through) -> 90 never 'through' -> stop 105 hit at idx2
    ex.run_day(dt.date(2024, 1, 8), "NQH4", ts, px, [Intent(ts[0], -1, stop=105, target=90)])
    t = ex.ledger().row(0, named=True)
    assert t["exit_reason"] == "stop" and t["exit_px"] == 110      # gapped through: fill at the print
    ex2 = TickExecutor(cost(0), "NQ", "t")
    ex2.run_day(dt.date(2024, 1, 8), "NQH4", ts, px, [Intent(ts[0], -1, stop=115, target=90.5)])
    t2 = ex2.ledger().row(0, named=True)
    assert t2["exit_reason"] == "target" and t2["exit_px"] == 90.5 and t2["exit_idx"] == 4


def test_one_open_trade_skips_overlapping_intents():
    ts, px = mk([100] * 20)
    ex = TickExecutor(cost(0), "NQ", "t")
    ex.run_day(dt.date(2024, 1, 8), "NQH4", ts, px, [Intent(ts[1], 1, exit_ts_ns=ts[10]), Intent(ts[5], 1, exit_ts_ns=ts[15]), Intent(ts[12], 1, exit_ts_ns=ts[18])])
    assert ex.ledger().height == 2 and ex.skipped[0]["why"] == "position_open"


def test_time_exit_uses_last_print_at_or_before_boundary():
    ts, px = mk([100, 101, 102, 103, 104, 105])
    ex = TickExecutor(cost(0), "NQ", "t")
    ex.run_day(dt.date(2024, 1, 8), "NQH4", ts, px, [Intent(ts[0], 1, exit_ts_ns=ts[3] + 500_000_000)])   # boundary between print 3 and 4
    t = ex.ledger().row(0, named=True)
    assert t["exit_idx"] == 3 and t["exit_px"] == 103
