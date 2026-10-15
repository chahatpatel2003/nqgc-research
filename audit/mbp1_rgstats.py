import pyarrow.parquet as pq, glob, os, json, time
files = sorted(glob.glob('/Volumes/T9/nq data/raw/mbp1/*.parquet'))
out={}
for p in files:
    t0=time.time(); f=pq.ParquetFile(p); md=f.metadata
    names=[md.schema.column(i).path for i in range(md.num_columns)] if hasattr(md.schema.column(0),'path') else None
    idx={}
    rg0=md.row_group(0)
    for c in range(rg0.num_columns): idx[rg0.column(c).path_in_schema]=c
    rows=[]
    for i in range(md.num_row_groups):
        rg=md.row_group(i)
        def st(col):
            s=rg.column(idx[col]).statistics
            return (s.min, s.max, s.null_count) if s else (None,None,None)
        rows.append(dict(i=i, n=rg.num_rows, ts_recv=st('ts_recv'), ts_event=st('ts_event'), symbol=st('symbol'), price=st('price'), bid=st('bid_px_00'), ask=st('ask_px_00'), rtype=st('rtype'), action=st('action')))
    out[os.path.basename(p)]=rows
    print(os.path.basename(p), 'rgs', len(rows), 'secs', round(time.time()-t0,1), flush=True)
json.dump(out, open('audit/mbp1_rgstats.json','w'), default=str)
print('DONE')
