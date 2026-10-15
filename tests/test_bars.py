import datetime as dt
import polars as pl
import pytest
from nqgc.bars import bars_from_trades, check_bar_semantics, regularize, resample_bars
from conftest import make_bars


def test_bars_from_trades_first_last_and_close_time():
    t0 = dt.datetime(2024, 1, 8, 15, 0, 0, tzinfo=dt.timezone.utc)
    rows = [(t0 + dt.timedelta(seconds=s), "NQH4", p, 1, i) for i, (s, p) in enumerate([(1, 100.0), (30, 101.0), (59, 99.5), (61, 102.0), (119, 101.5)])]
    tr = pl.DataFrame(rows, schema=["ts_event", "symbol", "price", "size", "sequence"], orient="row").with_columns(pl.col("ts_event").dt.replace_time_zone("UTC"))
    b = bars_from_trades(tr, 60)
    assert b.height == 2
    assert b["open"][0] == 100.0 and b["close"][0] == 99.5 and b["high"][0] == 101.0 and b["low"][0] == 99.5
    assert b["ts_close"][0] == t0 + dt.timedelta(seconds=60)
    assert b["ts_open"][1] == t0 + dt.timedelta(seconds=60)
    check_bar_semantics(b)


def test_regularize_fills_from_past_only():
    b = make_bars([dt.date(2023, 3, 6)]).slice(0, 10)
    gap = pl.concat([b.slice(0, 4), b.slice(6, 4)])
    r = regularize(gap, 60)
    assert r.height == 10
    assert r["synthetic"][4] and r["synthetic"][5]
    assert r["close"][4] == b["close"][3] and r["close"][5] == b["close"][3]   # not the later bar's value
    assert r["volume"][4] == 0


def test_resample_5m():
    b = make_bars([dt.date(2023, 3, 6)])
    r = resample_bars(b, 300)
    assert r["ts_close"][0] == r["ts_open"][0] + dt.timedelta(seconds=300)
    first5 = b.slice(0, 5)
    assert r["high"][0] == first5["high"].max() and r["open"][0] == first5["open"][0] and r["close"][0] == first5["close"][4]


def test_width_must_divide_hour():
    with pytest.raises(ValueError):
        bars_from_trades(pl.DataFrame({"ts_event": [], "symbol": [], "price": [], "size": [], "sequence": []}), 7 * 60)
