"""Derive the OBSERVED NQ calendar + causal front-contract map from the trades audit output
(audit/trades_audit.json: hourly counts per symbol, minutely outright counts). Writes
configs/calendar_observed_NQ.yaml and data_cache/nq_front_map.parquet."""
import collections, datetime as dt, json, sys
sys.path.insert(0, "src")
import polars as pl, yaml
from nqgc.calendar import CT, trade_date_of
from nqgc.contracts import nq_front_map, is_outright
from nqgc.paths import CONFIG_DIR, CACHE_DIR, assert_writable_target

aud = json.load(open("audit/trades_audit.json"))
UTC = dt.timezone.utc
rows = []; mins = []
def parse_ts(x: str) -> dt.datetime:
    """DuckDB rendered timestamps in the session's local zone (offset present); normalise to UTC."""
    t = dt.datetime.fromisoformat(x)
    return t.astimezone(UTC) if t.tzinfo is not None else t.replace(tzinfo=UTC)
for fname, r in aud.items():
    for sym, h, n, v in r["hourly"]:
        rows.append((sym, parse_ts(h), n, v))
    for m, n, v in r["minutely_outright"]:
        mins.append((parse_ts(m), n, v))
hourly = pl.DataFrame(rows, schema=["symbol", "hour_utc", "n", "volume"], orient="row").unique()
hourly = hourly.with_columns(pl.col("hour_utc").dt.convert_time_zone("UTC"))
minutely = pl.DataFrame(mins, schema=["minute_utc", "n", "volume"], orient="row").unique().sort("minute_utc").with_columns(pl.col("minute_utc").dt.convert_time_zone("UTC"))
td = lambda c: (pl.col(c).dt.convert_time_zone("America/Chicago") + pl.duration(hours=7)).dt.date()
hourly = hourly.with_columns(td("hour_utc").alias("trade_date"))
minutely = minutely.with_columns(td("minute_utc").alias("trade_date"), pl.col("minute_utc").dt.convert_time_zone("America/Chicago").alias("ct"))
outr = hourly.filter(pl.col("symbol").map_elements(is_outright, return_dtype=pl.Boolean))
daily = outr.group_by(["trade_date", "symbol"]).agg(pl.sum("volume").alias("volume"), pl.sum("n").alias("n_trades")).sort(["trade_date", "symbol"])
fm = nq_front_map(daily)
fm = fm.join(daily.rename({"symbol": "front"}).select("trade_date", "front", pl.col("volume").alias("front_volume_same_day")), on=["trade_date", "front"], how="left")
CACHE_DIR.mkdir(exist_ok=True)
fm.write_parquet(assert_writable_target(CACHE_DIR / "nq_front_map.parquet"))
daily.write_parquet(assert_writable_target(CACHE_DIR / "nq_daily_volume_by_symbol.parquet"))
# per trade date structure from minutely outright counts
per_day = minutely.group_by("trade_date").agg(pl.min("ct").alias("first"), pl.max("ct").alias("last"), pl.len().alias("n_minutes"), pl.sum("volume").alias("volume")).sort("trade_date")
dates = per_day["trade_date"].to_list()
dset = set(dates)
holidays = []
d = dates[0]
while d <= dates[-1]:
    if d.weekday() < 5 and d not in dset:
        holidays.append(d)
    d += dt.timedelta(days=1)
early = {}; partial = []
for r in per_day.iter_rows(named=True):
    lm = r["last"].hour * 60 + r["last"].minute
    fm_ = r["first"].hour * 60 + r["first"].minute
    late_start = not (r["first"].hour == 17 and r["first"].minute <= 5)
    ends_in_evening = r["last"].hour >= 17          # session ended before midnight of its first calendar day
    if late_start or ends_in_evening or r["n_minutes"] < 400:
        partial.append(dict(trade_date=str(r["trade_date"]), first_ct=r["first"].strftime("%a %H:%M"), last_ct=r["last"].strftime("%a %H:%M"), n_minutes=r["n_minutes"]))
        continue
    if lm < 15 * 60 + 45:
        m = ((lm + 1 + 14) // 15) * 15
        early[str(r["trade_date"])] = f"{m // 60:02d}:{m % 60:02d}"
# daily halt check 15:15-15:30 CT: minutes with prints in that window
halt = minutely.with_columns((pl.col("ct").dt.hour().cast(pl.Int32) * 60 + pl.col("ct").dt.minute().cast(pl.Int32)).alias("m"))
halt_counts = halt.filter(pl.col("m").is_between(15 * 60 + 15, 15 * 60 + 29)).group_by("trade_date").len()
halt_days = halt_counts.filter(pl.col("len") > 0).height
# holes: gaps > 30 min inside a trade date not at the session open and not the 15:15-15:30 halt
g = minutely.select("minute_utc", "trade_date", "ct", pl.col("minute_utc").diff().dt.total_minutes().alias("gap")).filter(pl.col("gap") > 30)
holes = []
for r in g.iter_rows(named=True):
    t = r["ct"]
    if t.hour == 17 and t.minute <= 5:
        continue
    if t.hour == 15 and 29 <= t.minute <= 35:
        continue
    holes.append(dict(trade_date=str(r["trade_date"]), resumes_at_utc=str(r["minute_utc"]), resumes_ct=t.strftime("%a %H:%M"), gap_minutes=int(r["gap"])))
rolls = fm.filter(pl.col("roll_day") | pl.col("bootstrap")).select("trade_date", "front", "basis_date", "basis_volume", "bootstrap").to_dicts()
out = dict(instrument="NQ", source="Databento GLBX.MDP3 NQ trades parquet 2021_H1..2026_H1, derived by scripts/build_calendar_nq.py",
           first_trade_date=str(dates[0]), last_trade_date=str(dates[-1]), n_trade_dates=len(dates),
           holidays=[str(h) for h in holidays], early_closes=early, partial_sessions=partial,
           daily_halt_1515_1530_days_with_prints=int(halt_days), data_holes=holes,
           roll_days=[{k: str(v) for k, v in x.items()} for x in rolls], trade_dates=[str(x) for x in dates])
assert_writable_target(CONFIG_DIR / "calendar_observed_NQ.yaml").write_text(yaml.safe_dump(out, sort_keys=False))
print("trade dates", len(dates), "holidays", holidays)
print("early closes", early)
print("partial sessions", partial)
print("halt days with prints 15:15-15:29", halt_days, "of", len(dates))
print("holes", holes)
print("rolls", rolls)
