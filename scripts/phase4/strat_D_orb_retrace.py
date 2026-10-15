"""D — NQ ORB retracement / volume-profile (dws-data/nas-orb-backtester, commit 03b28ee). See docs/phase4/SPEC_D_ORB_RETRACE_VP.md.
REPO-FAITHFUL: 1-min bars from front prints, entry at the touched VP level, stop/target at exact levels, zero cost.
CORRECTED: tick engine, limit entry filled only on trade-through by >= 1 tick, stop at/through + slippage, target through, four cost tiers.
Variant grid = repo grid: thresholds {10,15,20,25,30} % of ORB size x entry level {VAH, POC, VAL}, stop = ORB extreme, target = ORB extreme + 1.0 x ORB size.
ALL cells reported; none selected."""
import datetime as dt, json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl
import common as C
from common import *
from nqgc.bars import bars_from_trades
from nqgc.engine import Trade
from nqgc.tick_engine import TickExecutor, Intent
from nqgc.execution import CostModel
from dataclasses import asdict
C.OUT = RUNS_DIR / "phase4"
THRESHOLDS = (10, 15, 20, 25, 30); LEVELS = ("vah", "poc", "val")
RULES = open(__file__).read().split('"""')[1]
SPEC_ID = freeze_or_load("NQ_ORB_retrace_VP", "1.0-repo-03b28ee", "NQ", 60, RULES, dict(orb="09:30-09:45 ET", vp_rows=24, value_area=0.70, thresholds=list(THRESHOLDS), levels=list(LEVELS), stop="orb_extreme", target="orb_extreme+1.0*orb_size", spread=0, buffer=0, force_close="16:00 ET"), "H-D4")


def volume_profile(hi, lo, vol, num_rows=24):
    """Verbatim port of backtest/volume_profile.py (even spread over rows, POC, 70 % value area, row mid-points)."""
    low_floor, high_ceil = lo.min(), hi.max()
    bs = (high_ceil - low_floor) / num_rows
    if bs <= 0:
        return None
    va = np.zeros(num_rows)
    for i in range(len(lo)):
        if hi[i] <= lo[i] or vol[i] <= 0:
            continue
        a = max(0, int(np.floor((lo[i] - low_floor) / bs))); b = min(num_rows - 1, int(np.floor((hi[i] - low_floor) / bs)))
        if a > b:
            continue
        va[a:b + 1] += vol[i] / (b - a + 1)
    poc = int(np.argmax(va)); tot = va.sum(); target = 0.70 * tot; up = lo_i = poc; acc = va[poc]
    while acc < target:
        cu, cd = up < num_rows - 1, lo_i > 0
        if not cu and not cd:
            break
        nu = va[up + 1] if cu else 0.0; nd = va[lo_i - 1] if cd else 0.0
        if cu and (not cd or nu >= nd):
            up += 1; acc += nu
        else:
            lo_i -= 1; acc += nd
    buckets = low_floor + np.arange(num_rows + 1) * bs
    return dict(poc=float(buckets[poc] + bs / 2), vah=float(buckets[up] + bs / 2), val=float(buckets[lo_i] + bs / 2))


def day_context(d, ts, px, sz, sym):
    a, b = et_ns(d, "09:30"), et_ns(d, "16:00")
    i0, i1 = np.searchsorted(ts, a, "left"), np.searchsorted(ts, b, "left")
    if i1 - i0 < 500:
        return None
    t = pl.DataFrame({"ts_event": pl.from_epoch(pl.Series(ts[i0:i1]), time_unit="ns").dt.replace_time_zone("UTC"), "symbol": [sym] * (i1 - i0), "price": px[i0:i1], "size": sz[i0:i1], "sequence": np.arange(i1 - i0, dtype=np.uint32)})
    bars = bars_from_trades(t, 60, "NQ")
    o_ns = bars["ts_open"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy(); c_ns = bars["ts_close"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy()
    orb_end = et_ns(d, "09:45"); trade_start = et_ns(d, "09:46")
    orb = bars.filter((pl.col("ts_open") >= pl.lit(dt.datetime.fromtimestamp(a / 1e9, dt.timezone.utc))) & (pl.col("ts_open") < pl.lit(dt.datetime.fromtimestamp(orb_end / 1e9, dt.timezone.utc))))
    if orb.height < 10:
        return None
    oh, ol = float(orb["high"].max()), float(orb["low"].min()); size = oh - ol
    if size <= 0:
        return None
    vp = volume_profile(orb["high"].to_numpy(), orb["low"].to_numpy(), orb["volume"].to_numpy().astype(float))
    if vp is None:
        return None
    vah = min(vp["vah"], oh); poc = max(ol, min(vp["poc"], oh)); val = max(vp["val"], ol)
    post = bars.filter(pl.col("ts_open").dt.cast_time_unit("ns").cast(pl.Int64) >= trade_start)
    if post.is_empty():
        return None
    pc, ph, pl_, pts_o, pts_c = post["close"].to_numpy(), post["high"].to_numpy(), post["low"].to_numpy(), post["ts_open"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy(), post["ts_close"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy()
    def first_true(m):
        j = int(np.argmax(m)) if m.size else 0
        return j if (m.size and m[j]) else len(m)
    li, si = first_true(pc > oh), first_true(pc < ol); n = len(pc)
    if li == n and si == n:
        return None
    direction = 1 if li <= si else -1
    return dict(oh=oh, ol=ol, size=size, vah=vah, poc=poc, val=val, dir=direction, pc=pc, ph=ph, pl=pl_, o_ns=pts_o, c_ns=pts_c, ts=ts, px=px, sym=sym, first_true=first_true)


def main():
    days = nq_days("development", None, "phase4 D", exclude_early_close=True) + nq_days("validation1", SPEC_ID, "phase4 D", exclude_early_close=True) + nq_days("validation2", SPEC_ID, "phase4 D", exclude_early_close=True)
    all_dates = [x["date"] for x in days]
    cells = [(t, lv) for t in THRESHOLDS for lv in LEVELS]
    faithful = {c: [] for c in cells}
    tick_ex = {(c, tier): TickExecutor(cost_for("NQ", tier), "NQ", f"D_{c[0]}_{c[1]}_{tier}") for c in cells for tier in TIERS}
    ctx_days = 0
    for x in days:
        d = x["date"]; tk = load_day_ticks_full(d)
        if tk is None:
            continue
        ts, px, sz, sym = tk
        ctx = day_context(d, ts, px, sz, sym)
        if ctx is None:
            continue
        ctx_days += 1
        s = ctx["dir"]; oh, ol, size = ctx["oh"], ctx["ol"], ctx["size"]
        close_ns = et_ns(d, "16:00")
        for t, lv in cells:
            thr = size * t / 100.0
            conf = ctx["first_true"](ctx["pc"] >= oh + thr) if s > 0 else ctx["first_true"](ctx["pc"] <= ol - thr)
            n = len(ctx["pc"])
            if conf >= n:
                continue
            level = ctx[lv]
            stop = ol if s > 0 else oh
            target = oh + size if s > 0 else ol - size
            # ---- corrected tick intent: signal at the confirmation bar close ----
            sig = int(ctx["c_ns"][conf])
            for tier in TIERS:
                tick_ex[((t, lv), tier)].run_day(d, sym, ts, px, [Intent(sig, s, 1, stop=stop, target=target, entry_limit=level, exit_ts_ns=close_ns, tag=f"{t}_{lv}")])
            # ---- repo-faithful bar replica ----
            after_lo, after_hi = ctx["pl"][conf + 1:], ctx["ph"][conf + 1:]
            m = (after_lo <= level) if s > 0 else (after_hi >= level)
            e = ctx["first_true"](m)
            if e >= len(m):
                continue
            ei = conf + 1 + e
            entry = level
            xl, xh, xc = ctx["pl"][ei:], ctx["ph"][ei:], ctx["pc"][ei:]
            stop_m = (xl <= stop) if s > 0 else (xh >= stop)
            tgt_m = (xh >= target) if s > 0 else (xl <= target)
            tgt_m = tgt_m.copy(); tgt_m[0] = False
            sp, tp = ctx["first_true"](stop_m), ctx["first_true"](tgt_m); mlen = len(xl)
            if min(sp, tp) < mlen:
                if sp <= tp:
                    xi, xp, reason = sp, stop, "stop"
                else:
                    xi, xp, reason = tp, target, "target"
            else:
                xi, xp, reason = mlen - 1, float(xc[-1]), "time"
            pts = (xp - entry) * s
            ent_ts = dt.datetime.fromtimestamp(ctx["o_ns"][ei] / 1e9, dt.timezone.utc); ex_ts = dt.datetime.fromtimestamp(ctx["c_ns"][ei + xi] / 1e9, dt.timezone.utc)
            path_h, path_l = xh[:xi + 1].max(), xl[:xi + 1].min()
            faithful[(t, lv)].append(Trade("D_faithful", "NQ", sym, s, 1, dt.datetime.fromtimestamp(sig / 1e9, dt.timezone.utc), ent_ts, ex_ts, ei, ei + xi, entry, xp, "limit", reason, stop, target,
                                          pts, pts * 20.0, 0.0, 0.0, pts * 20.0, pts / abs(entry - stop) if abs(entry - stop) > 0 else float("nan"),
                                          max((entry - path_l) if s > 0 else (path_h - entry), 0), max((path_h - entry) if s > 0 else (entry - path_l), 0), xi, (ex_ts - ent_ts).total_seconds() / 60, False, False, d, "RTH", f"{t}_{lv}"))
    results = {"spec_id": SPEC_ID, "n_days_with_direction": ctx_days, "cells": {}}
    ledgers = {}
    ctx_nq = daily_ctx_nq(days)
    for c in cells:
        name = f"T{c[0]}_{c[1]}"
        results["cells"][name] = {}
        fl = pl.DataFrame([asdict(t) for t in faithful[c]]) if faithful[c] else pl.DataFrame()
        per = {}
        for ph in NQ_PHASES:
            lo, hi = Access(ph, "NQ", spec_id=SPEC_ID if ph != "development" else None, purpose="phase4 D eval").window()
            dl = [d for d in all_dates if lo <= d <= hi]
            sub = fl.filter((pl.col("trade_date") >= lo) & (pl.col("trade_date") <= hi)) if not fl.is_empty() else fl
            per[ph] = {"faithful_zero": evaluate(sub, dl, pl.DataFrame())}
            for tier in TIERS:
                led = tick_ex[(c, tier)].ledger()
                led = led.filter((pl.col("trade_date") >= lo) & (pl.col("trade_date") <= hi)) if not led.is_empty() else led
                per[ph][f"corrected_{tier}"] = evaluate(led, dl, ctx_nq if tier == "base" else pl.DataFrame())
                ledgers[f"{name}_{ph}_corrected_{tier}"] = led
            ledgers[f"{name}_{ph}_faithful"] = sub
        results["cells"][name] = per
        print(name, {ph: (per[ph]["faithful_zero"]["summary"].get("trades"), round(per[ph]["faithful_zero"]["summary"].get("avg_r", float("nan")), 3), "|corr base", per[ph]["corrected_base"]["summary"].get("trades"), round(per[ph]["corrected_base"]["summary"].get("avg_r", float("nan")), 3), round(per[ph]["corrected_base"]["summary"].get("profit_factor", float("nan")), 2)) for ph in NQ_PHASES}, flush=True)
    out = assert_writable_target(C.OUT / "D_NQ_ORB_retrace"); out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=1, default=str))
    for k, led in ledgers.items():
        if led is not None and not led.is_empty():
            led.write_parquet(out / f"trades_{k}.parquet")
    print("DONE")


if __name__ == "__main__":
    main()
