"""STRATEGY C — NQ rest-of-day -> last-30-minute momentum (Baltussen, Da, Lammers, Martens, JFE 2021).
Market window 09:30-16:00 ET (paper Table 1: NQ 9:30-16:00 EST). previous_close = last print at/before 16:00:00 ET on the
previous trade date for TODAY's front contract (roll days: targeted raw query for the new front). r_ROD = P(15:30)/prev_close - 1
where P(15:30) = last print at/before 15:30:00 ET (known at the boundary). Signal at the 15:30:00 boundary; entry at the first
print strictly after it (+ slippage); exit at the last print at/before 16:00:00 ET (- slippage). Long if r_ROD>0, short if <0,
none if 0. One trade/day, no stop, no target, no filters. Early-close days (no 16:00 ET window) excluded."""
import datetime as dt, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl
from common import *
from nqgc.tick_engine import TickExecutor, Intent

RULES = open(__file__).read().split('"""')[1]
SPEC_ID = freeze_or_load("NQ_ROD_last30", "1.0-paper", "NQ", 0, RULES, dict(window="09:30-16:00 ET", rod_end="15:30 ET", exit="16:00 ET", threshold=0.0), "H-C")


def main():
    spec = dict(name="NQ_ROD_last30", version="1.0-paper", spec_id=SPEC_ID, rules=RULES)
    per_phase = {}; ledgers = {}; notes = ["GROSS: no fees/slippage. BASE: fees + 1 tick/side. STRESS: fees + 3 ticks/side.", "Days: all NQ trade dates in the phase with a 16:00 ET close (early closes, partial and hole days excluded)."]
    prev_cache = {}
    for phase in NQ_PHASES:
        days = nq_days(phase, SPEC_ID, "NQ ROD momentum", exclude_early_close=True)
        all_days = [x["date"] for x in days]
        # previous-close lookup needs the previous TRADE DATE (any, incl. early close) for today's front
        cal_dates = [dt.date.fromisoformat(s) for s in nq_cal()["trade_dates"]]
        sig = []
        for x in days:
            d = x["date"]
            prev = max([c for c in cal_dates if c < d], default=None)
            if prev is None:
                continue
            tk = load_day_ticks(d)
            if tk is None:
                continue
            ts, px, sym = tk
            pk = load_day_ticks(prev)
            pc = None
            if pk is not None and pk[2] == sym:
                pc, _ = last_print_at_or_before(pk[0], pk[1], et_ns(prev, "16:00"))
            else:
                key = (sym, prev)
                if key not in prev_cache:
                    prev_cache[key] = print_at_or_before_raw(sym, dt.datetime(prev.year, prev.month, prev.day, 16, 0, tzinfo=ET))
                pc = prev_cache[key]
            if pc is None:
                continue
            p1530, _ = last_print_at_or_before(ts, px, et_ns(d, "15:30"))
            if p1530 is None:
                continue
            r = p1530 / pc - 1.0
            side = 1 if r > 0 else (-1 if r < 0 else 0)
            sig.append((d, sym, side, r, pc, p1530, ts, px))
        tiers = {}
        for tier in ("gross", "base", "stress"):
            ex = TickExecutor(cost_for("NQ", tier), "NQ", "NQ_ROD")
            for d, sym, side, r, pc, p1530, ts, px in sig:
                if side == 0:
                    continue
                ex.run_day(d, sym, ts, px, [Intent(et_ns(d, "15:30"), side, 1, exit_ts_ns=et_ns(d, "16:00"), tag="rod", meta=dict(r_rod=r))])
            led = ex.ledger(); ledgers[f"{phase}_{tier}"] = led
            tiers[tier] = evaluate(led, all_days, daily_ctx_nq(days) if tier == "base" else pl.DataFrame(), r_defined=False)
            print(phase, tier, {k: round(tiers[tier]["summary"].get(k, float("nan")), 3) for k in ("trades", "win_rate", "expectancy_usd", "net_pnl", "profit_factor", "sharpe_daily_ann")}, flush=True)
        per_phase[phase] = tiers
    save("C_NQ_ROD", spec, per_phase, ledgers, notes, "STRATEGY C — NQ ROD -> last 30 min momentum")


if __name__ == "__main__":
    main()
