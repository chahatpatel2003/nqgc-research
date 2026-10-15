import polars as pl, glob, json, os, datetime as dt, zoneinfo, numpy as np
files = sorted(glob.glob('/Volumes/T9/Gc:Xauusd/gc/gc_20??.parquet')) + sorted(glob.glob('/Volumes/T9/Gc:Xauusd/gc/Holdout/gc_20??.parquet'))
dfs=[]
for p in files:
    d = pl.read_parquet(p)
    d = d.with_columns(pl.lit(os.path.basename(p)).alias('file'))
    dfs.append(d)
df = pl.concat(dfs).sort('ts_event')
print('total rows', df.height, 'files', len(files))
print('schema', df.schema)
print('rtype', df['rtype'].unique().to_list(), 'publisher', df['publisher_id'].unique().to_list())
print('symbols', df.group_by('symbol').agg(pl.len(), pl.min('ts_event').alias('t0'), pl.max('ts_event').alias('t1')).sort('t0'))
# instrument_id segments
seg = df.with_columns((pl.col('instrument_id') != pl.col('instrument_id').shift(1)).fill_null(True).alias('chg'))
segs = seg.filter('chg').select('ts_event','instrument_id','open','close')
print('instrument_id changes (rolls):', segs.height)
# roll details: last bar of old id vs first bar of new id
ids = df.group_by('instrument_id').agg(pl.min('ts_event').alias('t0'), pl.max('ts_event').alias('t1'), pl.len().alias('n'), pl.sum('volume').alias('vol')).sort('t0')
print(ids)
rolls=[]
prev=None
for row in df.select('ts_event','instrument_id','open','high','low','close','volume').iter_rows():
    if prev is not None and row[1]!=prev[1]:
        rolls.append(dict(t_prev=str(prev[0]), id_prev=prev[1], close_prev=prev[5], t_new=str(row[0]), id_new=row[1], open_new=row[2], gap=row[2]-prev[5], gap_minutes=(row[0]-prev[0]).total_seconds()/60))
    prev=row
for r in rolls: print('ROLL', r)
# duplicates
dup = df.filter(pl.col('ts_event').is_duplicated())
print('duplicate ts_event rows', dup.height)
if dup.height: print(dup.head(20))
# spacing
sp = df.select((pl.col('ts_event').diff().dt.total_seconds()).alias('d')).drop_nulls()
print('spacing seconds histogram (top):', sp.group_by('d').len().sort('len', descending=True).head(15))
print('min spacing', sp['d'].min(), 'count <60', sp.filter(pl.col('d')<60).height)
# OHLC sanity
bad = df.filter((pl.col('high')<pl.max_horizontal('open','close')) | (pl.col('low')>pl.min_horizontal('open','close')) | (pl.col('high')<pl.col('low')) | (pl.col('open')<=0) | (pl.col('low')<=0))
print('OHLC sanity violations', bad.height)
# tick compliance GC 0.1
for c in ['open','high','low','close']:
    v = df.filter(((pl.col(c)*10).round(6) % 1).abs() > 1e-6).height
    print('tick(0.1) violations', c, v)
print('zero-volume bars', df.filter(pl.col('volume')==0).height, 'null volume', df['volume'].null_count())
# bad prints: 1-min close jumps
j = df.with_columns((pl.col('close')/pl.col('close').shift(1)-1).alias('r'), (pl.col('high')/pl.col('low')-1).alias('rng'))
print('close jumps >1%:', j.filter(pl.col('r').abs()>0.01).select('ts_event','symbol','instrument_id','open','high','low','close','volume','r').sort(pl.col('r').abs(), descending=True).head(25))
print('bar range >1.5%:', j.filter(pl.col('rng')>0.015).select('ts_event','symbol','open','high','low','close','volume','rng').sort('rng', descending=True).head(20))
# per trading day structure in CT
ct = zoneinfo.ZoneInfo('America/Chicago')
tsl = df['ts_event'].to_list()
import collections
day_minutes = collections.Counter(); first_last = {}
hour_ct = collections.Counter()
for t in tsl:
    tc = t.astimezone(ct)
    td = (tc + dt.timedelta(hours=7)).date()   # CME trade date: session opening 17:00 CT belongs to next calendar day
    day_minutes[td]+=1
    if td not in first_last: first_last[td]=[tc,tc]
    else: first_last[td][1]=tc
    hour_ct[(tc.hour, tc.minute==0)] += 0
    hour_ct[tc.hour]+=1
print('trading days', len(day_minutes))
cnts = np.array(list(day_minutes.values()))
print('bars per trade date: min', cnts.min(), 'p5', np.percentile(cnts,5), 'median', np.median(cnts), 'max', cnts.max())
print('CT hour histogram', sorted((k,v) for k,v in hour_ct.items() if isinstance(k,int)))
short = sorted([(d,n,first_last[d][0].strftime('%a %H:%M'),first_last[d][1].strftime('%H:%M')) for d,n in day_minutes.items() if n<1000], key=lambda x:x[0])
print('short days (<1000 bars):', len(short))
for s in short: print('  ', s)
# weekday distribution and missing weekdays
alld = sorted(day_minutes)
missing=[]
d=alld[0]
while d<=alld[-1]:
    if d.weekday()<5 and d not in day_minutes: missing.append(d)
    d+=dt.timedelta(days=1)
print('missing weekday trade dates:', len(missing)); print(missing)
# first/last bar time of day per weekday (mode)
fl = collections.Counter((first_last[d][0].strftime('%a %H:%M'), first_last[d][1].strftime('%a %H:%M')) for d in day_minutes)
print('first/last (CT) patterns:', fl.most_common(12))
# gc_2024_jan vs gc_2024
a = pl.read_parquet('/Volumes/T9/Gc:Xauusd/gc/Holdout/gc_2024_jan.parquet'); b = pl.read_parquet('/Volumes/T9/Gc:Xauusd/gc/Holdout/gc_2024.parquet').filter(pl.col('ts_event')<=a['ts_event'].max())
print('gc_2024_jan rows', a.height, 'gc_2024 same window rows', b.height, 'identical:', a.sort('ts_event').equals(b.sort('ts_event')))
# year boundaries: gaps between files
for i in range(1,len(dfs)):
    print('file boundary', os.path.basename(files[i-1]), dfs[i-1]['ts_event'].max(), '->', os.path.basename(files[i]), dfs[i]['ts_event'].min())
# big intra-week gaps (> 90 min) list
g = df.select('ts_event', pl.col('ts_event').diff().dt.total_minutes().alias('gap')).filter(pl.col('gap')>90)
gl = [(str(t), m, t.astimezone(ct).strftime('%a %H:%M')) for t,m in g.iter_rows()]
print('gaps >90min:', len(gl))
wk = [x for x in gl if not (x[2].startswith('Sun') and 2400 <= x[1] <= 3000)]
print('non-weekend gaps >90min:', len(wk))
for x in wk: print('  ', x)
json.dump(dict(rolls=rolls, missing=[str(m) for m in missing], short=[(str(a),b,c,d) for a,b,c,d in short], gaps=wk), open('audit/gc_audit.json','w'), indent=1)
