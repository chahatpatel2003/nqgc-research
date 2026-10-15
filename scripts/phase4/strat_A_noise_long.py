"""STRATEGY F — Noise-Area intraday momentum, LONG ONLY (Zarattini, Aziz, Barbon 2024, 'Beat the Market', SSRN 4824172).
Equations recovered from the paper text (audit/zarattini2024.txt):
  move_{t-i,HH:MM} = |Close_{t-i,HH:MM} / Open_{t-i,09:30} - 1|,  i = 1..14 (previous 14 eligible sessions)
  sigma_{t,HH:MM}  = (1/14) * sum_i move_{t-i,HH:MM}
  UB_{t,HH:MM} = max(Open_{t,09:30}, Close_{t-1,16:00}) * (1 + sigma_{t,HH:MM})
  LB_{t,HH:MM} = min(Open_{t,09:30}, Close_{t-1,16:00}) * (1 - sigma_{t,HH:MM})
  Trading only at semi-hourly checks HH:00 / HH:30 (first check 10:00 ET, last 15:30 ET), using the last completed 1-min close.
  LONG when flat and price > UB at a check (short side deliberately not traded).
  Final-model trailing stop (paper §3): Long TrailingStop = max(UB_{t,HH:MM}, VWAP_{t,HH:MM}); VWAP from market hours only
  (09:30 ET onward, cumulative, causal). Paper: 'Stop losses can also be triggered only on semi-hourly intervals' -> the stop is
  evaluated at the semi-hourly checks; exit when price < max(UB, VWAP). Re-entry at a later check is allowed when the entry
  condition holds again (paper does not forbid it; trade counts in the paper exceed one per day).
  All positions closed at the market close: 16:00 ET boundary (last completed 1-min bar close, 15:59 bar).
  Execution: decisions at bar close, fills at the next 1-min bar open + slippage (engine default). Sizing: 1 contract
  (the paper's vol-targeted share count is a sizing rule, not a signal rule; omitted and documented).
Bars: 1-min bars from front-contract ticks, 09:30-16:00 ET only. Days: all NQ trade dates with a 16:00 ET close; the first
14 eligible sessions of a phase serve only as sigma warm-up (no trades) — sigma history does NOT cross phase boundaries."""
import datetime as dt, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl
from common import *
from nqgc.bars import bars_from_trades, check_bar_semantics
from nqgc.engine import Backtester, EngineConfig
from nqgc.execution import Order
from nqgc.risk import PropFirmRules
from nqgc import indicators as I

RULES = open(__file__).read().split('"""')[1]
SPEC_ID = freeze_or_load("NQ_NoiseArea_long", "1.0-paper", "NQ", 60, RULES, dict(lookback_days=14, checks="HH:00/HH:30 10:00-15:30 ET", stop="max(UB,VWAP) at checks", close="16:00 ET", side="long only"), "H-F")


class NoiseLong:
    name = "NQ_NoiseArea_long"
    def __init__(self, ub, vwap, is_check):
        self.ub, self.vwap, self.chk = ub, vwap, is_check
    def on_bar(self, ctx):
        i = ctx.i
        if not self.chk[i] or np.isnan(self.ub[i]):
            return None
        px = ctx.last("close")
        if ctx.position is None:
            if px > self.ub[i]:
                return [Order(side=1, qty=1, tag="entry")]
        else:
            if px < max(self.ub[i], self.vwap[i]):
                return [Order(side=-1, qty=1, tag="exit")]
        return None


def build_day_bars(d, ts, px, sz, sym):
    a, b = et_ns(d, "09:30"), et_ns(d, "16:00")
    i0, i1 = np.searchsorted(ts, a, "left"), np.searchsorted(ts, b, "left")
    if i1 - i0 < 100:
        return None
    t = pl.DataFrame({"ts_event": pl.from_epoch(pl.Series(ts[i0:i1]), time_unit="ns").dt.replace_time_zone("UTC"), "symbol": [sym] * (i1 - i0),
                      "price": px[i0:i1], "size": sz[i0:i1], "sequence": np.arange(i1 - i0, dtype=np.uint32)})
    return bars_from_trades(t, 60, "NQ")


def main():
    spec = dict(name="NQ_NoiseArea_long", version="1.0-paper", spec_id=SPEC_ID, rules=RULES)
    per_phase = {}; ledgers = {}
    notes = ["Bar engine: signal at the check bar close, fill at next bar open + slippage; flatten at the 16:00 ET boundary bar close.",
             "VWAP = cumulative sum(price*size)/sum(size) over market-hours prints from 09:30 ET, evaluated at each bar close."]
    for phase in NQ_PHASES:
        days = nq_days(phase, SPEC_ID, "NQ noise area long", exclude_early_close=True)
        cal_dates = [dt.date.fromisoformat(s) for s in nq_cal()["trade_dates"]]
        hist = []      # list of (minute_of_day -> abs move) dicts for the previous eligible sessions
        day_frames = []; prev_close_cache = {}
        for x in days:
            d = x["date"]; tk = load_day_ticks_full(d)
            if tk is None:
                continue
            ts, px, sz, sym = tk
            b = build_day_bars(d, ts, px, sz, sym)
            if b is None:
                continue
            open_px = float(b["open"][0])
            mod = b.select((pl.col("ts_close").dt.convert_time_zone("America/New_York").dt.hour().cast(pl.Int32) * 60 + pl.col("ts_close").dt.convert_time_zone("America/New_York").dt.minute().cast(pl.Int32)).alias("m"))["m"].to_numpy()
            closes = b["close"].to_numpy()
            # previous close (16:00 ET of previous trade date, same contract)
            prev = max([c for c in cal_dates if c < d], default=None)
            pc = None
            if prev is not None:
                pk = load_day_ticks(prev)
                if pk is not None and pk[2] == sym:
                    pc, _ = last_print_at_or_before(pk[0], pk[1], et_ns(prev, "16:00"))
                else:
                    key = (sym, prev)
                    if key not in prev_close_cache:
                        prev_close_cache[key] = print_at_or_before_raw(sym, dt.datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=ET))
                    pc = prev_close_cache[key]
            if len(hist) >= 14 and pc is not None:
                sig = np.full(len(mod), np.nan)
                for j, m in enumerate(mod):
                    vals = [h.get(int(m)) for h in hist[-14:]]
                    vals = [v for v in vals if v is not None]
                    if len(vals) == 14:
                        sig[j] = float(np.mean(vals))
                ub = max(open_px, pc) * (1 + sig)
                is_check = (mod % 30 == 0) & (mod >= 600) & (mod <= 930)
                vwap = I.session_vwap(b)
                day_frames.append((d, b, ub, vwap, is_check))
            hist.append({int(m): abs(c / open_px - 1) for m, c in zip(mod, closes)})
        tiers = {}
        rules = PropFirmRules(account_size=ACCOUNT, flatten_by="15:00", max_contracts={"NQ": 10})   # 15:00 CT = 16:00 ET boundary
        for tier in TIERS:
            cost = cost_for("NQ", tier); parts = []
            for d, b, ub, vwap, chk in day_frames:
                bb = b.with_columns(pl.lit(True).alias("tradeable"))
                bt = Backtester(bb, NoiseLong(ub, vwap, chk), cost, rules, EngineConfig(instrument="NQ"))
                t = bt.run()
                if not t.is_empty():
                    parts.append(t)
            led = pl.concat(parts) if parts else pl.DataFrame()
            ledgers[f"{phase}_{tier}"] = led
            tiers[tier] = evaluate(led, [f[0] for f in day_frames], daily_ctx_nq(days) if tier == "base" else pl.DataFrame(), r_defined=False)
            print(phase, tier, {k: round(tiers[tier]["summary"].get(k, float("nan")), 3) for k in ("trades", "win_rate", "expectancy_usd", "net_pnl", "profit_factor", "sharpe_daily_ann")}, flush=True)
        per_phase[phase] = tiers
    import common as _c; _c.OUT = RUNS_DIR / "phase4"; save("A_NQ_NoiseLong", spec, per_phase, ledgers, notes, "PHASE 4 A — NQ Noise-Area momentum, long only (4 cost tiers, outlier attribution)")


if __name__ == "__main__":
    main()
