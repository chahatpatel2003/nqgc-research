"""One-time cache: NQ front-contract trade prints per trade date (infrastructure access, unlocked phases only).
Output: data_cache/nq_front_ticks/YYYY-MM.parquet with [trade_date, symbol, ts_event(ns UTC), price, size, sequence, side].
Never touches locked phases (Access('infrastructure') window ends 2026-06-17)."""
import sys, time, datetime as dt
sys.path.insert(0, "src")
import duckdb, polars as pl
from nqgc.guard import Access, trade_date_predicate_sql
from nqgc.paths import CACHE_DIR, nq_trades_files, assert_writable_target
from nqgc.data import _con

acc = Access("infrastructure", "NQ", purpose="build front-contract tick cache for Phase 2 strategies")
lo, hi = acc.window()
fm = pl.read_parquet(CACHE_DIR / "nq_front_map.parquet").filter(~pl.col("bootstrap") & (pl.col("trade_date") >= lo) & (pl.col("trade_date") <= hi))
pairs = {(r["trade_date"], r["front"]) for r in fm.iter_rows(named=True)}
out_dir = assert_writable_target(CACHE_DIR / "nq_front_ticks"); out_dir.mkdir(parents=True, exist_ok=True)
con = _con(mem="8GB", threads=8)
td = trade_date_predicate_sql("ts_event")
t0 = time.time()
for p in nq_trades_files():
    y, h = p.stem.split("_"); y = int(y)
    f0 = dt.date(y, 1, 1) if h == "H1" else dt.date(y, 7, 1)
    f1 = dt.date(y, 6, 30) if h == "H1" else dt.date(y, 12, 31)
    syms = sorted({s for d, s in pairs if f0 - dt.timedelta(days=3) <= d <= f1 + dt.timedelta(days=3)})
    if not syms:
        continue
    q = (f"SELECT {td} AS trade_date, symbol, ts_event, price, size, sequence, side FROM read_parquet('{p}') "
         f"WHERE symbol IN ({','.join(repr(s) for s in syms)}) AND {td} BETWEEN DATE '{lo}' AND DATE '{hi}'")
    df = pl.from_arrow(con.execute(q).arrow())
    if df.schema["ts_event"].time_zone is None:
        df = df.with_columns(pl.col("ts_event").dt.replace_time_zone("UTC"))
    df = df.with_columns(pl.col("ts_event").dt.cast_time_unit("ns"))
    keep = pl.DataFrame({"trade_date": [d for d, s in pairs], "symbol": [s for d, s in pairs]})
    df = df.join(keep, on=["trade_date", "symbol"], how="inner").sort(["ts_event", "sequence"])
    df = df.with_columns(pl.col("trade_date").dt.strftime("%Y-%m").alias("month"))
    for (m,), g in df.group_by(["month"], maintain_order=True):
        f = out_dir / f"{m}.parquet"
        if f.exists():   # a month can straddle two half-year files (files cut mid-session at 00:00 UTC)
            g = pl.concat([pl.read_parquet(f), g.drop("month")]).unique(maintain_order=True).sort(["ts_event", "sequence"])
        else:
            g = g.drop("month")
        g.write_parquet(f)
    print(p.name, "rows", df.height, "months", df["month"].n_unique(), f"{time.time()-t0:.0f}s", flush=True)
print("DONE")
