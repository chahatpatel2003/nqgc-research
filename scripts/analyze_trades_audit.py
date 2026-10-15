"""Summarise audit/trades_audit.json into tables for the docs."""
import json, datetime as dt, collections
aud = json.load(open("audit/trades_audit.json"))
def u(x):
    t = dt.datetime.fromisoformat(x); return (t.astimezone(dt.timezone.utc) if t.tzinfo else t).strftime("%Y-%m-%d %H:%M")
print("| file | rows | outright symbols | spread symbols | spread rows | off-tick prints | price<=0 | size=0 | ts_recv desc | lag p50 us | lag p99 us | lag max ms | lag<0 | exact-dup groups | (ts,seq) dup groups | secs |")
print("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
tot=0; allsyms=collections.defaultdict(lambda: dict(n=0, vol=0, t0=None, t1=None, pmin=1e12, pmax=0))
jumps=[]
for f, r in aud.items():
    syms=r["symbols"]; outr=[s for s in syms if "-" not in s[0]]; spr=[s for s in syms if "-" in s[0]]
    spread_rows=sum(s[2] for s in spr)
    q=r["lag_stats"][0]; neg=r["lag_stats"][1]
    print(f"| {f} | {r['rows']:,} | {len(outr)} | {len(spr)} | {spread_rows:,} | {r['tick_viol'][0]:,} | {r['tick_viol'][1]:,} | {r['tick_viol'][2]} | {r['nonmono_recv']} | {q[1]/1e3:.0f} | {q[2]/1e3:.0f} | {q[3]/1e6:.0f} | {neg} | {r['exact_dups']:,} | {r['ts_seq_dups']:,} | {r['secs']} |")
    tot+=r["rows"]
    for sym, iid, n, t0, t1, pmin, pmax, vol in syms:
        a=allsyms[(sym, iid)]; a["n"]+=n; a["vol"]+=vol; t0=u(t0); t1=u(t1); a["t0"]=min(a["t0"] or t0, t0); a["t1"]=max(a["t1"] or t1, t1); a["pmin"]=min(a["pmin"],pmin); a["pmax"]=max(a["pmax"],pmax)
    for j in r["jumps"][:8]:
        jumps.append((f, j[0], u(j[1]) + "Z") + tuple(j[2:]))
print("TOTAL rows", f"{tot:,}")
print("\n## Outright contracts (instrument_id, rows, volume, first/last print, price range)")
print("| symbol | instrument_id | rows | volume | first print (UTC) | last print (UTC) | min px | max px |")
print("|---|---|---|---|---|---|---|---|")
for (sym,iid),a in sorted(allsyms.items(), key=lambda kv: kv[1]["t0"]):
    if "-" in sym: continue
    print(f"| {sym} | {iid} | {a['n']:,} | {a['vol']:,} | {a['t0'][:16]} | {a['t1'][:16]} | {a['pmin']} | {a['pmax']} |")
print("\n## Calendar spreads present:", sorted({s for (s,i) in allsyms if '-' in s}))
print("\n## Largest print-to-print jumps (outrights, |rel|>0.2%): file, symbol, ts, price, prev, next, size, rel")
for j in sorted(jumps, key=lambda x: -abs(float(x[7])))[:25]:
    print("  ", j)
print("\n## Jump counts per file (>0.1%, >0.2%, >0.5%, >1%):")
for f, r in aud.items(): print("  ", f, r["jump_counts"])
print("\n## flags histogram per file:")
for f, r in aud.items(): print("  ", f, r["flags_hist"])
