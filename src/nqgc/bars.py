"""Bar construction with explicit availability semantics.

A bar row carries:
  ts_open  : bucket start (UTC).            NOTHING about the bar is known at ts_open.
  ts_close : bucket end = ts_open + width.  The bar's OHLCV becomes known at ts_close.
Signals evaluated on bar i may use bars[:i+1] and are timestamped ts_close[i]; the earliest
execution is at ts_open[i+1] (see engine.py). No bar is ever forward-filled from the future:
`regularize` inserts empty bars whose close is copied from the PREVIOUS bar only.
"""
from __future__ import annotations
import polars as pl

from .calendar import session_label_expr, trade_date_expr


def bars_from_trades(trades: pl.DataFrame, width_s: int, instrument: str = "NQ") -> pl.DataFrame:
    """Aggregate trade prints (sorted by ts_event, sequence) into fixed-width bars aligned to the UTC epoch.
    width_s must divide 3600 so that no bucket straddles the 17:00 CT session boundary."""
    if 3600 % width_s != 0:
        raise ValueError("bar width must divide 3600 s so buckets never straddle the session boundary")
    if trades.is_empty():
        return pl.DataFrame()
    t = trades.with_columns(pl.col("ts_event").dt.truncate(f"{width_s}s").alias("ts_open"))
    g = (t.group_by(["symbol", "ts_open"], maintain_order=True)
          .agg(pl.first("price").alias("open"), pl.max("price").alias("high"), pl.min("price").alias("low"),
               pl.last("price").alias("close"), pl.sum("size").alias("volume"), pl.len().alias("n_trades"),
               (pl.col("price") * pl.col("size")).sum().alias("_pv"),
               pl.first("ts_event").alias("ts_first_trade"), pl.last("ts_event").alias("ts_last_trade")))
    g = g.with_columns((pl.col("_pv") / pl.col("volume")).alias("bar_vwap"),
                       (pl.col("ts_open") + pl.duration(seconds=width_s)).dt.cast_time_unit("ns").alias("ts_close"),
                       pl.lit(False).alias("synthetic")).drop("_pv")
    g = g.with_columns(trade_date_expr("ts_open").alias("trade_date"), session_label_expr(instrument, "ts_open").alias("session"))
    return g.sort(["symbol", "ts_open"]).select("symbol", "trade_date", "session", "ts_open", "ts_close", "open", "high", "low", "close",
                                                "volume", "n_trades", "bar_vwap", "ts_first_trade", "ts_last_trade", "synthetic")


def resample_bars(bars: pl.DataFrame, width_s: int, instrument: str = "NQ") -> pl.DataFrame:
    """Aggregate finer bars (e.g. GC 1-minute) into width_s bars. ts_close = bucket end."""
    if 3600 % width_s != 0:
        raise ValueError("bar width must divide 3600 s")
    b = bars.with_columns(pl.col("ts_open").dt.truncate(f"{width_s}s").alias("_bucket"))
    keys = ["symbol", "_bucket"] if "symbol" in b.columns else ["_bucket"]
    agg = [pl.first("open"), pl.max("high"), pl.min("low"), pl.last("close"), pl.sum("volume"),
           pl.len().alias("n_src_bars")]
    if "n_trades" in b.columns:
        agg.append(pl.sum("n_trades"))
    if "bar_vwap" in b.columns:
        agg.append(((pl.col("bar_vwap") * pl.col("volume")).sum() / pl.col("volume").sum()).alias("bar_vwap"))
    g = b.sort("ts_open").group_by(keys, maintain_order=True).agg(agg).rename({"_bucket": "ts_open"})
    g = g.with_columns((pl.col("ts_open") + pl.duration(seconds=width_s)).dt.cast_time_unit("ns").alias("ts_close"), pl.lit(False).alias("synthetic"))
    g = g.with_columns(trade_date_expr("ts_open").alias("trade_date"), session_label_expr(instrument, "ts_open").alias("session"))
    return g.sort(keys[:-1] + ["ts_open"])


def gc_1m_to_bars(gc: pl.DataFrame, instrument: str = "GC") -> pl.DataFrame:
    """Normalise the GC.v.0 1-minute file layout to the framework layout (ts_event is the bar OPEN)."""
    b = gc.rename({"ts_event": "ts_open"}).with_columns(
        (pl.col("ts_open") + pl.duration(seconds=60)).dt.cast_time_unit("ns").alias("ts_close"), pl.lit(False).alias("synthetic"),
        pl.col("volume").cast(pl.Int64))
    b = b.with_columns(trade_date_expr("ts_open").alias("trade_date"), session_label_expr(instrument, "ts_open").alias("session"))
    return b.sort("ts_open")


def regularize(bars: pl.DataFrame, width_s: int) -> pl.DataFrame:
    """Insert missing buckets INSIDE each trade date as synthetic bars (volume 0, OHLC = previous close).
    The fill comes strictly from the previous real bar — never from a later one."""
    out = []
    for (td,), day in bars.group_by(["trade_date"], maintain_order=True):
        day = day.sort("ts_open")
        grid = pl.datetime_range(day["ts_open"][0], day["ts_open"][-1], interval=f"{width_s}s", time_zone="UTC", eager=True)
        full = pl.DataFrame({"ts_open": grid}).join(day, on="ts_open", how="left")
        full = full.with_columns(pl.col("synthetic").fill_null(True), pl.col("volume").fill_null(0),
                                 pl.col("trade_date").fill_null(pl.lit(td, dtype=pl.Date)),
                                 pl.col("close").fill_null(strategy="forward"))
        full = full.with_columns(*[pl.col(c).fill_null(pl.col("close")) for c in ("open", "high", "low")],
                                 pl.col("ts_close").fill_null((pl.col("ts_open") + pl.duration(seconds=width_s)).dt.cast_time_unit("ns")))
        for c in ("symbol", "session"):
            if c in full.columns:
                full = full.with_columns(pl.col(c).fill_null(strategy="forward"))
        out.append(full)
    return pl.concat(out)


def check_bar_semantics(bars: pl.DataFrame) -> None:
    """Assertions every bar frame must satisfy before it reaches the engine."""
    assert bars["ts_open"].is_sorted(), "bars must be sorted by ts_open"
    assert (bars["ts_close"] > bars["ts_open"]).all(), "ts_close must be after ts_open"
    assert bars["ts_open"].n_unique() == bars.height, "duplicate ts_open"
    real = bars.filter(~pl.col("synthetic")) if "synthetic" in bars.columns else bars
    chk = real.select((pl.col("high") >= pl.max_horizontal("open", "close")).all().alias("h"),
                      (pl.col("low") <= pl.min_horizontal("open", "close")).all().alias("l")).row(0)
    assert chk[0], "high < max(open, close)"
    assert chk[1], "low > min(open, close)"
    ov = bars.select((pl.col("ts_open").shift(-1) >= pl.col("ts_close")).fill_null(True).all()).item()
    assert ov, "overlapping bars"
