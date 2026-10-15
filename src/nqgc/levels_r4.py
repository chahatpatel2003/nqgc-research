"""Causal rebuild of the nq-levels R4 level engine from raw front-contract prints.

Faithful to the frozen methodology (zones.py / interactions.py / p14_common.py of nq-levels) EXCEPT for the one
chronology fix: a zone becomes available only when the bar that confirms its pivot has COMPLETED.

Every zone carries pivot_ts (open of the pivot minute), confirm_ts (open of the confirmation minute) and
available_ts = confirm_ts + 60 s. No tap may occur at a second earlier than available_ts. Every tap is known at
tap_sec + 1 s; every R4 fire is decided at the end of the fire second (decision_ts = fire_sec + 1 s).

The engine is strictly online: `process_session(sd, ...)` only ever reads prefix data, so running it on prints
truncated at T reproduces exactly the zones/taps/fires whose availability/known time is <= T (tests/test_r4_causal.py).
"""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import polars as pl

TICK = 0.25
DEFAULT_PARAMS = dict(
    scales=(0.15, 0.35, 0.75),   # zigzag reversal thresholds in ATR units
    base_min=10,                 # bars before the pivot used for the base range
    hw_floor=1.0,                # half-width floor, points (4 ticks)
    hw_cap_atr=0.03,             # half-width cap, ATR fraction
    rearm_s=900,                 # min seconds between taps of one zone
    hyst_pts=2.0,                # re-arm: 1-min close outside the band by max(hyst_pts, hw)   (8 ticks)
    hyst_mult=1.0,               # diagnostic multiplier on the effective re-arm distance (1.0 = frozen)
    max_taps=6, max_age_sessions=30,
    r4_win=60,                   # seconds after the tap in which the velocity break must occur
    displacements=(8.0, 9.0, 10.0, 11.0, 12.0),   # R4 displacement grid (10.0 = original); diagnostics only
    n_fwd_min=1800,              # seconds of session that must remain after the tap
    atr_n=14, atr_min=5,
    dedup=True, dedup_s=600, dedup_atr=0.05,   # frozen universe rule: same session+side, within 600 s and 0.05 ATR of the previous tap -> duplicate
    t0_s=900, t0_filter=True,   # frozen universe rule (P6 corpus): tap >= t0_s+60 s into the session and the close at tap-t0_s-1 s OUTSIDE the band
)


@dataclass
class Zone:
    zid: int
    scale: int
    dir: int
    price_rf: float          # pivot price, roll-free (points)
    hw: float                # half width (points)
    pivot_ts: int            # epoch seconds, open of the pivot minute
    confirm_ts: int          # epoch seconds, open of the confirmation minute
    available_ts: int        # epoch seconds: confirm_ts + 60 (bar complete)
    form_ord: int
    form_session: dt.date
    base_range: float
    taps: int = 0
    armed: bool = True
    last_tap_ts: float = -np.inf
    retired: bool = False


@dataclass
class SessionData:
    date: dt.date
    symbol: str
    sec_ts: np.ndarray       # dense epoch seconds
    hi: np.ndarray
    lo: np.ndarray
    cl: np.ndarray
    has_print: np.ndarray
    m_ts: np.ndarray         # minute bar opens (epoch s) — only minutes with prints
    m_hi: np.ndarray
    m_lo: np.ndarray
    m_cl: np.ndarray
    m_op: np.ndarray
    vwap: np.ndarray         # cumulative session vwap per dense second (through that second)
    open_px: float
    rth_range: float         # high-low over 08:30-15:00 CT prints (for the NEXT sessions' ATR)
    close_px: float
    n_complete_min: int = 0  # minute bars [0:n_complete_min] are complete (zone creation uses only these)
    close_ts: int = 0        # SCHEDULED session close (epoch s) — a known schedule, used for n_fwd


def build_session(date: dt.date, symbol: str, ts_ns: np.ndarray, px: np.ndarray, size: np.ndarray, truncate_ns: int | None = None,
                  rth_utc: tuple[int, int] | None = None, close_ts: int = 0) -> Optional[SessionData]:
    """Dense 1-second arrays (ffilled closes; empty seconds get hi=lo=close) and 1-minute bars from prints.
    With truncate_ns, only COMPLETE seconds (second_end <= T) and COMPLETE minutes (minute_end <= T) are used."""
    if truncate_ns is not None:
        T_s = truncate_ns // 1_000_000_000
        keep = (ts_ns // 1_000_000_000) < T_s          # prints in seconds that ended at/before T
        ts_ns, px, size = ts_ns[keep], px[keep], size[keep]
    if len(ts_ns) < 10:
        return None
    sec = (ts_ns // 1_000_000_000).astype(np.int64)
    s0, s1 = int(sec[0]), int(sec[-1])
    n = s1 - s0 + 1
    idx = sec - s0
    # per-second OHLC via ufunc reductions
    hi = np.full(n, -np.inf); lo = np.full(n, np.inf); cl = np.full(n, np.nan)
    np.maximum.at(hi, idx, px); np.minimum.at(lo, idx, px)
    cl[idx] = px                                  # last assignment wins = last print in the second (prints sorted)
    has = ~np.isnan(cl)
    # forward-fill closes over empty seconds (from the PAST only); empty seconds get hi = lo = close
    idxs = np.where(has, np.arange(n), 0); np.maximum.accumulate(idxs, out=idxs); c = cl[idxs]
    hi = np.where(has, hi, c); lo = np.where(has, lo, c); cl = c
    sec_ts = s0 + np.arange(n, dtype=np.int64)
    # cumulative vwap per second
    pv = np.zeros(n); vv = np.zeros(n)
    np.add.at(pv, idx, px * size); np.add.at(vv, idx, size)
    cpv, cvv = np.cumsum(pv), np.cumsum(vv)
    vwap = np.where(cvv > 0, cpv / np.maximum(cvv, 1e-9), cl)
    # minute bars (minutes with prints). The last minute may be PARTIAL under truncation: it is kept for tap screening
    # (a tap is a second-level event) but excluded from zone creation via n_complete_min (confirmation needs the full bar).
    mkey = (sec // 60) * 60
    mkey_m, px_m = mkey, px
    um, first_idx = np.unique(mkey_m, return_index=True)
    n_complete = int(len(um)) if truncate_ns is None else int(np.sum((um + 60) <= T_s))
    m_hi = np.full(len(um), -np.inf); m_lo = np.full(len(um), np.inf)
    pos = np.searchsorted(um, mkey_m)
    np.maximum.at(m_hi, pos, px_m); np.minimum.at(m_lo, pos, px_m)
    m_op = px_m[first_idx]
    last_idx = np.r_[first_idx[1:] - 1, len(px_m) - 1]
    m_cl = px_m[last_idx]
    rth = np.nan
    if rth_utc is not None:
        a, b = rth_utc
        w = (sec >= a) & (sec < b)
        rth = float(px[w].max() - px[w].min()) if w.any() else np.nan
    return SessionData(date, symbol, sec_ts, hi, lo, cl, has, um.astype(np.int64), m_hi, m_lo, m_cl, m_op, vwap, float(px[0]), rth, float(px[-1]), n_complete, close_ts)


def zigzag_confirmed(hi: np.ndarray, lo: np.ndarray, threshold: float):
    """Verbatim port of nqlevels.features.zones.zigzag_confirmed: (i_pivot, price, +1/-1, i_confirm)."""
    n = hi.size
    if n == 0:
        return []
    piv = []
    up = None
    imax, imin = 0, 0
    for i in range(1, n):
        if hi[i] > hi[imax]:
            imax = i
        if lo[i] < lo[imin]:
            imin = i
        if up is None:
            if hi[i] - lo[imin] >= threshold:
                piv.append((imin, lo[imin], -1, i)); up, imax = True, i
                for j in range(imin, i + 1):
                    if hi[j] > hi[imax]:
                        imax = j
            elif hi[imax] - lo[i] >= threshold:
                piv.append((imax, hi[imax], +1, i)); up, imin = False, i
                for j in range(imax, i + 1):
                    if lo[j] < lo[imin]:
                        imin = j
        elif up:
            if hi[imax] - lo[i] >= threshold:
                piv.append((imax, hi[imax], +1, i)); up, imin = False, imax
                for j in range(imax, i + 1):
                    if lo[j] < lo[imin]:
                        imin = j
        else:
            if hi[i] - lo[imin] >= threshold:
                piv.append((imin, lo[imin], -1, i)); up, imax = True, imin
                for j in range(imin, i + 1):
                    if hi[j] > hi[imax]:
                        imax = j
    return piv


class R4Engine:
    def __init__(self, params: dict | None = None):
        self.p = dict(DEFAULT_PARAMS, **(params or {}))
        self.registry: dict[int, Zone] = {}
        self.next_zid = 0
        self.zones_out: list[dict] = []
        self.taps_out: list[dict] = []
        self.fires_out: list[dict] = []
        self.rth_hist: list[float] = []      # per-session RTH ranges, in session order (S-1 appended AFTER processing S)
        self.close_hist: list[float] = []

    # ---- volatility scale: mean RTH range of sessions S-15..S-2 (frozen double-shift), min 5 ----
    def atr_for_next(self) -> float:
        h = [x for x in self.rth_hist[:-1]][-self.p["atr_n"]:]   # drop the most recent session (S-1) -> S-2..S-15
        h = [x for x in h if np.isfinite(x)]
        return float(np.mean(h)) if len(h) >= self.p["atr_min"] else np.nan

    def make_zones(self, sd: SessionData, atr: float, adj: float, sess_ord: int) -> list[Zone]:
        out = []
        nc = sd.n_complete_min if sd.n_complete_min else sd.m_ts.size
        found = []
        for si, s_atr in enumerate(self.p["scales"]):
            for ip, px_, d, ic in zigzag_confirmed(sd.m_hi[:nc], sd.m_lo[:nc], s_atr * atr):
                found.append((ic, si, d, ip, px_))
        found.sort()                                  # ids in confirmation order -> prefix-stable under truncation
        for ic, si, d, ip, px_ in found:
            if True:
                a = max(0, ip - self.p["base_min"])
                base = float(sd.m_hi[a:ip + 1].max() - sd.m_lo[a:ip + 1].min())
                hw = float(np.clip(base / 2.0, self.p["hw_floor"], self.p["hw_cap_atr"] * atr))
                z = Zone(self.next_zid, si, d, float(px_) - adj, hw, int(sd.m_ts[ip]), int(sd.m_ts[ic]), int(sd.m_ts[ic]) + 60,
                         sess_ord, sd.date, base)
                self.next_zid += 1
                out.append(z)
                self.zones_out.append(dict(zid=z.zid, session=sd.date, scale=si, dir=d, price=float(px_), price_rf=z.price_rf, hw=hw,
                                           pivot_ts=z.pivot_ts, confirm_ts=z.confirm_ts, available_ts=z.available_ts, base_range=base, atr=atr))
        return out

    def process_session(self, sd: SessionData, adj: float, sess_ord: int, trend_up: Optional[bool], atr_pct: float, T_known: int | None = None):
        """One session. adj = roll adjustment of this session (points). T_known (epoch s): only emit taps/fires known at/before it."""
        p = self.p
        atr = self.atr_for_next()
        if np.isfinite(atr):
            for z in self.make_zones(sd, atr, adj, sess_ord):
                self.registry[z.zid] = z
        n_sec = sd.cl.size
        events = []
        zstate = {}
        for zid in sorted(self.registry):
            z = self.registry[zid]
            if z.retired or sess_ord - z.form_ord > p["max_age_sessions"]:
                z.retired = True
                continue
            zlo, zhi = z.price_rf - z.hw + adj, z.price_rf + z.hw + adj
            hyst = max(p["hyst_pts"], z.hw) * p["hyst_mult"]
            elig = sd.m_ts >= z.available_ts                       # minute open at/after the zone became available
            mask = (sd.m_lo <= zhi) & (sd.m_hi >= zlo) & elig
            out_m = ((sd.m_cl < zlo - hyst) | (sd.m_cl > zhi + hyst)) & elig
            cand = np.flatnonzero(mask)
            if not cand.size:
                if not z.armed and out_m.any():
                    z.armed = True
                continue
            armed, last_ts = z.armed, z.last_tap_ts
            taps_now = 0; last_tap_min = -1
            outs = np.flatnonzero(out_m); j_out = 0
            for m in cand:
                if not armed:
                    while j_out < outs.size and outs[j_out] <= last_tap_min:
                        j_out += 1
                    if j_out < outs.size and outs[j_out] < m:
                        armed = True
                if not armed or z.taps + taps_now >= p["max_taps"]:
                    continue
                if sd.m_ts[m] - last_ts < p["rearm_s"]:
                    continue
                s0 = int(np.searchsorted(sd.sec_ts, sd.m_ts[m])); s1 = int(np.searchsorted(sd.sec_ts, sd.m_ts[m] + 60))
                hit = np.flatnonzero((sd.lo[s0:s1] <= zhi) & (sd.hi[s0:s1] >= zlo))
                if not hit.size:
                    continue
                t = s0 + int(hit[0])
                if int(sd.sec_ts[t]) < z.available_ts:      # belt and braces: never before availability
                    continue
                events.append((t, zid, zlo, zhi, z.taps + taps_now + 1))
                armed = False; last_ts = float(sd.sec_ts[t]); last_tap_min = m; taps_now += 1
            if not armed and out_m[last_tap_min + 1:].any():
                armed = True
            zstate[zid] = (armed, last_ts, taps_now)
        # chronological; ties at the same second ordered oldest zone first (all known at the same instant)
        events.sort(key=lambda e: (e[0], self.registry[e[1]].available_ts, e[1]))
        prev_tap = None          # (tap_sec, mid, below) of the previous tap in the stream (kept or not) — chain clustering as frozen
        for t, zid, zlo, zhi, tap_no in events:
            z = self.registry[zid]
            tap_ts = int(sd.sec_ts[t])
            if T_known is not None and tap_ts + 1 > T_known:
                continue
            mid = (zlo + zhi) / 2.0
            p0 = sd.cl[t - 1] if t > 0 else sd.cl[0]
            below = p0 <= mid
            n_fwd = (sd.close_ts - tap_ts) if sd.close_ts else (n_sec - t)     # seconds to the SCHEDULED close (known in advance)
            has_t0 = t - p["t0_s"] >= 60
            inside_t0 = bool(has_t0 and (zlo <= sd.cl[t - p["t0_s"] - 1] <= zhi))
            t0_ok = (not p["t0_filter"]) or (has_t0 and not inside_t0)
            dup = False
            if p["dedup"] and prev_tap is not None and np.isfinite(atr):
                dup = (t - prev_tap[0] <= p["dedup_s"]) and (abs(mid - prev_tap[1]) <= p["dedup_atr"] * atr) and (below == prev_tap[2])
            prev_tap = (t, mid, below)
            row = dict(session=sd.date, zid=zid, tap_sec=t, tap_ts=tap_ts, tap_no=tap_no, scale=z.scale, dir=z.dir, zlo=zlo, zhi=zhi, hw=z.hw,
                       below=bool(below), n_fwd=int(n_fwd), age_min=(tap_ts - z.available_ts) / 60.0, age_sessions=sess_ord - z.form_ord,
                       atr=atr, atr_pct=atr_pct, dist_open_atr=(p0 - sd.open_px) / atr if np.isfinite(atr) else np.nan,
                       dist_vwap_atr=(p0 - sd.vwap[t - 1]) / atr if (t > 0 and np.isfinite(atr)) else np.nan,
                       travel_30m_atr=((p0 - sd.cl[max(0, t - 1800)]) / atr) if np.isfinite(atr) else np.nan,
                       trend_up=trend_up, dup=dup, t0_ok=t0_ok)
            self.taps_out.append(row)
            if dup or not t0_ok or not below or n_fwd < p["n_fwd_min"]:
                continue
            e = min(n_sec, t + p["r4_win"] + 1)
            rev = zlo - np.minimum.accumulate(sd.lo[t:e])
            for dsp in p["displacements"]:
                k = np.flatnonzero(rev >= dsp)
                if not k.size:
                    continue
                f = t + int(k[0])
                dec_ts = int(sd.sec_ts[f]) + 1
                if T_known is not None and dec_ts > T_known:
                    continue
                self.fires_out.append(dict(**row, displacement=dsp, fire_sec=f, fire_ts=int(sd.sec_ts[f]), fire_s=f - t, decision_ts=dec_ts, symbol=sd.symbol))
        # end-of-session state roll-up (as the frozen engine: counts applied after the session)
        for zid, (armed, last_ts, taps_now) in zstate.items():
            z = self.registry[zid]
            z.armed = armed; z.taps += taps_now
            if taps_now:
                z.last_tap_ts = last_ts
            if z.taps >= p["max_taps"]:
                z.retired = True
        for zid in list(self.registry):
            if self.registry[zid].retired:
                del self.registry[zid]

    def end_session(self, sd: SessionData):
        self.rth_hist.append(sd.rth_range); self.close_hist.append(sd.close_px)

    def frames(self):
        return (pl.DataFrame(self.zones_out, infer_schema_length=None) if self.zones_out else pl.DataFrame(),
                pl.DataFrame(self.taps_out, infer_schema_length=None) if self.taps_out else pl.DataFrame(),
                pl.DataFrame(self.fires_out, infer_schema_length=None) if self.fires_out else pl.DataFrame())
