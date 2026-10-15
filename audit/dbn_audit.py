import zstandard, glob, os, json, time, collections, datetime as dt
from databento_dbn import DBNDecoder, Metadata
files = sorted(glob.glob('/Volumes/T9/nq data/NQ_HOLDOUT/GLBX-20260815-69WTYRKTDB/*.dbn.zst'))
out={}
for p in files:
    t0=time.time()
    raw = zstandard.ZstdDecompressor().stream_reader(open(p,'rb')).read()
    dec = DBNDecoder(); dec.write(raw); recs = dec.decode()
    meta = recs[0]; assert isinstance(meta, Metadata)
    mappings = {rs: [(iv['start_date'], iv['end_date'], iv['symbol']) for iv in ivs] for rs, ivs in meta.mappings.items()}
    cnt=collections.Counter(); first={}; last={}; pmin={}; pmax={}; vol=collections.Counter(); acts=collections.Counter(); rtypes=collections.Counter()
    nonmono=0; prev=None; tick_viol=0
    for r in recs[1:]:
        iid=r.instrument_id; cnt[iid]+=1; rtypes[int(r.rtype)]+=1; acts[str(r.action)]+=1
        px=r.price/1e9
        if (r.price % 250000000) != 0: tick_viol+=1
        pmin[iid]=min(pmin.get(iid,px),px); pmax[iid]=max(pmax.get(iid,px),px); vol[iid]+=r.size
        te=r.ts_event
        if iid not in first: first[iid]=te
        last[iid]=te
        if prev is not None and r.ts_recv<prev: nonmono+=1
        prev=r.ts_recv
    # map instrument ids to symbols via mappings: mappings are raw_symbol -> intervals with symbol=instrument_id string
    id2sym={}
    for rs, ivs in mappings.items():
        for s,e,sym in ivs: id2sym.setdefault(int(sym) if sym.isdigit() else sym, set()).add(rs)
    out[os.path.basename(p)] = dict(dataset=meta.dataset, schema=str(meta.schema), start=meta.start, end=meta.end, stype_in=str(meta.stype_in), stype_out=str(meta.stype_out), symbols=list(meta.symbols), ts_out=meta.ts_out, n_records=len(recs)-1,
        rtypes=dict(rtypes), actions=dict(acts), nonmono_recv=nonmono, tick_viol=tick_viol,
        per_id={str(i): dict(sym=sorted(id2sym.get(i,[])), n=cnt[i], vol=vol[i], t0=str(dt.datetime.fromtimestamp(first[i]/1e9, dt.timezone.utc)), t1=str(dt.datetime.fromtimestamp(last[i]/1e9, dt.timezone.utc)), pmin=pmin[i], pmax=pmax[i]) for i in cnt})
    print(os.path.basename(p), 'recs', len(recs)-1, 'ids', len(cnt), 'nonmono', nonmono, 'tick_viol', tick_viol, 'secs', round(time.time()-t0,1), flush=True)
json.dump(out, open('audit/dbn_audit.json','w'), indent=1, default=str)
print('DONE')
