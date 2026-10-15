"""Phase 3 execution: causal R4 fires -> tick engine, all original cells x cost tiers, per-year/per-phase metrics,
bootstrap CIs, Monte-Carlo drawdowns, cost sensitivity, parameter-neighbourhood surfaces (diagnostic), pattern tables.
Entry convention (frozen): order at the decision boundary (fire second end + k), FILL = the close of that next second
(last print inside second f+k+1); if that second has no print, the first later print. Stop/target relative to the fill.
Same-second stop/target tie -> STOP. One open trade. Session-end flatten at 16:00 CT. Holdout window never read."""
import datetime as dt, json, math, sys, time
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2"); sys.path.insert(0, "scripts/phase3")
import numpy as np, polars as pl
from common import load_day_ticks, nq_days, cost_for, ACCOUNT, freeze_or_load
from nqgc.execution import CostModel
from nqgc.tick_engine import TickExecutor, Intent
from nqgc.calendar import session_close_utc
from nqgc.stats import summary
from nqgc import diagnostics as dg
from nqgc.paths import RUNS_DIR, CONFIG_DIR, assert_writable_target

LEV = RUNS_DIR / "phase3" / "levels"; OUT = RUNS_DIR / "phase3"
CELLS = [("P14_ck2_S12.5_T30", 2, 12.5, 30.0)] + [(f"H2_ck0_S{s}_T{int(t)}", 0, s, t) for s in (15.0, 17.5, 20.0, 25.0) for t in (30.0, 40.0)]
TIERS = {"zero": CONFIG_DIR / "costs_gross.yaml", "base": CONFIG_DIR / "costs_base.yaml", "stress": CONFIG_DIR / "costs_stress.yaml", "stress2x": CONFIG_DIR / "costs_stress2x.yaml"}
SPEC_ID = json.load(open(LEV / "build_meta.json"))["spec_id"]
PHASES = {"development": (dt.date(2021, 1, 4), dt.date(2023, 12, 31)), "validation1": (dt.date(2024, 1, 1), dt.date(2024, 12, 31)), "validation2": (dt.date(2025, 1, 1), dt.date(2026, 6, 17))}
YEARS = {"2021": (dt.date(2021, 1, 1), dt.date(2021, 12, 31)), "2022": (dt.date(2022, 1, 1), dt.date(2022, 12, 31)), "2023": (dt.date(2023, 1, 1), dt.date(2023, 12, 31)),
         "2024": (dt.date(2024, 1, 1), dt.date(2024, 12, 31)), "2025": (dt.date(2025, 1, 1), dt.date(2025, 12, 31)), "2026H1": (dt.date(2026, 1, 1), dt.date(2026, 6, 17))}


class SecondCloseExecutor(TickExecutor):
    """Fill at the close of the second after the decision boundary (frozen convention)."""
    def run_day(self, trade_date, symbol, ts_ns, px, intents, session_label="RTH"):
        # emulate: signal at boundary B; fill = last print with ts in (B, B+1s]; else first print after B+1s.
        # Implemented by shifting the signal to (last print in (B, B+1s]) - 1ns when such a print exists.
        adj = []
        for it in intents:
            B = it.signal_ts_ns
            i0 = int(np.searchsorted(ts_ns, B, side="right")); i1 = int(np.searchsorted(ts_ns, B + 1_000_000_000, side="right"))
            if i1 > i0:
                it.signal_ts_ns = int(ts_ns[i1 - 1]) - 1           # the executor fills at the first print strictly after -> that close print
            else:
                it.signal_ts_ns = B + 1_000_000_000               # empty second: next legitimate print
            adj.append(it)
        return super().run_day(trade_date, symbol, ts_ns, px, adj, session_label)


def all_days():
    out = []
    for ph in PHASES:
        out += nq_days(ph, SPEC_ID, "phase3 R4 execution", exclude_early_close=False)
    return {x["date"]: x for x in out}


def intents_for_day(g: pl.DataFrame, k: int, S: float, T: float, close_ns: int) -> list:
    return [Intent(int((r["fire_ts"] + 1 + k) * 1e9), -1, 1, stop_offset=S, target_offset=T, exit_ts_ns=close_ns, tag=f"z{r['zid']}") for r in g.iter_rows(named=True)]


def run_many(configs: dict, fire_sets: dict, days: dict) -> dict:
    """configs: name -> (fireset_key, k, S, T, tier). One pass over the tick cache; one executor per config."""
    exs = {name: SecondCloseExecutor(CostModel.from_config("NQ", costs_path=TIERS[tier]), "NQ", name) for name, (_, _, _, _, tier) in configs.items()}
    by_day = {key: {d: g for (d,), g in f.filter(pl.col("tap_no") <= 3).sort(["session", "fire_ts"]).group_by(["session"], maintain_order=True)} for key, f in fire_sets.items()}
    for d in sorted(days):
        tk = load_day_ticks(d)
        if tk is None:
            continue
        ts, px, sym = tk
        close_ns = int(session_close_utc(d, "NQ").timestamp() * 1e9)
        for name, (fk, k, S, T, tier) in configs.items():
            g = by_day[fk].get(d)
            if g is None:
                continue
            exs[name].run_day(d, sym, ts, px, intents_for_day(g, k, S, T, close_ns))
    out = {}
    for name, ex in exs.items():
        led = ex.ledger()
        if led.is_empty():
            out[name] = led; continue
        fk = configs[name][0]
        meta = fire_sets[fk].filter(pl.col("tap_no") <= 3).select(pl.col("session").alias("trade_date"), pl.col("zid"), "tap_no", "scale", "age_min", "age_sessions", "atr", "atr_pct", "dist_open_atr", "dist_vwap_atr", "travel_30m_atr", "trend_up", "fire_s", "hw", "fire_ts", "tap_ts")
        led = led.with_columns(pl.col("tag").str.slice(1).cast(pl.Int64).alias("zid"))
        out[name] = led.join(meta, on=["trade_date", "zid"], how="left").unique(subset=["entry_ts", "zid"], keep="first").sort("entry_ts")
    return out


def metrics(led: pl.DataFrame, n_days: int) -> dict:
    if led.is_empty():
        return {"trades": 0}
    s = summary(led, ACCOUNT, n_trade_dates=n_days)
    r = led["r_multiple"].to_numpy(); r = r[~np.isnan(r)]
    m, lo, hi = dg.bootstrap_mean_ci(r) if len(r) > 1 else (float("nan"),) * 3
    gross_r = float((led["gross_usd"] / (led["init_stop"] - led["entry_px"]).abs() / 20.0).sum()) if led.height else float("nan")
    mc = dg.mc_drawdown(r) if len(r) > 1 else {}
    eqR = np.cumsum(r); ddR = float(np.max(np.maximum.accumulate(np.concatenate([[0], eqR])) - np.concatenate([[0], eqR]))) if len(r) else float("nan")
    return dict(trades=s["trades"], win_rate=s["win_rate"], expR=s["avg_r"], expR_ci=[lo, hi], pf=s["profit_factor"], gross_R=gross_r, net_R=float(r.sum()),
                net_usd=s["net_pnl"], maxdd_R=ddR, maxdd_usd=s["max_drawdown_usd"], avg_win=s["avg_winner"], avg_loss=s["avg_loser"], max_win=s["largest_winner"], max_loss=s["largest_loser"],
                sharpe=s["sharpe_daily_ann"], sortino=s["sortino_daily_ann"], hold_min=s["avg_hold_minutes"], streak_loss=s["consecutive_losses"], streak_win=s["consecutive_wins"],
                pct_months=dg.pct_profitable(led, "month"), pct_quarters=dg.pct_profitable(led, "quarter"), pct_years=dg.pct_profitable(led, "year"),
                mc_dd_R={k: mc.get(k) for k in ("p50", "p90", "p95", "p99", "historical")}, trades_per_day=s["trades_per_day"])


def per_window(led, dates):
    per = {}
    for name, (a, b) in {**YEARS, **PHASES, "full": (dates[0], dates[-1])}.items():
        sub = led.filter((pl.col("trade_date") >= a) & (pl.col("trade_date") <= b)) if not led.is_empty() else led
        per[name] = metrics(sub, sum(1 for d in dates if a <= d <= b))
    return per


def main():
    t0 = time.time()
    days = all_days(); dates = sorted(days)
    fire_sets = {"base": pl.read_parquet(LEV / "base_fires.parquet")}
    for var in ("nodedup", "thr_x0.8", "thr_x1.2", "hyst_x0.5", "hyst_x1.5", "rearm_600", "rearm_1200"):
        p = LEV / f"{var}_fires.parquet"
        if p.exists():
            fire_sets[var] = pl.read_parquet(p)
    fsets = {}
    for key, f in fire_sets.items():
        for dsp in (8.0, 9.0, 10.0, 11.0, 12.0):
            if key == "base" or dsp == 10.0:
                fsets[f"{key}@{dsp}"] = f.filter(pl.col("displacement") == dsp)
    results = {"spec_id": SPEC_ID, "cells": {}, "cost_tiers": {}, "neighbourhood": {}, "meta": {}}
    for tier, path in TIERS.items():
        c = CostModel.from_config("NQ", costs_path=path)
        rt = 2 * c.fee_per_side + 2 * c.slippage_ticks["market"] * 5.0
        results["cost_tiers"][tier] = dict(fees_usd_rt=2 * c.fee_per_side, slip_ticks_side=c.slippage_ticks["market"], total_usd_rt=rt, total_pts_rt=rt / 20.0)
    configs = {}
    for cell, k, S, T in CELLS:
        for tier in TIERS:
            configs[f"{cell}|{tier}"] = ("base@10.0", k, S, T, tier)
    for cell, k, S, T in (CELLS[0], CELLS[1]):
        for dsp in (8.0, 9.0, 11.0, 12.0):
            configs[f"NB|{cell}|displacement|{dsp}"] = (f"base@{dsp}", k, S, T, "base")
        for S2 in (S - 2.5, S + 2.5):
            configs[f"NB|{cell}|stop|{S2}"] = ("base@10.0", k, S2, T, "base")
        for T2 in (T - 5.0, T + 5.0):
            configs[f"NB|{cell}|target|{T2}"] = ("base@10.0", k, S, T2, "base")
        for var in ("nodedup", "thr_x0.8", "thr_x1.2", "hyst_x0.5", "hyst_x1.5", "rearm_600", "rearm_1200"):
            if f"{var}@10.0" in fsets:
                configs[f"NB|{cell}|level|{var}"] = (f"{var}@10.0", k, S, T, "base")
    print("configs", len(configs), "days", len(dates), flush=True)
    leds = run_many(configs, fsets, days)
    print("executed", f"{time.time()-t0:.0f}s", flush=True)
    for name, led in leds.items():
        parts = name.split("|")
        if parts[0] != "NB":
            cell, tier = parts
            results["cells"].setdefault(cell, {})[tier] = per_window(led, dates)
            if not led.is_empty():
                led.write_parquet(OUT / f"trades_{cell}_{tier}.parquet")
        else:
            _, cell, kind, val = parts
            results["neighbourhood"].setdefault(cell, {}).setdefault(kind, {})[val] = {n: per_window(led, dates)[n] for n in list(PHASES) + ["full"]}
    for cell, k, S, T in (CELLS[0], CELLS[1]):   # the original values inside each neighbourhood, for the tables
        results["neighbourhood"][cell]["displacement"]["10.0"] = {n: results["cells"][cell]["base"][n] for n in list(PHASES) + ["full"]}
        results["neighbourhood"][cell]["stop"][str(S)] = results["neighbourhood"][cell]["displacement"]["10.0"]
        results["neighbourhood"][cell]["target"][str(T)] = results["neighbourhood"][cell]["displacement"]["10.0"]
        results["neighbourhood"][cell]["level"]["base"] = results["neighbourhood"][cell]["displacement"]["10.0"]
    results["meta"] = dict(n_days=len(dates), first=str(dates[0]), last=str(dates[-1]), secs=time.time() - t0)
    (OUT / "results.json").write_text(json.dumps(results, indent=1, default=str))
    for cell in results["cells"]:
        print(cell, {t: {n: (v[n]["trades"], round(v[n].get("expR", float("nan")), 3), round(v[n].get("pf", float("nan")), 2)) for n in ("development", "validation1", "validation2", "full")} for t, v in results["cells"][cell].items()})
    print("DONE", round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
