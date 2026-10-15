"""Causal roll adjustment for carrying zones across contract rolls (port of nqlevels.build.roll.roll_spread):
for each roll date D (front S_old -> S_new), spread = median(incoming - outgoing) over incoming prints paired with the
most recent outgoing print within 1 s, measured on the basis session D-1 only (strictly before the decision cut).
adj(session) = cumulative sum of spreads of rolls at/before that session (points). Output data_cache/nq_roll_adjust.parquet."""
import datetime as dt, sys, time
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl, duckdb
from common import nq_front_map, load_day_ticks, print_at_or_before_raw
from nqgc.data import _con
from nqgc.paths import nq_trades_files, CACHE_DIR, assert_writable_target
from nqgc.guard import trade_date_predicate_sql

fm = nq_front_map()
dates = sorted(fm)
rolls = [(d, fm[d]["front"]) for d in dates if fm[d]["roll_day"]]
con = _con(mem="4GB", threads=6)
td = trade_date_predicate_sql("ts_event")
rows = []; adj = 0.0
prev_front = None
for d in dates:
    r = fm[d]
    if r["bootstrap"]:
        rows.append(dict(session=d, symbol=r["front"], adj=0.0, spread=None, n_pairs=None)); prev_front = r["front"]; continue
    if r["roll_day"] and prev_front is not None:
        basis = max(x for x in dates if x < d)
        t0 = time.time()
        # outgoing prints on the basis session from the cache; incoming from raw
        tk = load_day_ticks(basis)
        out_ts, out_px, sym = tk
        assert sym == prev_front, (basis, sym, prev_front)
        inc = None
        for p in nq_trades_files():
            y, h = p.stem.split("_"); y = int(y)
            f0 = dt.date(y, 1, 1) if h == "H1" else dt.date(y, 7, 1); f1 = dt.date(y, 6, 30) if h == "H1" else dt.date(y, 12, 31)
            if not (f0 - dt.timedelta(days=2) <= basis <= f1 + dt.timedelta(days=2)):
                continue
            q = con.execute(f"SELECT ts_event, price FROM read_parquet('{p}') WHERE symbol='{r['front']}' AND {td} = DATE '{basis}' ORDER BY ts_event, sequence").arrow()
            g = pl.from_arrow(q)
            if not g.is_empty():
                inc = g if inc is None else pl.concat([inc, g])
        if inc is None or inc.height < 200:
            rows.append(dict(session=d, symbol=r["front"], adj=adj, spread=None, n_pairs=0)); prev_front = r["front"]; print(d, "NO SPREAD"); continue
        inc = inc.with_columns(pl.col("ts_event").dt.cast_time_unit("ns"))
        in_ts = inc["ts_event"].cast(pl.Int64).to_numpy(); in_px = inc["price"].to_numpy()
        j = np.searchsorted(out_ts, in_ts, side="right") - 1
        ok = (j >= 0)
        ok[ok] &= (in_ts[ok] - out_ts[j[ok]]) <= 1_000_000_000
        diffs = in_px[ok] - out_px[j[ok]]
        spread = float(np.median(diffs)) if diffs.size >= 200 else None
        if spread is not None:
            adj += spread
        rows.append(dict(session=d, symbol=r["front"], adj=adj, spread=spread, n_pairs=int(diffs.size)))
        print(d, prev_front, "->", r["front"], "basis", basis, "spread", spread, "pairs", diffs.size, "adj", adj, f"{time.time()-t0:.0f}s", flush=True)
    else:
        rows.append(dict(session=d, symbol=r["front"], adj=adj, spread=None, n_pairs=None))
    prev_front = r["front"]
out = pl.DataFrame(rows)
out.write_parquet(assert_writable_target(CACHE_DIR / "nq_roll_adjust.parquet"))
print("DONE", out.filter(pl.col("spread").is_not_null()))
