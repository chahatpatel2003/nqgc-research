"""STRATEGY D — GC rest-of-day -> last-30-minute momentum (Baltussen et al. 2021; paper Table 1: COMEX GC 8:20-13:30 EST).
GC is 1-minute OHLCV only. Conventions (documented, conservative):
  previous_close = close of the last COMPLETED 1-min bar with ts_close <= 13:30:00 ET on the previous eligible trade date
  P(13:00)       = close of the last completed bar with ts_close <= 13:00:00 ET (i.e. the 12:59 bar; known at 13:00:00)
  entry          = OPEN of the first bar with ts_open >= 13:00:00 ET (the next executable trade), + slippage
  exit           = CLOSE of the last bar with ts_close <= 13:30:00 ET (final price at/before the boundary), - slippage
Long if r_ROD>0, short if <0, none if 0. One trade/day, no stop/target. Roll-switch dates, thin roll days, data holes and
early-close dates are excluded (configs/calendar_observed_GC.yaml). The 13:00->13:01 bar close is never used at 13:00."""
import datetime as dt, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl
from common import *
from nqgc.engine import Trade
from dataclasses import asdict

RULES = open(__file__).read().split('"""')[1]
SPEC_ID = freeze_or_load("GC_ROD_last30", "1.0-paper", "GC", 60, RULES, dict(window="08:20-13:30 ET", rod_end="13:00 ET", exit="13:30 ET"), "H-D")


def main():
    spec = dict(name="GC_ROD_last30", version="1.0-paper", spec_id=SPEC_ID, rules=RULES)
    per_phase = {}; ledgers = {}
    notes = ["Bar-based; entry at next bar open, exit at last completed bar close before the boundary; costs per tier.", "GC 2025 locked (not run)."]
    for phase in GC_PHASES:
        days, bars = gc_days(phase, SPEC_ID, "GC ROD momentum")
        bars = bars.with_columns(pl.col("ts_open").dt.cast_time_unit("ns").cast(pl.Int64).alias("o_ns"), pl.col("ts_close").dt.cast_time_unit("ns").cast(pl.Int64).alias("c_ns"))
        byday = {d: g for (d,), g in bars.group_by(["trade_date"], maintain_order=True)}
        all_dates = sorted(byday)
        sig = []
        for d in days:
            prev = max([c for c in all_dates if c < d], default=None)
            if prev is None:
                continue
            g = byday[d]; pg = byday[prev]
            pc = pg.filter(pl.col("c_ns") <= et_ns(prev, "13:30"))
            if pc.is_empty():
                continue
            prev_close = float(pc["close"][-1])
            s = g.filter(pl.col("c_ns") <= et_ns(d, "13:00"))
            e = g.filter(pl.col("o_ns") >= et_ns(d, "13:00"))
            x = g.filter(pl.col("c_ns") <= et_ns(d, "13:30"))
            if s.is_empty() or e.is_empty() or x.is_empty() or int(x["c_ns"][-1]) <= int(e["o_ns"][0]):
                continue
            p1300 = float(s["close"][-1]); r = p1300 / prev_close - 1.0
            side = 1 if r > 0 else (-1 if r < 0 else 0)
            if side == 0:
                continue
            ent = e.row(0, named=True); ext = x.row(-1, named=True)
            path = g.filter((pl.col("o_ns") >= ent["o_ns"]) & (pl.col("c_ns") <= ext["c_ns"]))
            sig.append((d, side, r, ent, ext, float(path["high"].max()), float(path["low"].min()), path.height))
        tiers = {}
        for tier in ("gross", "base", "stress"):
            cost = cost_for("GC", tier); rows = []
            for d, side, r, ent, ext, hi, lo, nb in sig:
                epx = cost.fill_market(ent["open"], side); xpx = cost.fill_market(ext["close"], -side)
                pts = (xpx - epx) * side; gross = cost.pnl_points_to_usd(pts, 1); fees = cost.fees(1, 2)
                mfe = (hi - epx) if side > 0 else (epx - lo); mae = (epx - lo) if side > 0 else (hi - epx)
                rows.append(Trade("GC_ROD", "GC", "GC.v.0", side, 1, ent["ts_open"], ent["ts_open"], ext["ts_close"], 0, nb, epx, xpx, "market", "time", None, None,
                                  pts, gross, fees, cost.pnl_points_to_usd(2 * cost.slip("market"), 1), gross - fees, float("nan"), max(mae, 0), max(mfe, 0), nb,
                                  (ext["ts_close"] - ent["ts_open"]).total_seconds() / 60, False, False, d, "RTH", "rod"))
            led = pl.DataFrame([asdict(t) for t in rows]) if rows else pl.DataFrame(schema={k: pl.Null for k in Trade.__dataclass_fields__})
            ledgers[f"{phase}_{tier}"] = led
            tiers[tier] = evaluate(led, days, daily_ctx_gc(bars) if tier == "base" else pl.DataFrame(), r_defined=False)
            print(phase, tier, {k: round(tiers[tier]["summary"].get(k, float("nan")), 3) for k in ("trades", "win_rate", "expectancy_usd", "net_pnl", "profit_factor", "sharpe_daily_ann")}, flush=True)
        per_phase[phase] = tiers
    save("D_GC_ROD", spec, per_phase, ledgers, notes, "STRATEGY D — GC ROD -> last 30 min momentum")


if __name__ == "__main__":
    main()
