"""Time-zone, trade-date and session logic. All timestamps are tz-aware UTC internally.

Verified facts (docs/TIMEZONE_SESSIONS.md): both Databento datasets store UTC nanoseconds;
Globex opens 17:00 America/Chicago (23:00 UTC in winter, 22:00 UTC in summer). DST is handled by
zoneinfo — no fixed offsets anywhere in this package.
"""
from __future__ import annotations
import datetime as dt
from functools import lru_cache
from zoneinfo import ZoneInfo

import polars as pl
import yaml

from .paths import CONFIG_DIR

CT = ZoneInfo("America/Chicago")
ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
TRADE_DATE_SHIFT = dt.timedelta(hours=7)   # 17:00 CT + 7h = 00:00 next day


@lru_cache
def load_sessions() -> dict:
    with open(CONFIG_DIR / "sessions.yaml") as f:
        return yaml.safe_load(f)


def _hm(s: str) -> dt.time:
    h, m = s.split(":")
    return dt.time(int(h), int(m))


def trade_date_of(ts: dt.datetime) -> dt.date:
    """CME trade date for one tz-aware timestamp."""
    if ts.tzinfo is None:
        raise ValueError("naive timestamp — all timestamps must be tz-aware")
    return (ts.astimezone(CT) + TRADE_DATE_SHIFT).date()


def trade_date_expr(col: str = "ts_event") -> pl.Expr:
    """Polars expression: CME trade date from a UTC datetime column."""
    return (pl.col(col).dt.convert_time_zone("America/Chicago") + pl.duration(hours=7)).dt.date()


def ct_time_expr(col: str = "ts_event") -> pl.Expr:
    """Polars expression: minutes-since-midnight in CT (0..1439) — used for session labelling."""
    c = pl.col(col).dt.convert_time_zone("America/Chicago")
    return c.dt.hour().cast(pl.Int32) * 60 + c.dt.minute().cast(pl.Int32)


def session_label_expr(instrument: str, col: str = "ts_event") -> pl.Expr:
    """Label each timestamp with the configured session name (ASIA/EUROPE/RTH/POST) or MAINT."""
    cfg = load_sessions()[instrument]["sessions"]
    m = ct_time_expr(col)
    expr = pl.lit("MAINT")
    for name, (a, b) in cfg.items():
        ta, tb = _hm(a), _hm(b)
        ma, mb = ta.hour * 60 + ta.minute, tb.hour * 60 + tb.minute
        cond = ((m >= ma) & (m < mb)) if ma < mb else ((m >= ma) | (m < mb))   # wraps midnight
        expr = pl.when(cond).then(pl.lit(name)).otherwise(expr)
    return expr


def is_rth_expr(instrument: str, col: str = "ts_event") -> pl.Expr:
    a, b = load_sessions()[instrument]["rth"]
    ta, tb = _hm(a), _hm(b)
    m = ct_time_expr(col)
    return (m >= ta.hour * 60 + ta.minute) & (m < tb.hour * 60 + tb.minute)


def session_open_utc(trade_date: dt.date, instrument: str = "NQ") -> dt.datetime:
    """UTC timestamp of the Globex open for a trade date (17:00 CT on the previous calendar day)."""
    o = _hm(load_sessions()[instrument]["globex_open"])
    local = dt.datetime.combine(trade_date - dt.timedelta(days=1), o, tzinfo=CT)
    return local.astimezone(UTC)


def session_close_utc(trade_date: dt.date, instrument: str = "NQ", early_close: str | None = None) -> dt.datetime:
    c = _hm(early_close) if early_close else _hm(load_sessions()[instrument]["globex_close"])
    local = dt.datetime.combine(trade_date, c, tzinfo=CT)
    return local.astimezone(UTC)


def ct_wallclock_to_utc(trade_date: dt.date, hhmm: str, instrument: str = "NQ") -> dt.datetime:
    """Map a CT wall-clock time on a trade date to UTC, honouring that 17:00-23:59 belongs to the prior calendar day."""
    t = _hm(hhmm)
    open_t = _hm(load_sessions()[instrument]["globex_open"])
    cal_date = trade_date - dt.timedelta(days=1) if t >= open_t else trade_date
    return dt.datetime.combine(cal_date, t, tzinfo=CT).astimezone(UTC)


# ---- observed calendar (built from the data by scripts/build_calendar.py) -----------------------
@lru_cache
def load_observed_calendar(instrument: str) -> dict:
    p = CONFIG_DIR / f"calendar_observed_{instrument}.yaml"
    if not p.exists():
        return {"trade_dates": [], "holidays": [], "early_closes": {}, "data_holes": []}
    with open(p) as f:
        cal = yaml.safe_load(f)
    ov = CONFIG_DIR / "calendar_overrides.yaml"
    if ov.exists():
        with open(ov) as f:
            o = yaml.safe_load(f) or {}
        for k, v in (o.get(instrument) or {}).items():
            if isinstance(cal.get(k), dict):
                cal[k].update(v)
            elif isinstance(cal.get(k), list):
                cal[k] = sorted(set(cal[k]) | set(v))
    return cal
