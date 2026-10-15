import pyarrow.parquet as pq, glob, os, sys, json, datetime as dt
paths = sorted(glob.glob('/Volumes/T9/nq data/raw/trades/*.parquet')) + \
        sorted(glob.glob('/Volumes/T9/nq data/NQ_HOLDOUT/*.parquet')) + \
        sorted(glob.glob('/Volumes/T9/nq data/raw/mbp1/*.parquet')) + \
        sorted(glob.glob('/Volumes/T9/Gc:Xauusd/gc/*.parquet')) + sorted(glob.glob('/Volumes/T9/Gc:Xauusd/gc/Holdout/*.parquet'))
out=[]
for p in paths:
    try:
        f = pq.ParquetFile(p)
        md = f.metadata
        sch = f.schema_arrow
        kv = md.metadata or {}
        # find timestamp columns and get min/max from first/last row group stats
        stats = {}
        for i in [0, md.num_row_groups-1]:
            rg = md.row_group(i)
            for c in range(rg.num_columns):
                col = rg.column(c)
                if col.path_in_schema in ('ts_event','ts_recv','timestamp','ts','time','datetime') and col.statistics:
                    s = col.statistics
                    stats.setdefault(col.path_in_schema, {})
                    stats[col.path_in_schema][f'rg{i}'] = (str(s.min), str(s.max))
        rec = dict(path=p, size_MB=round(os.path.getsize(p)/1e6,1), rows=md.num_rows, row_groups=md.num_row_groups,
                   created_by=md.created_by, columns=[(fld.name, str(fld.type)) for fld in sch],
                   kv_keys=[k.decode() if isinstance(k,bytes) else k for k in kv.keys()],
                   ts_stats=stats)
        # pandas metadata for index info
        if b'pandas' in kv:
            pm = json.loads(kv[b'pandas'])
            rec['pandas_index'] = pm.get('index_columns')
            rec['pandas_cols'] = [(c['name'], c.get('pandas_type'), c.get('numpy_type'), c.get('metadata')) for c in pm.get('columns',[])]
        out.append(rec)
        print(f"{p}\n  size={rec['size_MB']}MB rows={rec['rows']:,} rgs={rec['row_groups']} created_by={rec['created_by']}\n  cols={rec['columns']}\n  ts_stats={stats}\n  pandas_index={rec.get('pandas_index')}")
    except Exception as e:
        print(f"{p}\n  ERROR: {e!r}")
        out.append(dict(path=p, error=repr(e)))
json.dump(out, open('audit/footers.json','w'), indent=1, default=str)
