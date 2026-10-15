"""Tick-level executor for strategies whose signals are timestamps (not bars).

Contract:
  * An Intent carries signal_ts (the instant the information exists). The entry fills at the FIRST print
    with ts_event strictly AFTER signal_ts (+ configured slippage). No fill ever precedes its signal.
  * Exits, scanned print by print after the entry print, in chronological (ts_event, sequence) order:
      stop   : first print at/through the stop -> fill at the worse of stop / print, plus slippage
      target : first print THROUGH the target by >= 1 tick ('through' rule) -> fill at the target
      time   : the LAST print at/before exit_ts (final executable price at/before the boundary), minus slippage
      end    : last print of the day if nothing else happened
    Same-print tie between stop and target -> stop (worst case). Nothing is ambiguous at tick level.
  * one_open=True: an intent whose entry would occur while a trade is open is skipped (recorded).
Output uses the same ledger schema as engine.Backtester so stats/diagnostics are shared.
"""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field, asdict

import numpy as np
import polars as pl

from .engine import Trade
from .execution import CostModel


@dataclass
class Intent:
    signal_ts_ns: int
    side: int
    qty: int = 1
    stop: float | None = None
    target: float | None = None
    stop_offset: float | None = None    # points from the ACTUAL fill (stop placed adverse side)
    target_offset: float | None = None  # points from the ACTUAL fill (favourable side)
    exit_ts_ns: int | None = None       # hard time exit boundary (inclusive)
    max_entry_delay_ns: int | None = None
    entry_limit: float | None = None     # limit entry: fill at this price when a print trades THROUGH it (or touches, per limit_fill_rule)
    tag: str = "entry"
    meta: dict = field(default_factory=dict)


class TickExecutor:
    def __init__(self, cost: CostModel, instrument: str, strategy_name: str, one_open: bool = True):
        self.cost, self.instrument, self.name, self.one_open = cost, instrument, strategy_name, one_open
        self.trades: list[Trade] = []
        self.skipped: list[dict] = []

    def run_day(self, trade_date: dt.date, symbol: str, ts_ns: np.ndarray, px: np.ndarray, intents: list[Intent],
                session_label: str = "RTH") -> None:
        """ts_ns must be sorted ascending (ties already ordered by sequence)."""
        tick = self.cost.spec.tick_size
        open_until = -1          # exit index of the current open trade
        for it in sorted(intents, key=lambda x: x.signal_ts_ns):
            i = int(np.searchsorted(ts_ns, it.signal_ts_ns, side="right"))   # first print strictly after the signal
            if i >= len(ts_ns):
                self.skipped.append(dict(trade_date=trade_date, tag=it.tag, why="no_print_after_signal")); continue
            if it.entry_limit is not None:
                seg0 = px[i:]
                if self.cost.limit_fill_rule == "touch":
                    thr = it.entry_limit
                else:
                    thr = it.entry_limit - tick if it.side > 0 else it.entry_limit + tick
                hit0 = np.flatnonzero(seg0 <= thr + 1e-12) if it.side > 0 else np.flatnonzero(seg0 >= thr - 1e-12)
                if not hit0.size:
                    self.skipped.append(dict(trade_date=trade_date, tag=it.tag, why="limit_not_filled")); continue
                i = i + int(hit0[0])
                if it.max_entry_delay_ns is not None and ts_ns[i] - it.signal_ts_ns > it.max_entry_delay_ns:
                    self.skipped.append(dict(trade_date=trade_date, tag=it.tag, why="limit_after_cutoff")); continue
            if it.max_entry_delay_ns is not None and ts_ns[i] - it.signal_ts_ns > it.max_entry_delay_ns:
                self.skipped.append(dict(trade_date=trade_date, tag=it.tag, why="entry_delay_exceeded")); continue
            if it.exit_ts_ns is not None and ts_ns[i] > it.exit_ts_ns:
                self.skipped.append(dict(trade_date=trade_date, tag=it.tag, why="no_print_before_exit_boundary")); continue
            if self.one_open and i <= open_until:
                self.skipped.append(dict(trade_date=trade_date, tag=it.tag, why="position_open")); continue
            s = it.side
            if it.entry_limit is not None:
                entry_px = self.cost.spec.round_to_tick(it.entry_limit); slip_entry = 0.0      # limit fill at the limit price, unslipped
            else:
                entry_px = self.cost.fill_market(px[i], s)
                slip_entry = abs(entry_px - px[i])
            if it.stop_offset is not None:
                it.stop = self.cost.spec.round_to_tick(entry_px - s * it.stop_offset)
            if it.target_offset is not None:
                it.target = self.cost.spec.round_to_tick(entry_px + s * it.target_offset)
            # ---- exits ----
            seg = px[i + 1:]
            j_stop = j_tgt = -1
            if it.stop is not None:
                hit = np.flatnonzero(seg <= it.stop) if s > 0 else np.flatnonzero(seg >= it.stop)
                if hit.size:
                    j_stop = i + 1 + int(hit[0])
            if it.target is not None:
                if self.cost.limit_fill_rule == "touch":
                    thr = it.target
                else:
                    thr = it.target + tick if s > 0 else it.target - tick
                hit = np.flatnonzero(seg >= thr - 1e-12) if s > 0 else np.flatnonzero(seg <= thr + 1e-12)
                if hit.size:
                    j_tgt = i + 1 + int(hit[0])
            j_time = -1
            if it.exit_ts_ns is not None:
                k = int(np.searchsorted(ts_ns, it.exit_ts_ns, side="right")) - 1    # last print at/before boundary
                j_time = max(k, i)       # never before the entry print itself
            cands = [(j, kind) for j, kind in ((j_stop, "stop"), (j_tgt, "target"), (j_time, "time")) if j >= 0]
            if not cands:
                j, kind = len(px) - 1, "end_of_data"
            else:
                jmin = min(j for j, _ in cands)
                kinds = [kd for j, kd in cands if j == jmin]
                kind = "stop" if "stop" in kinds else ("target" if "target" in kinds else "time")
                j = jmin
            slip_exit = 0.0
            if kind == "stop":
                base = min(it.stop, px[j]) if s > 0 else max(it.stop, px[j])
                exit_px = self.cost.spec.round_to_tick(base - s * self.cost.slip("stop"))
                slip_exit = self.cost.slip("stop")
            elif kind == "target":
                exit_px = it.target
            else:
                exit_px = self.cost.fill_market(px[j], -s)
                slip_exit = self.cost.slip("market")
            if j == i:      # exit on the entry print (boundary edge case): flat at the same print
                exit_px = self.cost.fill_market(px[j], -s); kind = "time"; slip_exit = self.cost.slip("market")
            path = px[i:j + 1]
            mfe = float(path.max() - entry_px) if s > 0 else float(entry_px - path.min())
            mae = float(entry_px - path.min()) if s > 0 else float(path.max() - entry_px)
            pts = (exit_px - entry_px) * s
            qty = it.qty
            gross = self.cost.pnl_points_to_usd(pts, qty)
            fees = self.cost.fees(qty, 2)
            net = gross - fees
            risk_pts = abs(entry_px - it.stop) if it.stop is not None else float("nan")
            r = (net / self.cost.pnl_points_to_usd(risk_pts, qty)) if risk_pts == risk_pts and risk_pts > 0 else float("nan")
            t_entry = dt.datetime.fromtimestamp(ts_ns[i] / 1e9, dt.timezone.utc)
            t_exit = dt.datetime.fromtimestamp(ts_ns[j] / 1e9, dt.timezone.utc)
            t_sig = dt.datetime.fromtimestamp(it.signal_ts_ns / 1e9, dt.timezone.utc)
            self.trades.append(Trade(self.name, self.instrument, symbol, s, qty, t_sig, t_entry, t_exit, i, j, float(entry_px), float(exit_px),
                                     "market", kind, it.stop, it.target, float(pts), gross, fees,
                                     self.cost.pnl_points_to_usd(slip_entry + slip_exit, qty), net, r, max(mae, 0.0), max(mfe, 0.0),
                                     j - i, (t_exit - t_entry).total_seconds() / 60.0, False, True, trade_date, session_label, it.tag))
            open_until = j

    def ledger(self) -> pl.DataFrame:
        if not self.trades:
            return pl.DataFrame(schema={k: pl.Null for k in Trade.__dataclass_fields__})
        df = pl.DataFrame([asdict(t) for t in self.trades])
        return df.with_columns(pl.col("signal_ts").dt.cast_time_unit("ns"), pl.col("entry_ts").dt.cast_time_unit("ns"), pl.col("exit_ts").dt.cast_time_unit("ns"))
