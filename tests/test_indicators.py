import datetime as dt
import numpy as np
import polars as pl
from nqgc import indicators as I
from nqgc.leakage import truncation_test, perturbation_test
from conftest import make_bars


def _b():
    return make_bars([dt.date(2023, 3, 6), dt.date(2023, 3, 7)], seed=3)


def test_atr_vwap_rolling_truncation_invariant():
    b = _b()
    for fn in (lambda x: I.atr(x, 14), lambda x: I.atr(x, 14, method="wilder"), I.session_vwap,
               lambda x: I.rolling_high(x, 20), lambda x: I.rolling_low(x, 20, include_current=False),
               lambda x: I.session_running_extremes(x), I.prior_session_levels,
               lambda x: I.opening_range(x, 8 * 60 + 45, 8 * 60 + 30)):
        assert truncation_test(fn, b) == []
        assert perturbation_test(fn, b, b.height // 2)


def test_session_extremes_are_running_not_final():
    b = _b()
    hi, lo = I.session_running_extremes(b)
    day = b.filter(pl.col("trade_date") == dt.date(2023, 3, 6))
    assert hi[0] == day["high"][0]
    assert hi[day.height - 1] == day["high"].max()
    assert not np.all(hi[: day.height] == day["high"].max())


def test_opening_range_unavailable_before_end():
    b = _b()
    orr = I.opening_range(b, 8 * 60 + 45, 8 * 60 + 30)
    # bars whose ts_close < 08:45 CT must have null OR
    assert orr["or_high"][:14].null_count() == 14
    assert orr["or_high"][14] is not None
    day = b.filter(pl.col("trade_date") == dt.date(2023, 3, 6)).slice(0, 15)
    assert orr["or_high"][14] == day["high"].max()


def test_pivots_known_only_after_confirmation():
    b = _b()
    piv = I.confirmed_pivots(b, 3, 3)
    assert (piv["confirmed_idx"] == piv["pivot_idx"] + 3).all()
    last = I.known_last_pivot(b, piv, "high")
    for row in piv.filter(pl.col("kind") == "high").iter_rows(named=True):
        k, ck = row["pivot_idx"], row["confirmed_idx"]
        # before confirmation the value must not be this pivot
        if k > 0 and not np.isnan(last[ck - 1]):
            assert last[ck - 1] != row["price"] or last[ck - 1] == last[ck - 2]
        assert last[ck] == row["price"]
    assert truncation_test(lambda x: I.known_last_pivot(x, I.confirmed_pivots(x, 3, 3), "high"), b) == []


def test_prior_session_levels_are_previous_day():
    b = _b()
    p = I.prior_session_levels(b)
    d1 = b.filter(pl.col("trade_date") == dt.date(2023, 3, 6))
    d2_first = d1.height
    assert p["pdh"][0] is None
    assert p["pdh"][d2_first] == d1["high"].max() and p["pdl"][d2_first] == d1["low"].min()
