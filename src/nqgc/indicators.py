"""Causal indicators. Every function returns values aligned to the input bars such that value[i]
uses ONLY bars[0..i] (information available at ts_close[i]). Structural indicators that need
future confirmation (pivots) return an explicit `confirmed_idx`/`confirmed_at`, and the
`known_*` helpers only expose a pivot from the bar at which it became known.

All functions are checked by tests/test_indicators_causal.py with the truncation test in leakage.py.
"""
from __future__ import annotations
import numpy as np
import polars as pl


def _reset_groups(bars: pl.DataFrame, reset_on: str | None) -> np.ndarray:
    if reset_on is None:
        return np.zeros(bars.height, dtype=np.int64)
    return bars[reset_on].rle_id().to_numpy().astype(np.int64)


def true_range(bars: pl.DataFrame, reset_on: str | None = "trade_date") -> np.ndarray:
    """TR[i] = max(H-L, |H-prevC|, |L-prevC|). prevC is not used across a reset boundary (new session/contract)."""
    h, l, c = bars["high"].to_numpy(), bars["low"].to_numpy(), bars["close"].to_numpy()
    grp = _reset_groups(bars, reset_on)
    prev_c = np.roll(c, 1)
    same = np.roll(grp, 1) == grp
    same[0] = False
    tr = h - l
    tr2 = np.where(same, np.maximum(np.abs(h - prev_c), np.abs(l - prev_c)), 0.0)
    return np.maximum(tr, tr2)


def atr(bars: pl.DataFrame, n: int, reset_on: str | None = "trade_date", method: str = "sma") -> np.ndarray:
    """ATR over the last n COMPLETED bars ending at bar i (inclusive). NaN until n bars exist."""
    tr = true_range(bars, reset_on)
    s = pl.Series(tr)
    if method == "sma":
        return s.rolling_mean(n).to_numpy()
    if method == "wilder":
        return s.ewm_mean(alpha=1.0 / n, adjust=False, min_samples=n).to_numpy()
    raise ValueError(method)


def sma(x: np.ndarray, n: int) -> np.ndarray:
    return pl.Series(x).rolling_mean(n).to_numpy()


def ema(x: np.ndarray, n: int) -> np.ndarray:
    return pl.Series(x).ewm_mean(span=n, adjust=False, min_samples=n).to_numpy()


def rolling_high(bars: pl.DataFrame, n: int, include_current: bool = True) -> np.ndarray:
    """Highest high of bars i-n+1..i (include_current) or i-n..i-1 (prior bars only)."""
    s = bars["high"].rolling_max(n)
    return (s if include_current else s.shift(1)).to_numpy()


def rolling_low(bars: pl.DataFrame, n: int, include_current: bool = True) -> np.ndarray:
    s = bars["low"].rolling_min(n)
    return (s if include_current else s.shift(1)).to_numpy()


def session_vwap(bars: pl.DataFrame, group: str = "trade_date") -> np.ndarray:
    """Cumulative volume-weighted price within each trade date, through bar i (uses bar_vwap if present, else HLC/3)."""
    px = bars["bar_vwap"] if "bar_vwap" in bars.columns else (bars["high"] + bars["low"] + bars["close"]) / 3
    df = bars.select(pl.col(group), (px * pl.col("volume")).alias("pv"), pl.col("volume").cast(pl.Float64).alias("v"))
    cum = df.with_columns(pl.col("pv").cum_sum().over(group), pl.col("v").cum_sum().over(group))
    return (cum["pv"] / cum["v"]).to_numpy()


def session_running_extremes(bars: pl.DataFrame, group: str = "trade_date") -> tuple[np.ndarray, np.ndarray]:
    """Session high/low SO FAR through bar i (never the final session high/low)."""
    hi = bars.select(pl.col("high").cum_max().over(group))["high"].to_numpy()
    lo = bars.select(pl.col("low").cum_min().over(group))["low"].to_numpy()
    return hi, lo


def prior_session_levels(bars: pl.DataFrame, group: str = "trade_date") -> pl.DataFrame:
    """For each bar, the PREVIOUS trade date's high/low/close/volume (fully known at this session's open).
    Returns columns [pdh, pdl, pdc, pdv] aligned to bars."""
    daily = (bars.group_by(group, maintain_order=True)
                 .agg(pl.max("high").alias("pdh"), pl.min("low").alias("pdl"), pl.last("close").alias("pdc"), pl.sum("volume").alias("pdv"))
                 .sort(group))
    daily = daily.with_columns([pl.col(c).shift(1) for c in ("pdh", "pdl", "pdc", "pdv")])
    return bars.select(group).join(daily, on=group, how="left").drop(group)


def opening_range(bars: pl.DataFrame, or_end_minutes_ct: int, or_start_minutes_ct: int, group: str = "trade_date") -> pl.DataFrame:
    """Opening-range high/low. The OR is defined over bars with CT open-time in [start, end).
    The values are exposed ONLY on bars whose ts_close is at/after the OR end (i.e. once the range is complete).
    Returns [or_high, or_low] aligned to bars (NaN before availability)."""
    from .calendar import ct_time_expr
    m_open = ct_time_expr("ts_open")
    m_close_prev = ct_time_expr("ts_close")   # minutes of ts_close
    b = bars.with_columns(m_open.alias("_mo"), m_close_prev.alias("_mc"))
    in_or = (pl.col("_mo") >= or_start_minutes_ct) & (pl.col("_mo") < or_end_minutes_ct)
    orh = pl.when(in_or).then(pl.col("high")).otherwise(None).cum_max().over(group)
    orl = pl.when(in_or).then(pl.col("low")).otherwise(None).cum_min().over(group)
    # availability: bar's ts_close >= OR end. ts_close minute == or_end or later within the same session and after OR start
    avail = (pl.col("_mc") >= or_end_minutes_ct) & (pl.col("_mo") >= or_start_minutes_ct)
    out = b.with_columns(pl.when(avail).then(orh).otherwise(None).alias("or_high"),
                         pl.when(avail).then(orl).otherwise(None).alias("or_low"))
    return out.select("or_high", "or_low")


def confirmed_pivots(bars: pl.DataFrame, left: int, right: int) -> pl.DataFrame:
    """Swing highs/lows requiring `left` lower bars before and `right` lower bars after.
    A pivot at bar k is only KNOWN at bar k+right. Returns
    [kind, pivot_idx, pivot_ts_open, price, confirmed_idx, confirmed_at] with confirmed_at = ts_close[k+right]."""
    h, l = bars["high"].to_numpy(), bars["low"].to_numpy()
    n = len(h)
    rows = []
    for k in range(left, n - right):
        if np.all(h[k] > h[k - left:k]) and np.all(h[k] >= h[k + 1:k + right + 1]):
            rows.append(("high", k, bars["ts_open"][k], float(h[k]), k + right, bars["ts_close"][k + right]))
        if np.all(l[k] < l[k - left:k]) and np.all(l[k] <= l[k + 1:k + right + 1]):
            rows.append(("low", k, bars["ts_open"][k], float(l[k]), k + right, bars["ts_close"][k + right]))
    return pl.DataFrame(rows, schema=["kind", "pivot_idx", "pivot_ts_open", "price", "confirmed_idx", "confirmed_at"], orient="row")


def known_last_pivot(bars: pl.DataFrame, pivots: pl.DataFrame, kind: str) -> np.ndarray:
    """For each bar i, the price of the most recently CONFIRMED pivot of `kind` (confirmed_idx <= i).
    This is the only leak-safe way to reference a swing level."""
    out = np.full(bars.height, np.nan)
    p = pivots.filter(pl.col("kind") == kind).sort("confirmed_idx")
    if p.is_empty():
        return out
    cidx = p["confirmed_idx"].to_numpy()
    price = p["price"].to_numpy()
    j = -1
    for i in range(bars.height):
        while j + 1 < len(cidx) and cidx[j + 1] <= i:
            j += 1
        if j >= 0:
            out[i] = price[j]
    return out
