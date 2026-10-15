"""Strategy template. Copy, rename, fill in. The engine calls on_bar at the CLOSE of every bar with a
context that exposes only bars[0..i] and indicators[0..i]. Return orders for the NEXT bar or None.

Rules for a strategy file:
  * All parameters live in PARAMS (frozen into the spec by scripts/freeze_spec.py).
  * Never read data yourself; never import from nqgc.data here.
  * Structural levels (pivots, session extremes, OR, VWAP) must come from nqgc.indicators, which are
    truncation-tested. If you add a new indicator, add it to nqgc.indicators AND to tests/test_indicators.py.
"""
from __future__ import annotations
import datetime as dt
import numpy as np
import polars as pl
from nqgc import indicators as I
from nqgc.execution import Order, OrderType

NAME = "template"
VERSION = "0.1"
INSTRUMENT = "NQ"
TIMEFRAME_S = 60
PARAMS = dict(atr_n=14, stop_atr=2.0, target_atr=2.0, entry_ct="09:00", max_hold_bars=60)
RULES = """Plain-language mechanical rules go here, written BEFORE any backtest is run."""


def build_indicators(bars: pl.DataFrame) -> dict[str, np.ndarray]:
    """Vectorised, causal indicator arrays aligned to bars (each value uses bars[0..i] only)."""
    return {"atr": I.atr(bars, PARAMS["atr_n"])}


class Strategy:
    name = f"{NAME}_v{VERSION}"

    def __init__(self, params: dict | None = None):
        self.p = dict(PARAMS, **(params or {}))
        h, m = self.p["entry_ct"].split(":")
        self.entry_min = int(h) * 60 + int(m)

    def on_bar(self, ctx):
        if ctx.position is not None:
            return None
        ts_ct = ctx.last("ts_close").astimezone(dt.timezone.utc)
        from nqgc.calendar import CT
        ts_ct = ts_ct.astimezone(CT)
        if ts_ct.hour * 60 + ts_ct.minute != self.entry_min:
            return None
        atr = ctx.ind("atr")[-1]
        if np.isnan(atr):
            return None
        return [Order(side=1, qty=None, type=OrderType.MARKET,
                      stop_offset=self.p["stop_atr"] * atr, target_offset=self.p["target_atr"] * atr,
                      max_hold_bars=self.p["max_hold_bars"], tag="entry")]
