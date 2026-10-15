"""R4 P14 cell: decompose OLD-vs-NEW differences on the old comparison window (2022-01-01 .. 2026-06-17, all unlocked phases).
Variants: (1) OLD evaluator (1-s grids, 1.0 pt flat); (2) NEW gross + TOUCH target rule (closest to old fills);
(3) NEW gross + THROUGH target rule; (4) NEW base (fees + 1 tick/side); (5) NEW stress. Each also reported minus 1.0 pt flat."""
import datetime as dt, json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, pandas as pd, polars as pl
from common import *
from nqgc.tick_engine import TickExecutor, Intent
from nqgc.calendar import session_close_utc
from strat_A_r4 import FIRE, SPEC_ID, old_engine, old_summary

k, S, T = 2, 12.5, 30.0
fire = pd.read_parquet(FIRE); fire["session"] = fire["session"].astype(str)
fire = fire[(fire["tap_no"] <= 3) & fire["ck2_epx"].notna()].copy(); fire["date"] = pd.to_datetime(fire["session"]).dt.date
days = []
for ph in NQ_PHASES:
    days += nq_days(ph, SPEC_ID, "R4 decomposition", exclude_early_close=False)
days = [x for x in days if x["date"] >= dt.date(2022, 1, 1)]
dset = {x["date"] for x in days}
f = fire[fire["date"].isin(dset)]
out = {"window": "2022-01-01..2026-06-17", "n_days": len(days), "n_fires_tap3": int(len(f))}
o = old_engine(f, k, S, T); out["OLD_1pt"] = old_summary(o)
o0 = old_engine(f, k, S, T, cost_pts=0.0); out["OLD_0cost"] = old_summary(o0)
yr = o.assign(year=pd.to_datetime(o["session"]).dt.year).groupby("year")["R"].agg(["count", "mean"]); out["OLD_1pt_by_year"] = yr.to_dict("index")


def run(cost, name):
    ex = TickExecutor(cost, "NQ", name)
    for x in days:
        fd = f[f["date"] == x["date"]]
        if fd.empty:
            continue
        tk = load_day_ticks(x["date"])
        if tk is None:
            continue
        ts, px, sym = tk
        close_ns = int(session_close_utc(x["date"], "NQ").timestamp() * 1e9)
        ex.run_day(x["date"], sym, ts, px, [Intent(int((r.tap_ts + r.fire_s + 1 + k) * 1e9), -1, 1, stop_offset=S, target_offset=T, exit_ts_ns=close_ns, tag=name) for r in fd.itertuples()])
    led = ex.ledger()
    s = summary(led, ACCOUNT, n_trade_dates=len(days))
    r = led["r_multiple"].to_numpy(); n = led["net_usd"].to_numpy()
    res = dict(n=s["trades"], expR=s["avg_r"], pf=s["profit_factor"], wr=s["win_rate"], pts=s.get("gross_pnl", 0) / 20.0, net_usd=s["net_pnl"],
               exits=led.group_by("exit_reason").len().to_dicts(), skipped=len(ex.skipped),
               expR_minus_1pt=float(np.nanmean(r - 1.0 / S)))
    led = led.with_columns(pl.col("entry_ts").dt.year().alias("year"))
    res["by_year_expR"] = {int(y): float(v) for y, v in led.group_by("year").agg(pl.mean("r_multiple")).sort("year").iter_rows()}
    return res, led


g = cost_for("NQ", "gross"); g.limit_fill_rule = "touch"
out["NEW_gross_touch"], led_touch = run(g, "gross_touch")
out["NEW_gross_through"], led_thr = run(cost_for("NQ", "gross"), "gross_through")
out["NEW_base"], led_base = run(cost_for("NQ", "base"), "base")
out["NEW_stress"], _ = run(cost_for("NQ", "stress"), "stress")
# trade-level pairing OLD vs NEW(gross, touch): match by (session, zid, tap_sec) not carried in ledger -> compare counts and exit mix only
d = assert_writable_target(OUT / "A_R4"); d.mkdir(exist_ok=True, parents=True)
(d / "decomposition_P14cell.json").write_text(json.dumps(out, indent=1, default=str))
led_touch.write_parquet(d / "decomp_trades_gross_touch.parquet"); led_thr.write_parquet(d / "decomp_trades_gross_through.parquet"); led_base.write_parquet(d / "decomp_trades_base.parquet")
print(json.dumps(out, indent=1, default=str))
