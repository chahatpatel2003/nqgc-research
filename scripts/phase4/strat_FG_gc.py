"""F — GC fifth-half-hour -> last-half-hour intraday momentum (Wen et al. 2020 / Gao et al. 2018 construction), and
G — GC Crabel Stretch opening-range breakout (08:20-13:30 ET day session). Both on 1-minute bars with the Phase-2 GC conventions:
entry at the next bar open (+slippage), time exits at the last completed bar close (-slippage), same-minute stop/target -> worst case.
See docs/phase4/SPEC_F_GC_INTRADAY_MOMENTUM.md and SPEC_G_GC_CRABEL_ORB.md."""
import datetime as dt, json, sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2")
import numpy as np, polars as pl
import common as C
from common import *
from nqgc.engine import Trade
from dataclasses import asdict
C.OUT = RUNS_DIR / "phase4"
RULES = open(__file__).read().split('"""')[1]
SPEC_F = freeze_or_load("GC_h5_last30_momentum", "1.0-paper", "GC", 60, RULES, dict(predictor="11:30-12:00 ET", trade="15:30-16:00 ET", rule="sign"), "H-F4")
SPEC_G = freeze_or_load("GC_crabel_stretch_ORB", "1.0-crabel1990", "GC", 60, RULES, dict(session="08:20-13:30 ET", stretch_lookback=10, multiple=1.0, exit="session close"), "H-G4")


def mk_trade(name, d, side, ent, ext, epx, xpx, cost, hi, lo, nb, reason, stop=None):
    pts = (xpx - epx) * side; gross = cost.pnl_points_to_usd(pts, 1); fees = cost.fees(1, 2)
    mfe = (hi - epx) if side > 0 else (epx - lo); mae = (epx - lo) if side > 0 else (hi - epx)
    r = (gross - fees) / cost.pnl_points_to_usd(abs(epx - stop), 1) if stop is not None and abs(epx - stop) > 0 else float("nan")
    return Trade(name, "GC", "GC.v.0", side, 1, ent, ent, ext, 0, nb, epx, xpx, "market", reason, stop, None, pts, gross, fees, cost.pnl_points_to_usd(2 * cost.slip("market"), 1), gross - fees, r, max(mae, 0), max(mfe, 0), nb, (ext - ent).total_seconds() / 60, False, False, d, "RTH", name)


def main():
    res = {"F": {"spec_id": SPEC_F, "phases": {}}, "G": {"spec_id": SPEC_G, "phases": {}}}
    ledgers = {}
    for phase in GC_PHASES:
        days, bars = gc_days(phase, SPEC_F if phase != "development" else None, "phase4 F/G")
        bars = bars.with_columns(pl.col("ts_open").dt.cast_time_unit("ns").cast(pl.Int64).alias("o_ns"), pl.col("ts_close").dt.cast_time_unit("ns").cast(pl.Int64).alias("c_ns"))
        byday = {d: g for (d,), g in bars.group_by(["trade_date"], maintain_order=True)}
        ctx = daily_ctx_gc(bars)
        # ---------------- F ----------------
        sigF = []
        for d in days:
            g = byday.get(d)
            if g is None:
                continue
            p1130 = g.filter(pl.col("c_ns") <= et_ns(d, "11:30")); p1200 = g.filter(pl.col("c_ns") <= et_ns(d, "12:00"))
            e = g.filter(pl.col("o_ns") >= et_ns(d, "15:30")); x = g.filter(pl.col("c_ns") <= et_ns(d, "16:00"))
            if p1130.is_empty() or p1200.is_empty() or e.is_empty() or x.is_empty() or int(p1130["c_ns"][-1]) < et_ns(d, "11:00") or int(x["c_ns"][-1]) <= int(e["o_ns"][0]):
                continue
            r5 = float(p1200["close"][-1]) / float(p1130["close"][-1]) - 1.0
            side = 1 if r5 > 0 else (-1 if r5 < 0 else 0)
            if side == 0:
                continue
            ent, ext = e.row(0, named=True), x.row(-1, named=True)
            path = g.filter((pl.col("o_ns") >= ent["o_ns"]) & (pl.col("c_ns") <= ext["c_ns"]))
            sigF.append((d, side, ent, ext, float(path["high"].max()), float(path["low"].min()), path.height))
        # ---------------- G ----------------
        # day-session OHLC per eligible session for the stretch (prior sessions only)
        sess = {}
        for d, g in byday.items():
            w = g.filter((pl.col("o_ns") >= et_ns(d, "08:20")) & (pl.col("c_ns") <= et_ns(d, "13:30")))
            if w.height >= 200:
                sess[d] = (float(w["open"][0]), float(w["high"].max()), float(w["low"].min()))
        sdates = sorted(sess)
        sigG = []
        for d in days:
            if d not in sess:
                continue
            prior = [x for x in sdates if x < d][-10:]
            if len(prior) < 10:
                continue
            stretch = float(np.mean([min(sess[p][1] - sess[p][0], sess[p][0] - sess[p][2]) for p in prior]))
            g = byday[d]; w = g.filter((pl.col("o_ns") >= et_ns(d, "08:20")) & (pl.col("c_ns") <= et_ns(d, "13:30")))
            O = float(w["open"][0]); up, dn = O + stretch, O - stretch
            hi, lo, cl = w["high"].to_numpy(), w["low"].to_numpy(), w["close"].to_numpy()
            iu = np.flatnonzero(hi >= up); idn = np.flatnonzero(lo <= dn)
            if not iu.size and not idn.size:
                continue
            ju = int(iu[0]) if iu.size else 10 ** 9; jd = int(idn[0]) if idn.size else 10 ** 9
            if ju == jd:
                side, ei, both = (1, ju, True)         # same bar: worst case -> stopped at the other level
            elif ju < jd:
                side, ei, both = 1, ju, False
            else:
                side, ei, both = -1, jd, False
            trig = up if side > 0 else dn; prot = dn if side > 0 else up
            # protective stop scan from the entry bar onward (entry bar included; if it touches the other level in the same bar -> worst case)
            seg_hi, seg_lo = hi[ei:], lo[ei:]
            sm = (seg_lo <= prot) if side > 0 else (seg_hi >= prot)
            if both or (sm.size and sm[0]):
                xi, reason = 0, "stop"
            else:
                k = np.flatnonzero(sm); xi, reason = (int(k[0]), "stop") if k.size else (len(cl) - 1 - ei, "time")
            sigG.append((d, side, ei, xi, reason, trig, prot, w, stretch))
        for tier in TIERS:
            cost = cost_for("GC", tier)
            rowsF = [mk_trade("F_GC_h5", d, s, ent["ts_open"], ext["ts_close"], cost.fill_market(ent["open"], s), cost.fill_market(ext["close"], -s), cost, hi, lo, nb, "time") for d, s, ent, ext, hi, lo, nb in sigF]
            rowsG = []
            for d, s, ei, xi, reason, trig, prot, w, stretch in sigG:
                epx = cost.spec.round_to_tick(trig + s * cost.slip("stop"))
                if reason == "stop":
                    xpx = cost.spec.round_to_tick(prot - s * cost.slip("stop"))
                else:
                    xpx = cost.fill_market(float(w["close"][ei + xi]), -s)
                ent = w["ts_open"][ei]; ext = w["ts_close"][ei + xi]
                seg = w.slice(ei, xi + 1)
                rowsG.append(mk_trade("G_GC_crabel", d, s, ent, ext, epx, xpx, cost, float(seg["high"].max()), float(seg["low"].min()), xi + 1, reason, stop=prot))
            for key, rows, spec in (("F", rowsF, SPEC_F), ("G", rowsG, SPEC_G)):
                led = pl.DataFrame([asdict(t) for t in rows]) if rows else pl.DataFrame()
                ledgers[f"{key}_{phase}_{tier}"] = led
                res[key]["phases"].setdefault(phase, {})[tier] = evaluate(led, days, ctx if tier == "base" else pl.DataFrame(), r_defined=(key == "G"))
                s_ = res[key]["phases"][phase][tier]["summary"]
                print(key, phase, tier, {k: round(s_.get(k, float("nan")), 3) for k in ("trades", "win_rate", "expectancy_usd", "net_pnl", "profit_factor", "sharpe_daily_ann")}, flush=True)
    for key, title in (("F", "PHASE 4 F — GC 5th-half-hour -> last-half-hour momentum"), ("G", "PHASE 4 G — GC Crabel Stretch ORB")):
        C.save(f"{key}_GC", {"spec_id": res[key]["spec_id"]}, res[key]["phases"], {k[2:]: v for k, v in ledgers.items() if k.startswith(key + "_")}, ["GC 2025 locked (not run). Roll-switch, thin-roll, hole and early-close dates excluded."], title)
    print("DONE")


if __name__ == "__main__":
    main()
