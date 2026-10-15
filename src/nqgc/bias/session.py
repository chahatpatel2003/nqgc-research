"""Per-trade-date print handling for the pre-open bias project.

Everything that touches prints lives here. Two entry points:

* `pre_stats(dp, d, R20, ref_px)`  — statistics available at 09:29:59.999 ET on day `d`; the function truncates its
  input at the cutoff itself and reports the last timestamp it touched (`pre_max_ts`), which the builder audits.
* `post_stats(dp, d, close_ns, R20)` — statistics of the 09:30 → close window (targets and NEXT-day context only).

Window boundaries are ET wall-clock instants converted with zoneinfo (DST-safe). Sizes are contracts; `sgn` is the
aggressor side from Databento (`B` = buy aggressor → +1, `A` = sell aggressor → −1, `N` → 0).
"""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl

from nqgc.paths import CACHE_DIR

ET = ZoneInfo("America/New_York")
NS_SEC = 1_000_000_000
NS_MIN = 60 * NS_SEC
BIG_LOT = 10
SEQ_MINUTES = 930          # 18:00 ET (previous calendar day) → 09:30 ET = 15.5 h
PRE_WINDOWS = {"asia": (None, (2, 0)), "eu": ((2, 0), (8, 30)), "data": ((8, 30), (9, 0)), "last30": ((9, 0), (9, 30)),
               "pre4": ((4, 0), (9, 30)), "on": (None, (9, 30))}
WINDOW_KEYS = ("n", "first", "last", "high", "low", "ret_pts", "rng", "vwap", "vol", "buy", "sell", "imb", "big_imb", "rv", "nrev", "mean_size")


def et_ns(d: dt.date, h: int, m: int = 0, s: int = 0) -> int:
    return int(dt.datetime(d.year, d.month, d.day, h, m, s, tzinfo=ET).timestamp()) * NS_SEC


@dataclass
class DayPrints:
    date: dt.date
    symbol: str
    ts: np.ndarray    # int64 ns UTC, sorted (ts_event, sequence)
    px: np.ndarray    # float64
    size: np.ndarray  # int64
    sgn: np.ndarray   # int8

    def before(self, cutoff_ns: int) -> "DayPrints":
        """Physically truncated copy: prints with ts < cutoff_ns only."""
        k = int(np.searchsorted(self.ts, cutoff_ns, side="left"))
        return DayPrints(self.date, self.symbol, self.ts[:k].copy(), self.px[:k].copy(), self.size[:k].copy(), self.sgn[:k].copy())


_cache: dict = {}


def load_day(d: dt.date) -> DayPrints | None:
    mon = d.strftime("%Y-%m")
    if mon not in _cache:
        _cache.clear()
        p = CACHE_DIR / "nq_front_ticks" / f"{mon}.parquet"
        if not p.exists():
            return None
        _cache[mon] = pl.read_parquet(p).sort(["ts_event", "sequence"])
    t = _cache[mon].filter(pl.col("trade_date") == d)
    if t.is_empty():
        return None
    side = t["side"].to_numpy()
    sgn = np.where(side == "B", 1, np.where(side == "A", -1, 0)).astype(np.int8)
    return DayPrints(d, str(t["symbol"][0]), t["ts_event"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy(),
                     t["price"].to_numpy().astype(np.float64), t["size"].cast(pl.Int64).to_numpy(), sgn)


# ---------------------------------------------------------------- bar helpers
def minute_grid(ts: np.ndarray, px: np.ndarray, t0: int, t1: int, step_ns: int = NS_MIN):
    """Bars on [t0, t1): (print counts, closes). Close = last print at or before the bar end (forward-filled from
    earlier prints in the arrays, NaN if none)."""
    n = int((t1 - t0) // step_ns)
    if n <= 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0)
    edges = t0 + np.arange(n + 1, dtype=np.int64) * step_ns
    idx = np.searchsorted(ts, edges, side="left")
    cnt = np.diff(idx)
    last = idx[1:] - 1
    close = np.where(last >= 0, px[np.clip(last, 0, None)], np.nan)
    return cnt, close


def _last_at_or_before(ts: np.ndarray, px: np.ndarray, t: int) -> float:
    k = int(np.searchsorted(ts, t, side="right")) - 1
    return float(px[k]) if k >= 0 else np.nan


def n_reversals(c: np.ndarray, thr: float) -> float:
    """Number of zigzag reversals of at least `thr` points in a close series."""
    c = c[~np.isnan(c)]
    if c.size < 2 or not (thr > 0):
        return np.nan
    dirn = 0
    ext = c[0]
    start = c[0]
    n = 0
    for v in c[1:]:
        if dirn == 0:
            if v - start >= thr:
                dirn, ext = 1, v
            elif start - v >= thr:
                dirn, ext = -1, v
        elif dirn == 1:
            if v > ext:
                ext = v
            elif ext - v >= thr:
                n += 1
                dirn, ext = -1, v
        else:
            if v < ext:
                ext = v
            elif v - ext >= thr:
                n += 1
                dirn, ext = 1, v
    return float(n)


def _terminal_run(c: np.ndarray) -> float:
    """Signed length of the terminal run of same-sign changes in a close series (5-min bars)."""
    c = c[~np.isnan(c)]
    d = np.diff(c)
    d = d[d != 0]
    if d.size == 0:
        return 0.0
    s = np.sign(d[-1])
    k = 0
    for v in d[::-1]:
        if np.sign(v) == s:
            k += 1
        else:
            break
    return float(s * k)


def window_stats(dp: DayPrints, a: int, b: int, R20: float, prefix: str) -> dict:
    """Print statistics on [a, b)."""
    i0 = int(np.searchsorted(dp.ts, a, side="left"))
    i1 = int(np.searchsorted(dp.ts, b, side="left"))
    out = {f"{prefix}_{k}": np.nan for k in WINDOW_KEYS}
    out[f"{prefix}_n"] = float(i1 - i0)
    if i1 - i0 < 2:
        return out
    px = dp.px[i0:i1]
    sz = dp.size[i0:i1]
    sg = dp.sgn[i0:i1]
    vol = float(sz.sum())
    buy = float(sz[sg > 0].sum())
    sell = float(sz[sg < 0].sum())
    big = sz >= BIG_LOT
    bbuy = float(sz[big & (sg > 0)].sum())
    bsell = float(sz[big & (sg < 0)].sum())
    hi = float(px.max())
    lo = float(px.min())
    out.update({
        f"{prefix}_first": float(px[0]), f"{prefix}_last": float(px[-1]), f"{prefix}_high": hi, f"{prefix}_low": lo,
        f"{prefix}_ret_pts": float(px[-1] - px[0]), f"{prefix}_rng": hi - lo,
        f"{prefix}_vwap": float((px * sz).sum() / vol) if vol > 0 else np.nan,
        f"{prefix}_vol": vol, f"{prefix}_buy": buy, f"{prefix}_sell": sell,
        f"{prefix}_imb": (buy - sell) / (buy + sell) if buy + sell > 0 else np.nan,
        f"{prefix}_big_imb": (bbuy - bsell) / (bbuy + bsell) if bbuy + bsell > 0 else np.nan,
        f"{prefix}_mean_size": vol / (i1 - i0),
    })
    _, c5 = minute_grid(dp.ts[i0:i1], px, a, b, 5 * NS_MIN)
    c5 = c5[~np.isnan(c5)]
    r5 = np.diff(np.log(c5)) if c5.size > 1 else np.zeros(0)
    out[f"{prefix}_rv"] = float(np.sqrt((r5 ** 2).sum())) if r5.size else np.nan
    _, c1 = minute_grid(dp.ts[i0:i1], px, a, b, NS_MIN)
    out[f"{prefix}_nrev"] = n_reversals(c1, 0.25 * R20) if R20 == R20 else np.nan
    return out


# ---------------------------------------------------------------- pre-open statistics (available at 09:29:59.999 ET)
def pre_keys() -> list[str]:
    keys = ["pre_cutoff_ns", "pre_n", "pre_max_ts", "pre_session_start_ns", "pre_session_start_px", "pre_p0929", "pre_ts_last",
            "pre_on_high", "pre_on_low", "pre_on_min_since_high", "pre_on_min_since_low", "pre_p0830", "pre_p0835",
            "pre_on_coverage", "pre_on_share_above_ref", "pre_on_share_above_start", "pre_on_run5", "pre_on_max5m",
            "pre_on_seq_sum"]
    for w in PRE_WINDOWS:
        keys += [f"pre_{w}_{k}" for k in WINDOW_KEYS]
    return keys


def pre_stats(dp_in: DayPrints, d: dt.date, R20: float, ref_px: float) -> tuple[dict, np.ndarray]:
    """Statistics from prints strictly before 09:30:00.000 ET on `d`. Returns (dict, 1-min log-return sequence of
    length SEQ_MINUTES-1 over 18:00 → 09:30 ET, zero where no print)."""
    cutoff = et_ns(d, 9, 30)
    dp = dp_in.before(cutoff)
    out = {k: np.nan for k in pre_keys()}
    out["pre_cutoff_ns"] = float(cutoff)
    out["pre_n"] = float(dp.ts.size)
    out["pre_max_ts"] = float(dp.ts[-1]) if dp.ts.size else -1.0
    seq = np.zeros(SEQ_MINUTES - 1)
    if dp.ts.size < 100:
        return out, seq
    assert dp.ts[-1] < cutoff
    t_open = et_ns(d - dt.timedelta(days=1), 18, 0)
    t_start = int(dp.ts[0])
    for w, (a, b) in PRE_WINDOWS.items():
        a_ns = t_start if a is None else et_ns(d, *a)
        b_ns = et_ns(d, *b)
        out.update(window_stats(dp, a_ns, b_ns, R20, f"pre_{w}"))
    p = float(dp.px[-1])
    out["pre_session_start_ns"] = float(t_start)
    out["pre_session_start_px"] = float(dp.px[0])
    out["pre_p0929"] = p
    out["pre_ts_last"] = float(dp.ts[-1])
    i_hi = int(np.argmax(dp.px))
    i_lo = int(np.argmin(dp.px))
    out["pre_on_high"] = float(dp.px[i_hi])
    out["pre_on_low"] = float(dp.px[i_lo])
    out["pre_on_min_since_high"] = (cutoff - dp.ts[i_hi]) / NS_MIN
    out["pre_on_min_since_low"] = (cutoff - dp.ts[i_lo]) / NS_MIN
    out["pre_p0830"] = _last_at_or_before(dp.ts, dp.px, et_ns(d, 8, 30))
    out["pre_p0835"] = _last_at_or_before(dp.ts, dp.px, et_ns(d, 8, 35))
    cnt, c1 = minute_grid(dp.ts, dp.px, t_open, cutoff, NS_MIN)
    out["pre_on_coverage"] = float((cnt > 0).mean()) if cnt.size else np.nan
    ok = ~np.isnan(c1)
    out["pre_on_share_above_ref"] = float((c1[ok] > ref_px).mean()) if ok.any() and ref_px == ref_px else np.nan
    out["pre_on_share_above_start"] = float((c1[ok] > dp.px[0]).mean()) if ok.any() else np.nan
    lc = np.log(c1)
    r1 = np.diff(lc)
    r1[~np.isfinite(r1)] = 0.0
    seq[:] = r1
    out["pre_on_seq_sum"] = float(r1.sum())
    _, c5 = minute_grid(dp.ts, dp.px, t_open, cutoff, 5 * NS_MIN)
    out["pre_on_run5"] = _terminal_run(c5)
    d5 = np.diff(c5[~np.isnan(c5)])
    out["pre_on_max5m"] = float(np.abs(d5).max()) if d5.size else np.nan
    return out, seq


# ---------------------------------------------------------------- post-open statistics (targets / next-day context)
def post_keys() -> list[str]:
    keys = ["post_max_ts", "post_open_delay_s", "post_open", "post_close", "post_high", "post_low", "post_am_high", "post_am_low",
            "post_p1200", "post_p1500", "post_am_ret_pts", "post_pm_ret_pts", "post_last_hour_ret_pts", "post_rth_ret_pts",
            "post_am_rng", "post_rng", "post_mfe", "post_mae", "post_am_slope", "post_am_r2", "post_am_share_above_open",
            "post_rth_up_minute_share", "post_am_vol", "post_rth_vol", "post_last_hour_imb", "post_settle", "post_n_am",
            "post_fh25", "post_fh50", "post_fh25_min", "post_fh50_min"]
    keys += [f"post_pc_{k}" for k in WINDOW_KEYS]
    return keys


def _first_hit(px: np.ndarray, up: float, dn: float):
    iu = np.flatnonzero(px >= up)
    idn = np.flatnonzero(px <= dn)
    a = int(iu[0]) if iu.size else None
    b = int(idn[0]) if idn.size else None
    if a is None and b is None:
        return 0, None
    if b is None or (a is not None and a < b):
        return 1, a
    if a is None or b < a:
        return -1, b
    return 0, a  # same print (impossible unless R20 == 0)


def post_stats(dp: DayPrints, d: dt.date, close_ns: int, R20: float) -> dict:
    open_ns = et_ns(d, 9, 30)
    noon = et_ns(d, 12, 0)
    h15 = et_ns(d, 15, 0)
    h16 = et_ns(d, 16, 0)
    h17 = et_ns(d, 17, 0)
    ts, px, sz, sg = dp.ts, dp.px, dp.size, dp.sgn
    out = {k: np.nan for k in post_keys()}
    out["post_max_ts"] = float(ts[-1]) if ts.size else -1.0
    i0 = int(np.searchsorted(ts, open_ns, side="left"))
    i_noon = int(np.searchsorted(ts, noon, side="right"))
    i_close = int(np.searchsorted(ts, close_ns, side="right"))
    if i_close - i0 < 10 or i_noon - i0 < 10:
        return out
    O = float(px[i0])
    C = float(px[i_close - 1])
    seg = px[i0:i_close]
    am = px[i0:i_noon]
    H, L = float(seg.max()), float(seg.min())
    amH, amL = float(am.max()), float(am.min())
    P1200 = float(px[i_noon - 1])
    P1500 = _last_at_or_before(ts, px, h15) if h15 < close_ns else np.nan
    out.update({"post_open_delay_s": (ts[i0] - open_ns) / NS_SEC, "post_open": O, "post_close": C, "post_high": H, "post_low": L,
                "post_am_high": amH, "post_am_low": amL, "post_p1200": P1200, "post_p1500": P1500,
                "post_am_ret_pts": P1200 - O, "post_pm_ret_pts": C - P1200,
                "post_last_hour_ret_pts": (C - P1500) if P1500 == P1500 else np.nan, "post_rth_ret_pts": C - O,
                "post_am_rng": amH - amL, "post_rng": H - L, "post_mfe": amH - O, "post_mae": O - amL, "post_n_am": float(i_noon - i0)})
    _, c1 = minute_grid(ts[i0:i_noon], am, open_ns, noon, NS_MIN)
    ok = ~np.isnan(c1)
    if ok.sum() >= 30:
        x = np.arange(c1.size, dtype=float)[ok]
        y = c1[ok]
        slope, intercept = np.polyfit(x, y, 1)
        resid = y - (slope * x + intercept)
        sst = ((y - y.mean()) ** 2).sum()
        out["post_am_slope"] = float(slope)
        out["post_am_r2"] = float(1 - (resid ** 2).sum() / sst) if sst > 0 else 0.0
        out["post_am_share_above_open"] = float((y > O).mean())
    _, cr = minute_grid(ts[i0:i_close], seg, open_ns, close_ns, NS_MIN)
    okr = ~np.isnan(cr)
    out["post_rth_up_minute_share"] = float((cr[okr] > O).mean()) if okr.any() else np.nan
    out["post_am_vol"] = float(sz[i0:i_noon].sum())
    out["post_rth_vol"] = float(sz[i0:i_close].sum())
    if h15 < close_ns:
        j = int(np.searchsorted(ts, h15, side="left"))
        b = float(sz[j:i_close][sg[j:i_close] > 0].sum())
        s = float(sz[j:i_close][sg[j:i_close] < 0].sum())
        out["post_last_hour_imb"] = (b - s) / (b + s) if b + s > 0 else np.nan
    js = int(np.searchsorted(ts, close_ns - 30 * NS_SEC, side="left"))
    v = float(sz[js:i_close].sum())
    out["post_settle"] = float((px[js:i_close] * sz[js:i_close]).sum() / v) if v > 0 else C
    if R20 == R20 and R20 > 0:
        for k, name in ((0.25, "25"), (0.5, "50")):
            lab, idx = _first_hit(am, O + k * R20, O - k * R20)
            out[f"post_fh{name}"] = float(lab)
            out[f"post_fh{name}_min"] = (ts[i0 + idx] - open_ns) / NS_MIN if idx is not None else np.nan
    if close_ns >= h16:
        out.update(window_stats(dp, h16, h17, R20, "post_pc"))
    return out
