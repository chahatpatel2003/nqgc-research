import duckdb, sys, json, glob, os, tempfile, time
SCR = os.environ.get("NQGC_SCRATCH", os.path.join(tempfile.gettempdir(), "nqgc-trades-audit"))
os.makedirs(SCR, exist_ok=True)
files = sorted(glob.glob('/Volumes/T9/nq data/raw/trades/*.parquet'))
out = {}
con = duckdb.connect()
con.execute(f"SET memory_limit='10GB'; SET threads=6; SET temp_directory='{SCR}/duckdb_tmp'; SET preserve_insertion_order=false;")
for p in files:
    t0=time.time(); name=os.path.basename(p); r={}
    con.execute(f"CREATE OR REPLACE VIEW t AS SELECT * FROM read_parquet('{p}')")
    r['rows'] = con.execute("SELECT count(*) FROM t").fetchone()[0]
    r['symbols'] = con.execute("""SELECT symbol, instrument_id, count(*) n, min(ts_event) t0, max(ts_event) t1, min(price) pmin, max(price) pmax, sum(size) vol
        FROM t GROUP BY 1,2 ORDER BY t0""").fetchall()
    r['distinct'] = con.execute("""SELECT count(DISTINCT rtype) rtypes, list(DISTINCT rtype) rtype_vals, list(DISTINCT action) actions, list(DISTINCT side) sides,
        list(DISTINCT depth) depths, list(DISTINCT publisher_id) pubs, count(DISTINCT flags) nflags FROM t""").fetchone()
    r['flags_hist'] = con.execute("SELECT flags, count(*) FROM t GROUP BY 1 ORDER BY 2 DESC").fetchall()
    r['exact_dups'] = con.execute("SELECT count(*) - count(DISTINCT (ts_event, instrument_id, sequence, price, size, side)) FROM t").fetchone()[0]
    r['ts_seq_dups'] = con.execute("SELECT count(*) FROM (SELECT ts_event, instrument_id, sequence, count(*) c FROM t GROUP BY 1,2,3 HAVING c>1)").fetchone()[0]
    r['nonmono_recv'] = con.execute("SELECT count(*) FROM (SELECT ts_recv, lag(ts_recv) OVER (ORDER BY rowid) p FROM (SELECT ts_recv, row_number() OVER () rowid FROM t)) WHERE ts_recv < p").fetchone()[0]
    r['lag_stats'] = con.execute("""SELECT quantile_cont(d,[0.0,0.5,0.99,1.0]), count(*) FILTER (WHERE d<0) FROM (SELECT epoch_ns(ts_recv)-epoch_ns(ts_event) d FROM t)""").fetchone()
    r['tick_viol'] = con.execute("SELECT count(*) FILTER (WHERE (price*4) <> floor(price*4)), count(*) FILTER (WHERE price<=0), count(*) FILTER (WHERE size=0), count(*) FILTER (WHERE price IS NULL) FROM t").fetchone()
    # hourly counts by symbol (UTC hour)
    r['hourly'] = con.execute("""SELECT symbol, date_trunc('hour', ts_event) h, count(*) n, sum(size) v FROM t GROUP BY 1,2 ORDER BY 2,1""").fetchall()
    # per-minute counts for outrights (no '-') all symbols combined
    r['minutely_outright'] = con.execute("""SELECT date_trunc('minute', ts_event) m, count(*) n, sum(size) v FROM t WHERE symbol NOT LIKE '%-%' GROUP BY 1 ORDER BY 1""").fetchall()
    # bad prints: per outright symbol, jumps vs previous trade
    r['jumps'] = con.execute("""WITH s AS (SELECT symbol, ts_event, sequence, price, size, lag(price) OVER (PARTITION BY symbol ORDER BY ts_event, sequence) pp, lead(price) OVER (PARTITION BY symbol ORDER BY ts_event, sequence) np FROM t WHERE symbol NOT LIKE '%-%')
        SELECT symbol, ts_event, price, pp, np, size, (price/pp-1) rel FROM s WHERE pp IS NOT NULL AND abs(price/pp-1) > 0.002 ORDER BY abs(price/pp-1) DESC LIMIT 60""").fetchall()
    r['jump_counts'] = con.execute("""WITH s AS (SELECT symbol, price, lag(price) OVER (PARTITION BY symbol ORDER BY ts_event, sequence) pp FROM t WHERE symbol NOT LIKE '%-%')
        SELECT count(*) FILTER (WHERE abs(price/pp-1)>0.001), count(*) FILTER (WHERE abs(price/pp-1)>0.002), count(*) FILTER (WHERE abs(price/pp-1)>0.005), count(*) FILTER (WHERE abs(price/pp-1)>0.01) FROM s WHERE pp IS NOT NULL""").fetchone()
    r['secs'] = round(time.time()-t0,1)
    out[name]=r
    print(name, 'rows', r['rows'], 'symbols', len(r['symbols']), 'distinct', r['distinct'], 'dups', r['exact_dups'], r['ts_seq_dups'], 'nonmono', r['nonmono_recv'], 'lag', r['lag_stats'], 'tick', r['tick_viol'], 'jumps', r['jump_counts'], 'secs', r['secs'], flush=True)
    json.dump(out, open('audit/trades_audit.json','w'), default=str)
print('DONE')
