"""Deterministic, leak-safe bar-driven backtest engine (single instrument, single strategy).

Timing contract (enforced, not assumed):
  * The strategy is called once per bar, AFTER the bar closes, with a context that exposes
    bars[0..i] and indicator arrays[0..i] only. Its orders carry submitted_idx = i.
  * A market order created at the close of bar i fills at open[i+1] (+ slippage). Limit/stop
    orders are checked against bars i+1, i+2, ... A fill is never placed in bar i.
  * Stop/target exits inside a bar: if both are touched and a tick resolver is present, the actual
    trade sequence decides; otherwise the configured conservative rule applies ('worst' = stop first)
    and the trade is flagged ambiguous. If the position was opened INSIDE the bar (stop/limit entry)
    and no resolver exists, a touched stop counts as a loss and a touched target is NOT taken.
  * Every fill asserts fill_ts > signal_ts. Violations raise LeakageError.
  * Forced flatten, daily loss limit, trailing drawdown, max trades/day and one-position-at-a-time
    are configuration, evaluated at bar closes on information available at that close.
"""
from __future__ import annotations
import datetime as dt
import math
from dataclasses import dataclass, field, asdict
from typing import Protocol

import numpy as np
import polars as pl

from .calendar import ct_wallclock_to_utc, load_observed_calendar
from .execution import CostModel, Order, OrderType
from .risk import AccountState, PropFirmRules, size_fixed, size_fixed_dollar_risk, size_pct_account


class LeakageError(RuntimeError):
    pass


# --------------------------------------------------------------------------------------------
@dataclass
class Position:
    side: int
    qty: int
    entry_px: float
    entry_idx: int
    entry_ts: dt.datetime
    signal_idx: int
    signal_ts: dt.datetime
    entry_type: str
    intrabar_entry: bool
    stop: float | None
    target: float | None
    init_stop: float | None
    tag: str
    max_hold_bars: int | None
    mae_pts: float = 0.0
    mfe_pts: float = 0.0
    entry_slip_pts: float = 0.0


@dataclass
class Trade:
    strategy: str
    instrument: str
    symbol: str
    side: int
    qty: int
    signal_ts: dt.datetime
    entry_ts: dt.datetime
    exit_ts: dt.datetime
    entry_idx: int
    exit_idx: int
    entry_px: float
    exit_px: float
    entry_type: str
    exit_reason: str
    init_stop: float | None
    target: float | None
    gross_pts: float
    gross_usd: float
    fees_usd: float
    slippage_usd: float
    net_usd: float
    r_multiple: float
    mae_pts: float
    mfe_pts: float
    hold_bars: int
    hold_minutes: float
    ambiguous: bool
    tick_resolved: bool
    trade_date: dt.date
    session: str
    tag: str


class Strategy(Protocol):
    name: str
    def on_bar(self, ctx: "BarContext") -> list[Order] | None: ...


class BarContext:
    """Read-only, causally bounded view handed to the strategy at the close of bar i."""
    __slots__ = ("i", "_bars", "_ind", "position", "account", "now", "trade_date")

    def __init__(self, i, bars, ind, position, account, now, trade_date):
        self.i, self._bars, self._ind, self.position, self.account, self.now, self.trade_date = i, bars, ind, position, account, now, trade_date

    @property
    def bars(self) -> pl.DataFrame:
        return self._bars.slice(0, self.i + 1)

    def ind(self, name: str) -> np.ndarray:
        return self._ind[name][: self.i + 1]

    def last(self, col: str):
        return self._bars[col][self.i]


# --------------------------------------------------------------------------------------------
class TickResolver:
    """Resolves intrabar ordering using actual trade prints (NQ). Prints are ordered by (ts_event, sequence)."""

    def __init__(self, trades: pl.DataFrame):
        self._by_sym = {}
        for (sym,), g in trades.sort(["ts_event", "sequence"]).group_by(["symbol"], maintain_order=True):
            self._by_sym[sym] = (g["ts_event"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy(), g["price"].to_numpy(), g["ts_event"].to_list())

    def first_touch(self, symbol: str, t_from_ns: int, t_to_ns: int, levels: list[tuple[str, float, str]],
                    start_after_trigger: tuple[float, str] | None = None):
        """levels: [(name, price, '>=' or '<=')]. Returns (name, ts, price) of the first print satisfying a level,
        scanning prints with t_from_ns <= ts_event <= t_to_ns. If start_after_trigger=(px, cmp) is given, the scan
        starts at the first print satisfying that trigger (the entry print) and considers prints strictly after it."""
        if symbol not in self._by_sym:
            return None
        ts, px, tsl = self._by_sym[symbol]
        a = np.searchsorted(ts, t_from_ns, side="left")
        b = np.searchsorted(ts, t_to_ns, side="right")
        if a >= b:
            return None
        seg = px[a:b]
        start = 0
        if start_after_trigger is not None:
            tp, tc = start_after_trigger
            hit = np.flatnonzero(seg >= tp) if tc == ">=" else np.flatnonzero(seg <= tp)
            if len(hit) == 0:
                return None
            start = hit[0] + 1
        best = None
        for name, lp, cmp in levels:
            idx = np.flatnonzero(seg[start:] >= lp) if cmp == ">=" else np.flatnonzero(seg[start:] <= lp)
            if len(idx):
                k = start + idx[0]
                if best is None or k < best[0]:
                    best = (k, name)
        if best is None:
            return None
        k, name = best
        return name, tsl[a + k], float(px[a + k])


# --------------------------------------------------------------------------------------------
@dataclass
class EngineConfig:
    instrument: str = "NQ"
    execution_lag_bars: int = 1
    position_mode: str = "one_at_a_time"
    max_trades_per_day: int | None = None
    sizing: dict = field(default_factory=lambda: {"mode": "fixed_contracts", "contracts": 1})
    respect_tradeable: bool = True
    allow_overnight: bool = False


class Backtester:
    def __init__(self, bars: pl.DataFrame, strategy: Strategy, cost: CostModel, rules: PropFirmRules,
                 cfg: EngineConfig, indicators: dict[str, np.ndarray] | None = None, resolver: TickResolver | None = None):
        from .bars import check_bar_semantics
        check_bar_semantics(bars)
        self.bars, self.strategy, self.cost, self.rules, self.cfg = bars, strategy, cost, rules, cfg
        self.ind = indicators or {}
        for k, v in self.ind.items():
            if len(v) != bars.height:
                raise ValueError(f"indicator {k} length {len(v)} != bars {bars.height}")
        self.resolver = resolver
        self.trades: list[Trade] = []
        self.events: list[dict] = []
        self._prep()

    # ---- precompute numpy views ---------------------------------------------------------------
    def _prep(self):
        b = self.bars
        self.o, self.h, self.l, self.c = (b[k].to_numpy() for k in ("open", "high", "low", "close"))
        self.ts_open, self.ts_close = b["ts_open"].to_list(), b["ts_close"].to_list()
        self.ts_open_ns = b["ts_open"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy()
        self.ts_close_ns = b["ts_close"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy()
        self.td = b["trade_date"].to_list()
        self.sym = b["symbol"].to_list() if "symbol" in b.columns else [self.cost.spec.symbol_root] * b.height
        self.sess = b["session"].to_list() if "session" in b.columns else ["?"] * b.height
        self.tradeable = b["tradeable"].to_numpy() if "tradeable" in b.columns else np.ones(b.height, dtype=bool)
        cal = load_observed_calendar(self.cfg.instrument)
        early = {dt.date.fromisoformat(k): v for k, v in (cal.get("early_closes") or {}).items()}
        self.flatten_ns = {}
        for d in sorted(set(self.td)):
            t = None
            if self.rules.flatten_by:
                t = ct_wallclock_to_utc(d, self.rules.flatten_by, self.cfg.instrument)
            if d in early:
                ec = ct_wallclock_to_utc(d, early[d], self.cfg.instrument) - dt.timedelta(minutes=5)
                t = ec if t is None else min(t, ec)
            self.flatten_ns[d] = int(t.timestamp() * 1e9) if t else None

    # ---- helpers -------------------------------------------------------------------------------
    def _size(self, order: Order, ref_px: float, stop_px: float | None, account: AccountState) -> int:
        s = self.cfg.sizing
        cap = self.rules.max_contracts.get(self.cfg.instrument) if self.rules.max_contracts else None
        if order.qty:
            n = order.qty
        elif s["mode"] == "fixed_contracts":
            n = size_fixed(s["contracts"])
        elif s["mode"] == "fixed_dollar_risk":
            n = size_fixed_dollar_risk(s["risk_usd"], None if stop_px is None else abs(ref_px - stop_px), self.cost.spec.point_value)
        elif s["mode"] == "pct_account_risk":
            n = size_pct_account(account.balance, s["pct"], None if stop_px is None else abs(ref_px - stop_px), self.cost.spec.point_value)
        else:
            raise ValueError(s["mode"])
        return min(n, cap) if cap else n

    def _abs_level(self, val, offset, fill_px, side, kind) -> float | None:
        if val is not None:
            return self.cost.spec.round_to_tick(val)
        if offset is not None:
            sign = -side if kind == "stop" else side
            return self.cost.spec.round_to_tick(fill_px + sign * offset)
        return None

    def _open_position(self, order: Order, i: int, fill_px: float, intrabar: bool, entry_ts, account: AccountState, entry_type: str, ref_slip_base: float):
        stop = self._abs_level(getattr(order, "stop", None), getattr(order, "stop_offset", None), fill_px, order.side, "stop")
        target = self._abs_level(getattr(order, "target", None), getattr(order, "target_offset", None), fill_px, order.side, "target")
        qty = self._size(order, fill_px, stop, account)
        if qty <= 0:
            self.events.append(dict(i=i, what="entry_skipped_zero_size", tag=order.tag))
            return None
        # The open of bar i+1 is the first print at/after ts_close[i] (== ts_open[i+1]); equality is the boundary case.
        if entry_ts < order.submitted_ts:
            raise LeakageError(f"fill at {entry_ts} before signal at {order.submitted_ts}")
        return Position(order.side, qty, fill_px, i, entry_ts, order.submitted_idx, order.submitted_ts, entry_type, intrabar,
                        stop, target, stop, order.tag, getattr(order, "max_hold_bars", None),
                        entry_slip_pts=abs(fill_px - ref_slip_base))

    def _close(self, pos: Position, i: int, exit_px: float, reason: str, exit_ts, ambiguous: bool, tick_resolved: bool, slip_pts: float, account: AccountState):
        pts = (exit_px - pos.entry_px) * pos.side
        gross = self.cost.pnl_points_to_usd(pts, pos.qty)
        fees = self.cost.fees(pos.qty, 2)
        slip_usd = self.cost.pnl_points_to_usd(pos.entry_slip_pts + slip_pts, pos.qty)
        net = gross - fees
        risk_pts = abs(pos.entry_px - pos.init_stop) if pos.init_stop is not None else float("nan")
        r = (net / self.cost.pnl_points_to_usd(risk_pts, pos.qty)) if risk_pts and risk_pts > 0 else float("nan")
        hold_min = (exit_ts - pos.entry_ts).total_seconds() / 60.0
        self.trades.append(Trade(self.strategy.name, self.cfg.instrument, self.sym[i], pos.side, pos.qty, pos.signal_ts, pos.entry_ts, exit_ts,
                                 pos.entry_idx, i, pos.entry_px, exit_px, pos.entry_type, reason, pos.init_stop, pos.target,
                                 pts, gross, fees, slip_usd, net, r, pos.mae_pts, pos.mfe_pts, i - pos.entry_idx, hold_min,
                                 ambiguous, tick_resolved, self.td[pos.entry_idx], self.sess[pos.entry_idx], pos.tag))
        account.on_realised(net, exit_ts)

    # ---- main loop ------------------------------------------------------------------------------
    def run(self) -> pl.DataFrame:
        account = AccountState(self.rules)
        pending: list[Order] = []
        pos: Position | None = None
        n = self.bars.height
        cur_day = None
        for i in range(n):
            day = self.td[i]
            o, h, l, c = self.o[i], self.h[i], self.l[i], self.c[i]
            if day != cur_day:
                if pos is not None and not self.cfg.allow_overnight:
                    # should have been flattened; data hole or missing flatten config -> exit at previous close
                    self._close(pos, i - 1, self.cost.fill_market(self.c[i - 1], -pos.side), "session_end", self.ts_close[i - 1], False, False, self.cost.slip("market"), account)
                    pos = None
                pending = []
                account.new_day(day)
                cur_day = day
            flat_ns = self.flatten_ns.get(day)
            in_flatten = flat_ns is not None and self.ts_close_ns[i] >= flat_ns
            side_sym_change = i > 0 and self.sym[i] != self.sym[i - 1]
            if pos is not None and side_sym_change:
                self._close(pos, i - 1, self.cost.fill_market(self.c[i - 1], -pos.side), "roll", self.ts_close[i - 1], False, False, self.cost.slip("market"), account)
                pos = None

            # 1. pending orders vs bar i (all were submitted at the close of a bar < i)
            still = []
            for od in pending:
                if od.submitted_idx >= i:
                    raise LeakageError("order evaluated in its own signal bar")
                if od.tif_bars is not None and i - od.submitted_idx > od.tif_bars:
                    self.events.append(dict(i=i, what="order_expired", tag=od.tag)); continue
                if od.tag == "exit":
                    if pos is not None:
                        px = self.cost.fill_market(o, od.side)
                        self._close(pos, i, px, "strategy_exit", self.ts_open[i], False, False, self.cost.slip("market"), account)
                        pos = None
                    continue
                if pos is not None or in_flatten or not account.can_trade(self.cfg.max_trades_per_day):
                    continue   # one position at a time / no new entries in the flatten window / rule breach
                if od.type == OrderType.MARKET:
                    px = self.cost.fill_market(o, od.side)
                    pos = self._open_position(od, i, px, False, self.ts_open[i], account, "market", o)
                elif od.type == OrderType.LIMIT:
                    if self.cost.limit_fillable(od.price, h, l, od.side):
                        px = self.cost.fill_limit(od.price, o, od.side)
                        pos = self._open_position(od, i, px, True, self.ts_close[i], account, "limit", px)
                    else:
                        still.append(od)
                elif od.type == OrderType.STOP:
                    trig = (h >= od.stop_price) if od.side > 0 else (l <= od.stop_price)
                    if trig:
                        px = self.cost.fill_stop(od.stop_price, o, od.side)
                        base = max(od.stop_price, o) if od.side > 0 else min(od.stop_price, o)
                        pos = self._open_position(od, i, px, True, self.ts_close[i], account, "stop", base)
                    else:
                        still.append(od)
                else:
                    raise NotImplementedError(od.type)
            pending = still

            # 2. exits for bar i
            if pos is not None:
                s = pos.side
                entered_here = pos.entry_idx == i
                pos.mfe_pts = max(pos.mfe_pts, (h - pos.entry_px) * s if s > 0 else (pos.entry_px - l))
                pos.mae_pts = max(pos.mae_pts, (pos.entry_px - l) if s > 0 else (h - pos.entry_px))
                stop_hit = pos.stop is not None and ((l <= pos.stop) if s > 0 else (h >= pos.stop))
                tgt_hit = pos.target is not None and self.cost.limit_fillable(pos.target, h, l, -s)
                exit_px = None; reason = None; amb = False; tick = False; exit_ts = self.ts_close[i]; slip = 0.0
                if stop_hit and tgt_hit:
                    res = None
                    if self.resolver is not None:
                        levels = [("stop", pos.stop, "<=" if s > 0 else ">="), ("target", pos.target, ">=" if s > 0 else "<=")]
                        trig = None
                        if entered_here and pos.intrabar_entry:
                            trig = (pos.entry_px, ">=" if (pos.entry_type == "stop") == (s > 0) else "<=")
                        res = self.resolver.first_touch(self.sym[i], self.ts_open_ns[i], self.ts_close_ns[i], levels, trig)
                    if res is not None:
                        tick = True
                        if res[0] == "stop":
                            exit_px, reason, exit_ts, slip = self.cost.fill_stop(pos.stop, o, -s), "stop", res[1], self.cost.slip("stop")
                        else:
                            exit_px, reason, exit_ts = self.cost.fill_limit(pos.target, o, -s), "target", res[1]
                    else:
                        amb = True
                        exit_px, reason, slip = self.cost.fill_stop(pos.stop, o, -s), "stop_ambiguous", self.cost.slip("stop")
                elif stop_hit:
                    exit_px, reason, slip = self.cost.fill_stop(pos.stop, o, -s), "stop", self.cost.slip("stop")
                elif tgt_hit:
                    if entered_here and pos.intrabar_entry and self.resolver is None:
                        pass   # sequence unknown: do not take the target in the entry bar
                    elif entered_here and pos.intrabar_entry:
                        trig = (pos.entry_px, ">=" if (pos.entry_type == "stop") == (s > 0) else "<=")
                        res = self.resolver.first_touch(self.sym[i], self.ts_open_ns[i], self.ts_close_ns[i], [("target", pos.target, ">=" if s > 0 else "<=")], trig)
                        if res is not None:
                            exit_px, reason, exit_ts, tick = self.cost.fill_limit(pos.target, o, -s), "target", res[1], True
                    else:
                        exit_px, reason = self.cost.fill_limit(pos.target, o, -s), "target"
                if exit_px is None and pos.max_hold_bars is not None and i - pos.entry_idx >= pos.max_hold_bars:
                    exit_px, reason, slip = self.cost.fill_market(c, -s), "max_hold", self.cost.slip("market")
                if exit_px is None and in_flatten:
                    exit_px, reason, slip = self.cost.fill_market(c, -s), "flatten", self.cost.slip("market")
                if exit_px is None and i == n - 1:
                    exit_px, reason, slip = self.cost.fill_market(c, -s), "end_of_data", self.cost.slip("market")
                if exit_px is None:
                    unreal = self.cost.pnl_points_to_usd((c - pos.entry_px) * s, pos.qty)
                    account.on_mark(unreal, self.ts_close[i])
                    if account.breached:
                        exit_px, reason, slip = self.cost.fill_market(c, -s), f"breach_{account.breached}", self.cost.slip("market")
                if exit_px is not None:
                    self._close(pos, i, exit_px, reason, exit_ts, amb, tick, slip, account)
                    pos = None

            # 3. strategy decision at the close of bar i
            if not account.can_trade(self.cfg.max_trades_per_day) and pos is None:
                continue
            if self.cfg.respect_tradeable and not self.tradeable[i] and pos is None:
                continue
            ctx = BarContext(i, self.bars, self.ind, pos, account, self.ts_close[i], day)
            orders = self.strategy.on_bar(ctx) or []
            for od in orders:
                od.submitted_idx, od.submitted_ts = i, self.ts_close[i]
                if od.tag != "exit" and (pos is not None or in_flatten):
                    continue
                if od.type in (OrderType.LIMIT,) and od.price is None:
                    raise ValueError("limit order needs price")
                if od.type == OrderType.STOP and od.stop_price is None:
                    raise ValueError("stop order needs stop_price")
                pending.append(od)
        self.account = account
        return self.trades_frame()

    def trades_frame(self) -> pl.DataFrame:
        if not self.trades:
            return pl.DataFrame(schema={k: pl.Null for k in Trade.__dataclass_fields__})
        return pl.DataFrame([asdict(t) for t in self.trades])
