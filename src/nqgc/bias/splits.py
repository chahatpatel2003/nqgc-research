"""Phase-5 splits (configs/splits_bias.yaml) and the per-phase list of CME trade dates with calendar flags."""
from __future__ import annotations
import datetime as dt
from functools import lru_cache

import polars as pl
import yaml

from nqgc.calendar import load_observed_calendar
from nqgc.guard import Access
from nqgc.paths import CACHE_DIR, CONFIG_DIR, RUNS_DIR

SPLITS_BIAS = CONFIG_DIR / "splits_bias.yaml"
OUT = RUNS_DIR / "phase5"


def load_splits_bias() -> dict:
    with open(SPLITS_BIAS) as f:
        return yaml.safe_load(f)


def bias_access(phase: str, spec_id: str | None = None, purpose: str = "", unlock: str | None = None) -> Access:
    return Access(phase, "NQ", spec_id=spec_id, unlock=unlock, purpose=purpose, splits=load_splits_bias())


@lru_cache
def nq_cal() -> dict:
    return load_observed_calendar("NQ")


@lru_cache
def front_map() -> dict:
    fm = pl.read_parquet(CACHE_DIR / "nq_front_map.parquet")
    return {r["trade_date"]: r for r in fm.iter_rows(named=True)}


@lru_cache
def roll_adj() -> dict:
    r = pl.read_parquet(CACHE_DIR / "nq_roll_adjust.parquet")
    return {row["session"]: float(row["adj"]) for row in r.iter_rows(named=True)}


def _close_ct(v) -> tuple[int, int]:
    """Early-close entries are CT wall-clock; PyYAML may parse an unquoted 08:15 as the sexagesimal int 495."""
    if isinstance(v, int):
        return divmod(v, 60)
    h, m = str(v).split(":")
    return int(h), int(m)


def all_trade_dates() -> list[dt.date]:
    return [dt.date.fromisoformat(s) for s in nq_cal()["trade_dates"]]


def session_days(phase: str, spec_id: str | None = None, purpose: str = "", unlock: str | None = None) -> list[dict]:
    """Every CME trade date inside the phase window, with calendar flags. Nothing is excluded here: eligibility is
    decided from the data in the daily builder, so that non-eligible sessions still provide context."""
    acc = bias_access(phase, spec_id, purpose, unlock)
    lo, hi = acc.window()
    cal = nq_cal()
    fm = front_map()
    partial = {p["trade_date"] for p in cal.get("partial_sessions", [])}
    holes = {h["trade_date"] for h in cal.get("data_holes", [])}
    early = cal.get("early_closes", {})
    out = []
    for s in cal["trade_dates"]:
        d = dt.date.fromisoformat(s)
        if d < lo or d > hi or d not in fm:
            continue
        ec = early.get(s)
        close_ct = _close_ct(ec) if ec is not None else (15, 0)  # regular equity-index futures RTH close 15:00 CT = 16:00 ET
        out.append(dict(date=d, front=fm[d]["front"], roll_day=bool(fm[d]["roll_day"]), bootstrap=bool(fm[d]["bootstrap"]),
                        early_close=ec is not None, close_ct=close_ct, partial=s in partial, hole=s in holes,
                        holiday_session=ec is not None and close_ct <= (12, 0), half_day=ec is not None and close_ct > (12, 0)))
    return out
