"""Contract identification and CAUSAL front-month selection.

NQ (individual contracts in the trades data)
-------------------------------------------
Front contract for trade date D = the outright with the highest traded volume on the most recent
COMPLETED trade date before D. This uses only information available before D opens. The first
trade date of the dataset has no prior day and is marked `bootstrap=True` (excluded from trading).
No back-adjustment is ever applied: a strategy day never mixes contracts, so there is no roll gap
inside a day; the roll gap between D-1 (old front) and D (new front) is flagged (`roll_day=True`)
so that any indicator spanning the boundary can be reset or the day excluded.

GC (Databento GC.v.0 continuous 1-minute bars)
---------------------------------------------
Only the vendor's volume-rolled continuous series exists on disk (no individual contracts).
The vendor roll takes effect at 00:00 UTC — i.e. INSIDE the Globex session (18:00/19:00 CT) — and is
unadjusted. We recover the segments from `instrument_id` changes and flag, per trade date:
  roll_switch_date : the trade date containing the 00:00 UTC switch (price jump inside the session)
  thin_last_day    : the last trade date of the outgoing segment (vendor lags one day; bars sparse)
Strategies must treat both as non-tradeable by default.
"""
from __future__ import annotations
import datetime as dt
import re

import polars as pl

OUTRIGHT_RE = re.compile(r"^(NQ|MNQ|GC|MGC)([FGHJKMNQUVXZ])(\d{1,2})$")
MONTH_CODES = "FGHJKMNQUVXZ"


def is_outright(symbol: str) -> bool:
    return bool(OUTRIGHT_RE.match(symbol))


def parse_symbol(symbol: str) -> tuple[str, int, int] | None:
    """-> (root, month 1-12, year 4-digit) or None for spreads / unknown. Year digits are
    resolved relative to 2020s: 'H1' -> 2021, 'H26' -> 2026."""
    m = OUTRIGHT_RE.match(symbol)
    if not m:
        return None
    root, mc, yy = m.groups()
    year = 2020 + int(yy) if len(yy) == 1 else 2000 + int(yy)
    return root, MONTH_CODES.index(mc) + 1, year


def nq_front_map(daily_volume: pl.DataFrame) -> pl.DataFrame:
    """daily_volume: columns [trade_date, symbol, volume] for OUTRIGHTS only, one row per (date, symbol).

    Returns one row per trade date: [trade_date, front, basis_date, basis_volume, roll_day, bootstrap].
    Causal by construction: the decision for date D uses the row set of the previous trade date only.
    Ties are broken by the earlier expiry (deterministic).
    """
    dv = daily_volume.filter(pl.col("symbol").map_elements(is_outright, return_dtype=pl.Boolean))
    dv = dv.with_columns(
        pl.col("symbol").map_elements(lambda s: parse_symbol(s)[2] * 100 + parse_symbol(s)[1], return_dtype=pl.Int64).alias("expiry_key"))
    best = (dv.sort(["trade_date", "volume", "expiry_key"], descending=[False, True, False])
              .group_by("trade_date", maintain_order=True).first()
              .select("trade_date", pl.col("symbol").alias("prev_best"), pl.col("volume").alias("basis_volume")))
    dates = dv.select("trade_date").unique().sort("trade_date")
    out = dates.join(best.with_columns(pl.col("trade_date").alias("basis_date")).select("basis_date", "prev_best", "basis_volume"),
                     how="cross").filter(pl.col("basis_date") < pl.col("trade_date"))
    out = out.sort(["trade_date", "basis_date"], descending=[False, True]).group_by("trade_date", maintain_order=True).first()
    out = dates.join(out, on="trade_date", how="left").rename({"prev_best": "front"})
    out = out.with_columns(
        pl.col("front").is_null().alias("bootstrap"),
        (pl.col("front") != pl.col("front").shift(1)).fill_null(False).alias("roll_day"),
    ).sort("trade_date")
    return out.select("trade_date", "front", "basis_date", "basis_volume", "roll_day", "bootstrap")


def gc_segments(bars: pl.DataFrame) -> pl.DataFrame:
    """From GC.v.0 bars with [ts_event, instrument_id], derive contiguous instrument segments.
    -> [instrument_id, t0, t1, n_bars]"""
    b = bars.sort("ts_event").with_columns(
        (pl.col("instrument_id") != pl.col("instrument_id").shift(1)).fill_null(True).cum_sum().alias("seg"))
    return (b.group_by("seg", maintain_order=True)
             .agg(pl.first("instrument_id"), pl.min("ts_event").alias("t0"), pl.max("ts_event").alias("t1"), pl.len().alias("n_bars"))
             .drop("seg"))


def gc_roll_flags(bars: pl.DataFrame) -> pl.DataFrame:
    """Per trade date flags for the continuous GC series. bars needs [ts_event, instrument_id, trade_date].
    -> [trade_date, instrument_ids, n_ids, roll_switch_date, thin_last_day]"""
    per_day = (bars.group_by("trade_date").agg(pl.col("instrument_id").unique().sort().alias("instrument_ids"),
                                              pl.col("instrument_id").n_unique().alias("n_ids"),
                                              pl.len().alias("n_bars")).sort("trade_date"))
    seg = gc_segments(bars)
    last_days = set()
    for row in seg.iter_rows(named=True):
        last_days.add((row["t1"].astimezone(dt.timezone.utc)))
    from .calendar import trade_date_of
    thin = {trade_date_of(t) for t in last_days}
    per_day = per_day.with_columns(
        (pl.col("n_ids") > 1).alias("roll_switch_date"),
        pl.col("trade_date").map_elements(lambda d: d in thin, return_dtype=pl.Boolean).alias("thin_last_day"),
    )
    return per_day
