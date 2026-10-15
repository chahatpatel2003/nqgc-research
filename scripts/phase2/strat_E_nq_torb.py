"""STRATEGY E — NQ 1-minute TORB (Tsai et al., IEEE Access 2019; rules as specified for this task).
Opening range = prints with 09:30:00 <= ts < 09:31:00 ET on the front contract: OR_HIGH = max, OR_LOW = min.
After 09:31:00 ET the first print strictly ABOVE OR_HIGH -> long signal; strictly BELOW OR_LOW -> short; whichever first.
Signal time = that print's ts_event; entry at the next print strictly after (+ slippage). Exit at the last print at/before
16:00:00 ET (- slippage). One trade/day. No stop, target, or filters. Early-close days excluded."""
import datetime as dt, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl
from common import *
from nqgc.tick_engine import TickExecutor, Intent

RULES = open(__file__).read().split('"""')[1]
SPEC_ID = freeze_or_load("NQ_TORB_1min", "1.0-paper", "NQ", 0, RULES, dict(or_window="09:30:00-09:31:00 ET", exit="16:00 ET"), "H-E")


def main():
    spec = dict(name="NQ_TORB_1min", version="1.0-paper", spec_id=SPEC_ID, rules=RULES)
    per_phase = {}; ledgers = {}; notes = ["GROSS/BASE/STRESS cost tiers as configured.", "Breakout print must be strictly beyond the range; signal = that print's timestamp; fill = next print."]
    for phase in NQ_PHASES:
        days = nq_days(phase, SPEC_ID, "NQ TORB", exclude_early_close=True)
        all_days = [x["date"] for x in days]
        sig = []
        for x in days:
            d = x["date"]; tk = load_day_ticks(d)
            if tk is None:
                continue
            ts, px, sym = tk
            a, b, c = et_ns(d, "09:30"), et_ns(d, "09:31"), et_ns(d, "16:00")
            i0, i1 = np.searchsorted(ts, a, "left"), np.searchsorted(ts, b, "left")
            if i1 <= i0:
                continue
            orh, orl = float(px[i0:i1].max()), float(px[i0:i1].min())
            seg = px[i1:]; segts = ts[i1:]
            up = np.flatnonzero(seg > orh); dn = np.flatnonzero(seg < orl)
            cand = []
            if up.size: cand.append((int(up[0]), 1))
            if dn.size: cand.append((int(dn[0]), -1))
            if not cand:
                continue
            j, side = min(cand)
            if segts[j] >= c:
                continue
            sig.append((d, sym, side, int(segts[j]), orh, orl, ts, px))
        tiers = {}
        for tier in ("gross", "base", "stress"):
            ex = TickExecutor(cost_for("NQ", tier), "NQ", "NQ_TORB")
            for d, sym, side, sts, orh, orl, ts, px in sig:
                ex.run_day(d, sym, ts, px, [Intent(sts, side, 1, exit_ts_ns=et_ns(d, "16:00"), tag="torb", meta=dict(orh=orh, orl=orl))])
            led = ex.ledger(); ledgers[f"{phase}_{tier}"] = led
            tiers[tier] = evaluate(led, all_days, daily_ctx_nq(days) if tier == "base" else pl.DataFrame(), r_defined=False)
            print(phase, tier, {k: round(tiers[tier]["summary"].get(k, float("nan")), 3) for k in ("trades", "win_rate", "expectancy_usd", "net_pnl", "profit_factor", "sharpe_daily_ann")}, flush=True)
        per_phase[phase] = tiers
    save("E_NQ_TORB", spec, per_phase, ledgers, notes, "STRATEGY E — NQ 1-minute TORB")


if __name__ == "__main__":
    main()
