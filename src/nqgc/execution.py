"""Configurable execution/cost model. Nothing here is hardcoded per firm; all numbers come from configs."""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from enum import Enum

import yaml

from .paths import CONFIG_DIR


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class Order:
    side: int                      # +1 buy, -1 sell
    qty: int
    type: OrderType = OrderType.MARKET
    price: float | None = None     # limit price (LIMIT / STOP_LIMIT)
    stop_price: float | None = None  # trigger (STOP / STOP_LIMIT)
    tag: str = "entry"
    tif_bars: int | None = None    # cancel after this many bars unfilled (None = GTC within session)
    submitted_idx: int = -1        # bar index at whose close the order was created
    submitted_ts: object = None
    # bracket for the resulting position: absolute prices or offsets (points) from the actual fill
    stop: float | None = None
    target: float | None = None
    stop_offset: float | None = None
    target_offset: float | None = None
    max_hold_bars: int | None = None


@dataclass
class InstrumentSpec:
    symbol_root: str
    tick_size: float
    point_value: float
    tick_value: float

    def round_to_tick(self, px: float, direction: int = 0) -> float:
        q = px / self.tick_size
        if direction > 0:
            q = math.ceil(q - 1e-9)
        elif direction < 0:
            q = math.floor(q + 1e-9)
        else:
            q = round(q)
        return round(q * self.tick_size, 10)


@dataclass
class CostModel:
    spec: InstrumentSpec
    fee_per_side: float                     # USD per contract per side (commission + exchange + clearing + nfa)
    slippage_ticks: dict = field(default_factory=lambda: {"market": 1, "stop": 1, "limit": 0})
    limit_fill_rule: str = "through"
    intrabar_ambiguity: str = "worst"

    @classmethod
    def from_config(cls, instrument: str, costs_path=None, instruments_path=None) -> "CostModel":
        with open(instruments_path or CONFIG_DIR / "instruments.yaml") as f:
            ins = yaml.safe_load(f)[instrument]
        with open(costs_path or CONFIG_DIR / "costs_default.yaml") as f:
            c = yaml.safe_load(f)
        spec = InstrumentSpec(ins.get("price_source_symbol_root", instrument), ins["tick_size"], ins["point_value"], ins["tick_value"])
        assert abs(spec.tick_size * spec.point_value - spec.tick_value) < 1e-9, f"tick_value inconsistent for {instrument}"
        fees = sum(c["per_side"][instrument].values())
        return cls(spec, fees, dict(c["slippage_ticks"][instrument]), c.get("limit_fill_rule", "through"), c.get("intrabar_ambiguity", "worst"))

    def slip(self, kind: str) -> float:
        return self.slippage_ticks.get(kind, 0) * self.spec.tick_size

    def fill_market(self, ref_px: float, side: int) -> float:
        """Market fill at ref_px (the next available price) moved AGAINST the trader by the configured slippage."""
        return self.spec.round_to_tick(ref_px + side * self.slip("market"))

    def fill_stop(self, trigger_px: float, bar_open: float, side: int) -> float:
        """Stop triggered inside a bar: fill at the trigger (or the open if the bar gapped through), plus slippage."""
        base = max(trigger_px, bar_open) if side > 0 else min(trigger_px, bar_open)
        return self.spec.round_to_tick(base + side * self.slip("stop"))

    def fill_limit(self, limit_px: float, bar_open: float, side: int) -> float:
        """Limit fill: at the limit, or better if the bar opened through it."""
        base = min(limit_px, bar_open) if side > 0 else max(limit_px, bar_open)
        return self.spec.round_to_tick(base)

    def limit_fillable(self, limit_px: float, bar_high: float, bar_low: float, side: int) -> bool:
        t = self.spec.tick_size
        if self.limit_fill_rule == "touch":
            return bar_low <= limit_px if side > 0 else bar_high >= limit_px
        # 'through': price must trade at least one tick beyond the limit
        return bar_low <= limit_px - t + 1e-12 if side > 0 else bar_high >= limit_px + t - 1e-12

    def fees(self, qty: int, sides: int = 2) -> float:
        return self.fee_per_side * qty * sides

    def pnl_points_to_usd(self, points: float, qty: int) -> float:
        return points * self.spec.point_value * qty
