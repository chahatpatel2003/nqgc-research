"""Part 8 diagnostics on the P14 cell (BASE cost) — DIAGNOSTICS ONLY. For each bucket: trades, expR, PF, 95% CI, per year,
and a recurrence score = number of years (of those with >= 30 trades) in which the bucket's expR exceeds the year's overall expR."""
import datetime as dt, json, sys, math
sys.path.insert(0, "src"); sys.path.insert(0, "scripts/phase2"); sys.path.insert(0, "scripts/phase3")
import numpy as np, polars as pl
from nqgc import diagnostics as dg
from nqgc.paths import RUNS_DIR

OUT = RUNS_DIR / "phase3"
CT = "America/Chicago"


def buckets(led: pl.DataFrame) -> dict[str, pl.Expr]:
    ent = pl.col("entry_ts").dt.convert_time_zone(CT)
    q = lambda c, n=5: ((pl.col(c).rank("ordinal") - 1) * n // pl.len()).cast(pl.Utf8)
    return {
        "hour_ct": ent.dt.hour().cast(pl.Utf8).str.zfill(2),
        "half_hour_ct": (ent.dt.hour().cast(pl.Utf8).str.zfill(2) + ":" + pl.when(ent.dt.minute() < 30).then(pl.lit("00")).otherwise(pl.lit("30"))),
        "dow": ent.dt.strftime("%a"),
        "month": ent.dt.strftime("%m"),
        "atr_quintile": q("atr"),
        "atr_pct_quintile": pl.when(pl.col("atr_pct").fill_nan(None).is_null()).then(pl.lit("na")).otherwise(((pl.col("atr_pct").fill_nan(None) * 5).clip(0, 4.999).floor()).cast(pl.Int64, strict=False).cast(pl.Utf8)),
        "trend_regime": pl.when(pl.col("trend_up").is_null()).then(pl.lit("na")).when(pl.col("trend_up")).then(pl.lit("UP")).otherwise(pl.lit("DOWN")),
        "dist_vwap_atr": pl.when(pl.col("dist_vwap_atr") < -0.3).then(pl.lit("<-0.3")).when(pl.col("dist_vwap_atr") < 0).then(pl.lit("[-0.3,0)")).when(pl.col("dist_vwap_atr") < 0.3).then(pl.lit("[0,0.3)")).otherwise(pl.lit(">=0.3")),
        "dist_open_atr": pl.when(pl.col("dist_open_atr") < -0.3).then(pl.lit("<-0.3")).when(pl.col("dist_open_atr") < 0).then(pl.lit("[-0.3,0)")).when(pl.col("dist_open_atr") < 0.3).then(pl.lit("[0,0.3)")).otherwise(pl.lit(">=0.3")),
        "travel_30m_atr": pl.when(pl.col("travel_30m_atr") < 0).then(pl.lit("down into zone")).when(pl.col("travel_30m_atr") < 0.1).then(pl.lit("[0,0.1)")).when(pl.col("travel_30m_atr") < 0.25).then(pl.lit("[0.1,0.25)")).otherwise(pl.lit(">=0.25")),
        "zone_age_min": pl.when(pl.col("age_min") < 5).then(pl.lit("1-5")).when(pl.col("age_min") < 30).then(pl.lit("5-30")).when(pl.col("age_min") < 120).then(pl.lit("30-120")).when(pl.col("age_min") < 1440).then(pl.lit("2h-1d")).otherwise(pl.lit(">1d")),
        "age_sessions": pl.when(pl.col("age_sessions") == 0).then(pl.lit("0")).when(pl.col("age_sessions") <= 2).then(pl.lit("1-2")).when(pl.col("age_sessions") <= 10).then(pl.lit("3-10")).otherwise(pl.lit("11-30")),
        "pivot_scale": pl.col("scale").cast(pl.Utf8),
        "tap_no": pl.col("tap_no").cast(pl.Utf8),
        "fire_speed_s": pl.when(pl.col("fire_s") <= 10).then(pl.lit("0-10")).when(pl.col("fire_s") <= 30).then(pl.lit("11-30")).otherwise(pl.lit("31-60")),
    }


def table(led: pl.DataFrame, name: str, expr: pl.Expr) -> list[dict]:
    t = led.with_columns(expr.alias("b"), pl.col("entry_ts").dt.year().alias("year"))
    overall = {y: float(v) for y, v in t.group_by("year").agg(pl.mean("r_multiple")).iter_rows()}
    rows = []
    for (b,), g in t.group_by(["b"], maintain_order=True):
        r = g["r_multiple"].to_numpy(); r = r[~np.isnan(r)]
        if len(r) < 5:
            continue
        m, lo, hi = dg.bootstrap_mean_ci(r, n_boot=2000)
        w = r[r > 0].sum(); l = -r[r < 0].sum()
        yrs = {}
        for y, gy in g.group_by("year"):
            ry = gy["r_multiple"].to_numpy(); ry = ry[~np.isnan(ry)]
            if len(ry) >= 30:
                yrs[int(y[0])] = dict(n=int(len(ry)), expR=float(ry.mean()), beats_year=bool(ry.mean() > overall[int(y[0])]))
        rows.append(dict(bucket=b, n=int(len(r)), expR=float(m), ci=[lo, hi], pf=float(w / l) if l > 0 else float("inf"),
                         years=yrs, recur=f"{sum(1 for v in yrs.values() if v['beats_year'])}/{len(yrs)}"))
    rows.sort(key=lambda x: x["bucket"])
    return rows


def main():
    led = pl.read_parquet(OUT / "trades_P14_ck2_S12.5_T30_base.parquet")
    led = led.with_columns(pl.col("entry_ts").dt.replace_time_zone("UTC") if led.schema["entry_ts"].time_zone is None else pl.col("entry_ts"))
    out = {"n": led.height, "tables": {}}
    for name, expr in buckets(led).items():
        out["tables"][name] = table(led, name, expr)
    (OUT / "diagnostics_P14.json").write_text(json.dumps(out, indent=1, default=str))
    L = ["# R4 P14 cell — diagnostic buckets (BASE cost; diagnostics only, no filter applied)", "", f"Trades: {led.height}. recur = years (with >= 30 trades in the bucket) in which the bucket beat that year's overall expectancy.", ""]
    for name, rows in out["tables"].items():
        L.append(f"## {name}"); L.append("| bucket | n | expR | 95% CI | PF | recur | per-year expR (n) |"); L.append("|---|---|---|---|---|---|---|")
        for r in rows:
            yr = " ".join(f"{y}:{v['expR']:+.2f}({v['n']})" for y, v in sorted(r["years"].items()))
            L.append(f"| {r['bucket']} | {r['n']} | {r['expR']:+.3f} | [{r['ci'][0]:+.3f}, {r['ci'][1]:+.3f}] | {r['pf']:.2f} | {r['recur']} | {yr} |")
        L.append("")
    (OUT / "DIAGNOSTICS_P14.md").write_text("\n".join(L))
    print("\n".join(L[:6]))


if __name__ == "__main__":
    main()
