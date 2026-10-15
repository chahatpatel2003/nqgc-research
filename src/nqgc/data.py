"""Guarded, read-only loaders for the raw datasets. Every loader:
  * takes an `Access` (phase-scoped) and clips the requested trade-date range to the phase window;
  * filters on the CME TRADE DATE computed from ts_event (never on the UTC calendar date);
  * returns tz-aware UTC timestamps; prices as float64 (points); never writes to T9.
"""
from __future__ import annotations
import datetime as dt
from pathlib import Path

import duckdb
import polars as pl

from .calendar import trade_date_expr
from .guard import Access, trade_date_predicate_sql
from .paths import CACHE_DIR, assert_writable_target, gc_bar_files, nq_dbn_files, nq_trades_files

TRADE_COLS = ["ts_event", "ts_recv", "instrument_id", "symbol", "side", "price", "size", "sequence", "flags"]


def _con(mem="6GB", threads=6) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    scratch = CACHE_DIR / "duckdb_tmp"
    assert_writable_target(scratch).mkdir(parents=True, exist_ok=True)
    con.execute(f"SET memory_limit='{mem}'; SET threads={threads}; SET temp_directory='{scratch}'; SET TimeZone='UTC';")
    return con


def _files_for(start: dt.date, end: dt.date) -> list[Path]:
    """Half-year files whose nominal span intersects [start-3d, end+3d] (files are cut at 00:00 UTC, mid-session)."""
    out = []
    for p in nq_trades_files():
        y, h = p.stem.split("_")
        y = int(y)
        f0 = dt.date(y, 1, 1) if h == "H1" else dt.date(y, 7, 1)
        f1 = dt.date(y, 6, 30) if h == "H1" else dt.date(y, 12, 31)
        if f1 >= start - dt.timedelta(days=3) and f0 <= end + dt.timedelta(days=3):
            out.append(p)
    return out


def load_nq_trades(access: Access, start, end, symbols: list[str] | None = None,
                   outrights_only: bool = True, columns: list[str] = TRADE_COLS) -> pl.DataFrame:
    """Trade prints for trade dates in [start, end] (clipped to the access window), sorted by
    (ts_event, sequence, file row order). Duplicated identical fills are KEPT (they are real fills)."""
    s, e = access.clip(start, end)
    if s > e:
        return pl.DataFrame(schema={c: pl.Null for c in columns})
    files = _files_for(s, e)
    if not files:
        raise FileNotFoundError(f"no NQ trades files cover {s}..{e}")
    con = _con()
    td = trade_date_predicate_sql("ts_event")
    where = [f"{td} BETWEEN DATE '{s}' AND DATE '{e}'"]
    if outrights_only:
        where.append("symbol NOT LIKE '%-%'")
    if symbols:
        where.append("symbol IN (" + ",".join(f"'{x}'" for x in symbols) + ")")
    cols = ", ".join(columns) + ", row_number() OVER () AS file_row"
    parts = []
    for p in files:
        parts.append(f"SELECT {cols}, '{p.name}' AS src FROM read_parquet('{p}') WHERE " + " AND ".join(where))
    sql = " UNION ALL ".join(parts)
    tbl = con.execute(f"SELECT * FROM ({sql}) ORDER BY ts_event, sequence, src, file_row").arrow()
    df = pl.from_arrow(tbl).drop("file_row", "src")
    df = df.with_columns(pl.col("ts_event").dt.replace_time_zone("UTC") if df.schema["ts_event"].time_zone is None else pl.col("ts_event"))
    return df.with_columns(trade_date_expr("ts_event").alias("trade_date"))


def nq_daily_volume(access: Access) -> pl.DataFrame:
    """[trade_date, symbol, volume, n_trades] over the whole access window (infrastructure use)."""
    s, e = access.window()
    con = _con()
    td = trade_date_predicate_sql("ts_event")
    parts = [f"SELECT {td} AS trade_date, symbol, sum(size) AS volume, count(*) AS n_trades FROM read_parquet('{p}') "
             f"WHERE symbol NOT LIKE '%-%' GROUP BY 1,2" for p in nq_trades_files()]
    sql = " UNION ALL ".join(parts)
    df = pl.from_arrow(con.execute(f"SELECT trade_date, symbol, sum(volume) AS volume, sum(n_trades) AS n_trades FROM ({sql}) "
                                   f"WHERE trade_date BETWEEN DATE '{s}' AND DATE '{e}' GROUP BY 1,2 ORDER BY 1,2").arrow())
    return df


def load_gc_bars(access: Access, start, end) -> pl.DataFrame:
    """GC.v.0 1-minute bars for trade dates in [start, end]. Adds trade_date and ts_close (= ts_event + 60s).
    ts_event is the bar OPEN time; the bar's OHLCV is only knowable at ts_close."""
    s, e = access.clip(start, end)
    frames = []
    for p in gc_bar_files():
        y = int(p.stem[3:7])
        if y < s.year - 1 or y > e.year + 1:
            continue
        frames.append(pl.read_parquet(p))
    df = pl.concat(frames).sort("ts_event").unique(subset=["ts_event"], keep="first", maintain_order=True)
    df = df.with_columns(trade_date_expr("ts_event").alias("trade_date"),
                         (pl.col("ts_event") + pl.duration(seconds=60)).dt.cast_time_unit("ns").alias("ts_close"))
    return df.filter((pl.col("trade_date") >= s) & (pl.col("trade_date") <= e))


def load_nq_dbn(access: Access, start, end, outrights_only: bool = True) -> pl.DataFrame:
    """Decode the Databento DBN batch (2026-06-17 .. 2026-08-14) into the same layout as load_nq_trades."""
    import zstandard
    from databento_dbn import DBNDecoder
    s, e = access.clip(start, end)
    rows = []
    for p in nq_dbn_files():
        d = dt.date.fromisoformat(f"{p.name[10:14]}-{p.name[14:16]}-{p.name[16:18]}")
        if d < s - dt.timedelta(days=2) or d > e + dt.timedelta(days=1):
            continue
        raw = zstandard.ZstdDecompressor().stream_reader(open(p, "rb")).read()
        dec = DBNDecoder(); dec.write(raw); recs = dec.decode()
        meta = recs[0]
        id2sym = {}
        for rs, ivs in meta.mappings.items():
            for iv in ivs:
                id2sym[int(iv["symbol"])] = rs
        for r in recs[1:]:
            sym = id2sym.get(r.instrument_id, str(r.instrument_id))
            if outrights_only and "-" in sym:
                continue
            rows.append((r.ts_event, r.ts_recv, r.instrument_id, sym, str(r.side.value if hasattr(r.side, 'value') else r.side),
                         r.price / 1e9, r.size, r.sequence, r.flags))
    df = pl.DataFrame(rows, schema=["ts_event", "ts_recv", "instrument_id", "symbol", "side", "price", "size", "sequence", "flags"], orient="row")
    df = df.with_columns(pl.from_epoch("ts_event", time_unit="ns").dt.replace_time_zone("UTC"),
                         pl.from_epoch("ts_recv", time_unit="ns").dt.replace_time_zone("UTC"),
                         pl.col("instrument_id").cast(pl.UInt32), pl.col("size").cast(pl.UInt32),
                         pl.col("sequence").cast(pl.UInt32), pl.col("flags").cast(pl.UInt8))
    df = df.with_columns(trade_date_expr("ts_event").alias("trade_date")).sort(["ts_event", "sequence"])
    return df.filter((pl.col("trade_date") >= s) & (pl.col("trade_date") <= e))
