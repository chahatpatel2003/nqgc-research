import datetime as dt
import numpy as np
import polars as pl
import pytest
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")


def make_bars(trade_dates, start_ct="08:30", end_ct="15:59", width_s=60, seed=0, base=17000.0, symbol="NQH4", tick=0.25):
    """Synthetic 1-minute bars covering [start_ct, end_ct] CT on each trade date (same calendar day)."""
    rng = np.random.default_rng(seed)
    frames = []
    for d in trade_dates:
        t0 = dt.datetime.combine(d, dt.time.fromisoformat(start_ct), tzinfo=CT).astimezone(dt.timezone.utc)
        t1 = dt.datetime.combine(d, dt.time.fromisoformat(end_ct), tzinfo=CT).astimezone(dt.timezone.utc)
        ts = pl.datetime_range(t0, t1, interval=f"{width_s}s", time_zone="UTC", eager=True)
        n = len(ts)
        steps = rng.normal(0, 3, n).cumsum()
        close = np.round((base + steps) / tick) * tick
        open_ = np.concatenate([[close[0]], close[:-1]])
        hi = np.maximum(open_, close) + np.round(rng.uniform(0, 4, n) / tick) * tick
        lo = np.minimum(open_, close) - np.round(rng.uniform(0, 4, n) / tick) * tick
        frames.append(pl.DataFrame({"symbol": [symbol] * n, "trade_date": [d] * n, "session": ["RTH"] * n, "ts_open": ts,
                                    "ts_close": ts + dt.timedelta(seconds=width_s), "open": open_, "high": hi, "low": lo, "close": close,
                                    "volume": rng.integers(50, 500, n), "n_trades": rng.integers(10, 100, n),
                                    "bar_vwap": (hi + lo + close) / 3, "synthetic": [False] * n, "tradeable": [True] * n}))
        base = close[-1]
    return pl.concat(frames)


@pytest.fixture
def bars3():
    return make_bars([dt.date(2023, 3, 6), dt.date(2023, 3, 7), dt.date(2023, 3, 8)])
