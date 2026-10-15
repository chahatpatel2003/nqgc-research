import datetime as dt
import polars as pl
from nqgc.calendar import trade_date_of, trade_date_expr, session_open_utc, ct_wallclock_to_utc, session_label_expr, CT, UTC


def test_trade_date_shift_winter_and_summer():
    # 17:00 CT Sunday 2024-01-07 (winter, UTC-6) = 23:00 UTC -> trade date Monday 2024-01-08
    assert trade_date_of(dt.datetime(2024, 1, 7, 23, 0, tzinfo=UTC)) == dt.date(2024, 1, 8)
    assert trade_date_of(dt.datetime(2024, 1, 7, 22, 59, tzinfo=UTC)) == dt.date(2024, 1, 7)
    # summer (UTC-5): 17:00 CT = 22:00 UTC
    assert trade_date_of(dt.datetime(2024, 7, 7, 22, 0, tzinfo=UTC)) == dt.date(2024, 7, 8)
    assert trade_date_of(dt.datetime(2024, 7, 8, 20, 59, tzinfo=UTC)) == dt.date(2024, 7, 8)   # 15:59 CT
    assert trade_date_of(dt.datetime(2024, 7, 8, 21, 0, tzinfo=UTC)) == dt.date(2024, 7, 8)    # 16:00 CT still same date


def test_dst_transition_days():
    # US DST starts 2024-03-10 02:00 local. Sunday open that evening is 17:00 CDT = 22:00 UTC.
    assert session_open_utc(dt.date(2024, 3, 11)) == dt.datetime(2024, 3, 10, 22, 0, tzinfo=UTC)
    # before DST: Sunday 2024-03-03 open 17:00 CST = 23:00 UTC
    assert session_open_utc(dt.date(2024, 3, 4)) == dt.datetime(2024, 3, 3, 23, 0, tzinfo=UTC)
    # DST ends 2024-11-03: Sunday open 17:00 CST = 23:00 UTC
    assert session_open_utc(dt.date(2024, 11, 4)) == dt.datetime(2024, 11, 3, 23, 0, tzinfo=UTC)


def test_polars_expr_matches_scalar():
    ts = [dt.datetime(2024, 3, 9, 22, 30, tzinfo=UTC), dt.datetime(2024, 3, 10, 22, 30, tzinfo=UTC), dt.datetime(2024, 11, 3, 22, 30, tzinfo=UTC)]
    df = pl.DataFrame({"ts_event": ts}).with_columns(pl.col("ts_event").dt.replace_time_zone("UTC"))
    got = df.select(trade_date_expr()).to_series().to_list()
    assert got == [trade_date_of(t) for t in ts]


def test_wallclock_mapping_evening_belongs_to_previous_calendar_day():
    d = dt.date(2024, 1, 8)
    assert ct_wallclock_to_utc(d, "17:30") == dt.datetime(2024, 1, 7, 23, 30, tzinfo=UTC)
    assert ct_wallclock_to_utc(d, "15:55") == dt.datetime(2024, 1, 8, 21, 55, tzinfo=UTC)


def test_session_labels():
    ts = [dt.datetime(2024, 1, 8, 15, 0, tzinfo=UTC),   # 09:00 CT -> RTH
          dt.datetime(2024, 1, 8, 5, 0, tzinfo=UTC),    # 23:00 CT -> ASIA
          dt.datetime(2024, 1, 8, 22, 30, tzinfo=UTC)]  # 16:30 CT -> MAINT
    df = pl.DataFrame({"ts_event": ts}).with_columns(pl.col("ts_event").dt.replace_time_zone("UTC"))
    assert df.select(session_label_expr("NQ")).to_series().to_list() == ["RTH", "ASIA", "MAINT"]
