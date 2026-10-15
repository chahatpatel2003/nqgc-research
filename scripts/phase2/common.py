"""Shared Phase-2 infrastructure: eligible days, tick loading, boundaries, cost tiers, evaluation, reports."""
from __future__ import annotations
import datetime as dt, json, math, sys
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo
sys.path.insert(0, "src")
import numpy as np, polars as pl, yaml
from nqgc.paths import CONFIG_DIR, CACHE_DIR, RUNS_DIR, PROJECT_ROOT, assert_writable_target
from nqgc.guard import Access
from nqgc.calendar import load_observed_calendar, CT, UTC, session_close_utc
from nqgc.execution import CostModel
from nqgc.stats import summary, breakdown
from nqgc import diagnostics as dg
from nqgc.protocol import StrategySpec, freeze, SPECS_DIR

ET = ZoneInfo("America/New_York")
TIERS = {"gross": CONFIG_DIR / "costs_gross.yaml", "base": CONFIG_DIR / "costs_base.yaml", "stress": CONFIG_DIR / "costs_stress.yaml", "stress2x": CONFIG_DIR / "costs_stress2x.yaml"}
NQ_PHASES = ["development", "validation1", "validation2"]
GC_PHASES = ["development", "validation"]
ACCOUNT = 50000.0
OUT = RUNS_DIR / "phase2"


def cost_for(instrument: str, tier: str) -> CostModel:
    return CostModel.from_config(instrument, costs_path=TIERS[tier])


def freeze_or_load(name, version, instrument, tf, rules, params, hypothesis, notes="") -> str:
    existing = sorted(SPECS_DIR.glob(f"{name}_v{version}_*.json"))
    if existing:
        return json.loads(existing[0].read_text())["spec_id"]
    splits = yaml.safe_load(open(CONFIG_DIR / "splits.yaml"))
    s = StrategySpec(name, version, instrument, tf, rules, dict(params), splits[instrument], hypothesis, notes=notes)
    freeze(s, Path(__file__))
    return s.spec_id


def access(phase, instrument, spec_id, purpose):
    return Access(phase, instrument, spec_id=spec_id if phase != "development" else None, purpose=purpose)


# ---------------- NQ days & ticks ----------------
@lru_cache
def nq_cal():
    return load_observed_calendar("NQ")


@lru_cache
def nq_front_map() -> dict:
    fm = pl.read_parquet(CACHE_DIR / "nq_front_map.parquet")
    return {r["trade_date"]: r for r in fm.iter_rows(named=True)}


def nq_days(phase: str, spec_id: str | None, purpose: str, exclude_early_close=True, exclude_roll=False) -> list[dict]:
    acc = access(phase, "NQ", spec_id, purpose)
    lo, hi = acc.window()
    cal = nq_cal(); fm = nq_front_map()
    bad = {p["trade_date"] for p in cal.get("partial_sessions", [])} | {h["trade_date"] for h in cal.get("data_holes", [])}
    early = cal.get("early_closes", {})
    out = []
    for s in cal["trade_dates"]:
        d = dt.date.fromisoformat(s)
        if d < lo or d > hi or s in bad or d not in fm or fm[d]["bootstrap"]:
            continue
        if exclude_early_close and s in early:
            continue
        if exclude_roll and fm[d]["roll_day"]:
            continue
        out.append(dict(date=d, front=fm[d]["front"], roll_day=bool(fm[d]["roll_day"]), early_close=early.get(s)))
    return out


_tick_cache: dict = {}


def load_day_ticks(d: dt.date):
    """(ts_ns int64, price float64, symbol) for the front contract on trade date d, sorted (ts_event, sequence)."""
    mon = d.strftime("%Y-%m")
    if mon not in _tick_cache:
        _tick_cache.clear()
        _tick_cache[mon] = pl.read_parquet(CACHE_DIR / "nq_front_ticks" / f"{mon}.parquet")
    t = _tick_cache[mon].filter(pl.col("trade_date") == d)
    if t.is_empty():
        return None
    t = t.sort(["ts_event", "sequence"])
    return t["ts_event"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy(), t["price"].to_numpy(), t["symbol"][0]


def load_day_ticks_full(d: dt.date):
    """(ts_ns, price, size, symbol) for the front contract on trade date d."""
    mon = d.strftime("%Y-%m")
    if mon not in _tick_cache:
        _tick_cache.clear()
        _tick_cache[mon] = pl.read_parquet(CACHE_DIR / "nq_front_ticks" / f"{mon}.parquet")
    t = _tick_cache[mon].filter(pl.col("trade_date") == d)
    if t.is_empty():
        return None
    t = t.sort(["ts_event", "sequence"])
    return t["ts_event"].dt.cast_time_unit("ns").cast(pl.Int64).to_numpy(), t["price"].to_numpy(), t["size"].cast(pl.UInt32).to_numpy(), t["symbol"][0]


def et_ns(d: dt.date, hhmm: str) -> int:
    h, m = map(int, hhmm.split(":"))
    return int(dt.datetime(d.year, d.month, d.day, h, m, tzinfo=ET).timestamp() * 1e9)


def last_print_at_or_before(ts_ns, px, boundary_ns):
    k = int(np.searchsorted(ts_ns, boundary_ns, side="right")) - 1
    return (float(px[k]), int(ts_ns[k])) if k >= 0 else (None, None)


def print_at_or_before_raw(symbol: str, boundary: dt.datetime, lookback_min: int = 30):
    """Targeted raw query (used only when the previous session's prints for today's front are not cached, i.e. roll days)."""
    import duckdb
    from nqgc.data import _con
    from nqgc.paths import nq_trades_files
    lo = boundary - dt.timedelta(minutes=lookback_min)
    con = _con(mem="2GB", threads=4)
    for p in nq_trades_files():
        y, h = p.stem.split("_"); y = int(y)
        f0 = dt.date(y, 1, 1) if h == "H1" else dt.date(y, 7, 1); f1 = dt.date(y, 6, 30) if h == "H1" else dt.date(y, 12, 31)
        if not (f0 - dt.timedelta(days=1) <= boundary.date() <= f1 + dt.timedelta(days=1)):
            continue
        r = con.execute(f"SELECT price, ts_event FROM read_parquet('{p}') WHERE symbol = '{symbol}' AND ts_event > TIMESTAMPTZ '{lo.isoformat()}' AND ts_event <= TIMESTAMPTZ '{boundary.isoformat()}' ORDER BY ts_event DESC, sequence DESC LIMIT 1").fetchone()
        if r:
            return float(r[0])
    return None


# ---------------- GC ----------------
@lru_cache
def gc_cal():
    return load_observed_calendar("GC")


def gc_days(phase: str, spec_id: str | None, purpose: str) -> tuple[list[dt.date], pl.DataFrame]:
    from nqgc.data import load_gc_bars
    from nqgc.bars import gc_1m_to_bars
    acc = access(phase, "GC", spec_id, purpose)
    lo, hi = acc.window()
    cal = gc_cal()
    bad = set(cal.get("roll_switch_dates", [])) | set(cal.get("thin_last_days", [])) | {h["trade_date"] for h in cal.get("data_holes", [])} | set(cal.get("early_closes", {}).keys())
    g = load_gc_bars(acc, lo, hi)
    bars = gc_1m_to_bars(g, "GC")
    days = [d for d in sorted(set(bars["trade_date"].to_list())) if str(d) not in bad]
    return days, bars


# ---------------- evaluation ----------------
def daily_ctx_nq(days: list[dict]) -> pl.DataFrame:
    rows = []
    for x in days:
        t = load_day_ticks(x["date"])
        if t is None:
            continue
        ts, px, sym = t
        rows.append((x["date"], float(px.max()), float(px.min()), float(px[-1])))
    return dg.daily_context(pl.DataFrame(rows, schema=["trade_date", "high", "low", "close"], orient="row"))


def daily_ctx_gc(bars: pl.DataFrame) -> pl.DataFrame:
    d = bars.group_by("trade_date").agg(pl.max("high"), pl.min("low"), pl.last("close")).sort("trade_date")
    return dg.daily_context(d)


def evaluate(ledger: pl.DataFrame, all_days: list[dt.date], daily_ctx: pl.DataFrame, account=ACCOUNT, r_defined=True) -> dict:
    res = {"summary": summary(ledger, account, n_trade_dates=len(all_days))}
    if ledger.is_empty():
        return res
    net = ledger["net_usd"].to_numpy()
    m, lo, hi = dg.bootstrap_mean_ci(net)
    res["bootstrap_mean_trade"] = {"mean": m, "ci95_lo": lo, "ci95_hi": hi}
    if r_defined and ledger["r_multiple"].drop_nans().len() > 1:
        mr, lr, hr = dg.bootstrap_mean_ci(ledger["r_multiple"].to_numpy())
        res["bootstrap_mean_R"] = {"mean": mr, "ci95_lo": lr, "ci95_hi": hr}
    res["mc_drawdown"] = dg.mc_drawdown(net)
    res["daily"] = dg.daily_stats(ledger, all_days, account)
    res["clustering"] = dg.clustering(ledger)
    res["pct_profitable"] = {k: dg.pct_profitable(ledger, k) for k in ("month", "quarter", "year")}
    res["cost_drag_usd"] = float(ledger["gross_usd"].sum() - ledger["net_usd"].sum())
    res["outliers"] = dg.outlier_dependence(ledger)
    yrs = max(len(all_days) / 252.0, 1e-9)
    res["calmar"] = float(ledger["net_usd"].sum() / yrs / res["summary"]["max_drawdown_usd"]) if res["summary"].get("max_drawdown_usd") else float("nan")
    res["total_points"] = float(ledger["gross_pts"].sum())
    b = {k: dg.bucket(ledger, k).to_dicts() for k in ("year", "quarter", "month", "hour", "dow")}
    b["side"] = dg.bucket(ledger, "side", pl.col("side").cast(pl.Utf8)).to_dicts()
    b["exit_reason"] = dg.bucket(ledger, "exit_reason", pl.col("exit_reason")).to_dicts()
    if not daily_ctx.is_empty():
        vq, tr = dg.vol_quintile_table(ledger, daily_ctx)
        b["vol_quintile"] = vq.rename({"vol_q": "vol_quintile"}).to_dicts(); b["trend_regime"] = tr.rename({"trend": "trend_regime"}).to_dicts()
    res["buckets"] = b
    return res


def _fmt(v, nd=2):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return "n/a"
    return f"{v:,.{nd}f}" if isinstance(v, float) else str(v)


def report_md(title: str, spec: dict, per_phase: dict, notes: list[str]) -> str:
    L = [f"# {title}", "", "## Specification", "```", json.dumps(spec, indent=1, default=str), "```", ""]
    for n in notes:
        L.append(f"- {n}")
    L.append("")
    for phase, tiers in per_phase.items():
        L.append(f"## {phase}")
        keys = ["trades", "win_rate", "expectancy_usd", "avg_r", "gross_pnl", "net_pnl", "profit_factor", "sharpe_daily_ann", "sortino_daily_ann",
                "max_drawdown_usd", "largest_winner", "largest_loser", "avg_hold_minutes", "long_trades", "short_trades", "ambiguous_trades"]
        L.append("| metric | " + " | ".join(tiers.keys()) + " |"); L.append("|---|" + "---|" * len(tiers))
        for k in keys:
            L.append(f"| {k} | " + " | ".join(_fmt(t["summary"].get(k)) for t in tiers.values()) + " |")
        for k in ("total_points", "cost_drag_usd"):
            L.append(f"| {k} | " + " | ".join(_fmt(t.get(k)) for t in tiers.values()) + " |")
        for k, lab in (("bootstrap_mean_trade", "mean trade $ [95% CI]"), ("bootstrap_mean_R", "mean R [95% CI]")):
            L.append(f"| {lab} | " + " | ".join((f"{_fmt(t[k]['mean'])} [{_fmt(t[k]['ci95_lo'])}, {_fmt(t[k]['ci95_hi'])}]" if k in t else "n/a") for t in tiers.values()) + " |")
        L.append("| MC max-DD p50/p95/p99 (hist) | " + " | ".join((f"{_fmt(t['mc_drawdown'].get('p50'),0)}/{_fmt(t['mc_drawdown'].get('p95'),0)}/{_fmt(t['mc_drawdown'].get('p99'),0)} ({_fmt(t['mc_drawdown'].get('historical'),0)})" if t.get("mc_drawdown") else "n/a") for t in tiers.values()) + " |")
        L.append("| daily: mean $ / t / hit / Sharpe | " + " | ".join((f"{_fmt(t['daily'].get('mean_daily_usd'))} / {_fmt(t['daily'].get('t_stat'))} / {_fmt(t['daily'].get('hit_rate_traded_days'))} / {_fmt(t['daily'].get('sharpe_ann'))}" if t.get("daily") else "n/a") for t in tiers.values()) + " |")
        L.append("| % profitable months/quarters/years | " + " | ".join((f"{_fmt(100*t['pct_profitable']['month'],0)}% / {_fmt(100*t['pct_profitable']['quarter'],0)}% / {_fmt(100*t['pct_profitable']['year'],0)}%" if t.get("pct_profitable") else "n/a") for t in tiers.values()) + " |")
        L.append("| clustering top5 trades / top5 days / best month share | " + " | ".join((f"{_fmt(t['clustering'].get('share_top5_trades'))} / {_fmt(t['clustering'].get('share_top5_days'))} / {_fmt(t['clustering'].get('best_month_share'))} ({t['clustering'].get('sufficiency')})" if t.get("clustering") else "n/a") for t in tiers.values()) + " |")
        L.append("")
        base = tiers.get("base") or next(iter(tiers.values()))
        for bk in ("year", "quarter", "month", "hour", "dow", "side", "vol_quintile", "trend_regime", "exit_reason"):
            rows = base.get("buckets", {}).get(bk)
            if not rows:
                continue
            L.append(f"### {phase} — by {bk} (BASE cost)")
            L.append(f"| {bk} | n | wr | gross $ | net $ | avg $ | avg R | pts |"); L.append("|---|---|---|---|---|---|---|---|")
            for r in rows:
                L.append(f"| {r[bk]} | {r['n']} | {_fmt(r['wr'])} | {_fmt(r['gross'],0)} | {_fmt(r['net'],0)} | {_fmt(r['avg'])} | {_fmt(r['avg_r'])} | {_fmt(r['pts'],1)} |")
            L.append("")
    return "\n".join(L)


def save(name: str, spec: dict, per_phase: dict, ledgers: dict, notes: list[str], title: str):
    d = assert_writable_target(OUT / name); d.mkdir(parents=True, exist_ok=True)
    (d / "results.json").write_text(json.dumps({"spec": spec, "phases": per_phase, "notes": notes}, indent=1, default=str))
    for k, led in ledgers.items():
        if led is not None and not led.is_empty():
            led.write_parquet(d / f"trades_{k}.parquet")
    (d / "REPORT.md").write_text(report_md(title, spec, per_phase, notes))
    return d
