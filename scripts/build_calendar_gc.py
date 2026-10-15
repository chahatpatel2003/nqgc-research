"""Derive the OBSERVED GC trading calendar from the data (holidays, early closes, data holes, roll flags).
Writes configs/calendar_observed_GC.yaml. Infrastructure access (aggregate metadata only)."""
import collections, datetime as dt, sys
sys.path.insert(0, "src")
import polars as pl, yaml
from nqgc.calendar import CT, trade_date_expr
from nqgc.contracts import gc_roll_flags, gc_segments
from nqgc.paths import CONFIG_DIR, gc_bar_files, assert_writable_target

df = pl.concat([pl.read_parquet(p) for p in gc_bar_files()]).sort("ts_event").unique("ts_event", keep="first", maintain_order=True)
df = df.with_columns(trade_date_expr("ts_event").alias("trade_date"))
ct = df.select(pl.col("ts_event").dt.convert_time_zone("America/Chicago").alias("ct"), "trade_date", "instrument_id", "volume")
per_day = (ct.group_by("trade_date").agg(pl.min("ct").alias("first"), pl.max("ct").alias("last"), pl.len().alias("n_bars"), pl.sum("volume").alias("volume")).sort("trade_date"))
flags = gc_roll_flags(df.select("ts_event", "instrument_id", "trade_date"))
per_day = per_day.join(flags.select("trade_date", "roll_switch_date", "thin_last_day"), on="trade_date", how="left")
dates = per_day["trade_date"].to_list()
holidays = []
d = dates[0]
while d <= dates[-1]:
    if d.weekday() < 5 and d not in set(dates):
        holidays.append(d)
    d += dt.timedelta(days=1)
early = {}
for r in per_day.iter_rows(named=True):
    last = r["last"]
    # normal close: last bar opens 15:59 CT (or 16:00 settlement bar). Early close if last bar < 15:30 and it's not a data hole.
    if last.hour * 60 + last.minute < 15 * 60 + 30 and not r["thin_last_day"] and r["n_bars"] >= 500 and r["first"].hour == 17 and r["first"].minute == 0:
        # round up to next :00/:15/:30/:45 as the official early close
        m = last.hour * 60 + last.minute + 1
        m = ((m + 14) // 15) * 15
        early[str(r["trade_date"])] = f"{m // 60:02d}:{m % 60:02d}"
# data holes: gaps > 90 min inside a trade date that are not the thin roll day, excluding the maintenance hour
g = df.select("ts_event", "trade_date", pl.col("ts_event").diff().dt.total_minutes().alias("gap")).filter(pl.col("gap") > 90)
holes = []
thin = set(per_day.filter("thin_last_day")["trade_date"].to_list())
for r in g.iter_rows(named=True):
    t = r["ts_event"].astimezone(CT)
    if t.hour == 17 and t.minute == 0:       # gap ends at a session open: weekend / holiday / early-close closure, not a hole
        continue
    holes.append(dict(trade_date=str(r["trade_date"]), resumes_at_utc=str(r["ts_event"]), gap_minutes=int(r["gap"]), thin_roll_day=r["trade_date"] in thin))
segs = gc_segments(df.select("ts_event", "instrument_id"))
rolls = [dict(instrument_id=int(s["instrument_id"]), first_bar_utc=str(s["t0"]), last_bar_utc=str(s["t1"]), n_bars=int(s["n_bars"])) for s in segs.iter_rows(named=True)]
hole_dates = {h["trade_date"] for h in holes if h["gap_minutes"] > 300}
early = {k: v for k, v in early.items() if k not in hole_dates}
out = dict(instrument="GC", source="Databento GC.v.0 1-minute bars, derived 2026-09-02 by scripts/build_calendar_gc.py",
           first_trade_date=str(dates[0]), last_trade_date=str(dates[-1]), n_trade_dates=len(dates),
           holidays=[str(h) for h in holidays], early_closes=early,
           roll_switch_dates=[str(x) for x in per_day.filter("roll_switch_date")["trade_date"].to_list()],
           thin_last_days=[str(x) for x in sorted(thin)], data_holes=holes, segments=rolls,
           trade_dates=[str(x) for x in dates])
p = assert_writable_target(CONFIG_DIR / "calendar_observed_GC.yaml")
p.write_text(yaml.safe_dump(out, sort_keys=False))
print("holidays", len(holidays), "early closes", len(early), "holes", len(holes), "roll switch dates", len(out["roll_switch_dates"]), "thin", len(thin))
print("early closes:", early)
print("holes:", holes)
