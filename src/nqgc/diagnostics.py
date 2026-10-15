"""Statistical diagnostics for Phase-2 baseline truth: bootstrap CIs, Monte-Carlo drawdowns, daily-return
statistics, bucket tables (DIAGNOSTICS ONLY — nothing here may feed back into a rule), clustering checks."""
from __future__ import annotations
import datetime as dt
import math

import numpy as np
import polars as pl


def bootstrap_mean_ci(x: np.ndarray, n_boot: int = 5000, seed: int = 20260902, alpha: float = 0.05) -> tuple[float, float, float]:
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    if len(x) < 2:
        return float("nan"), float("nan"), float("nan")
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(x), size=(n_boot, len(x)))
    means = x[idx].mean(axis=1)
    return float(x.mean()), float(np.percentile(means, 100 * alpha / 2)), float(np.percentile(means, 100 * (1 - alpha / 2)))


def mc_drawdown(net: np.ndarray, n_sim: int = 5000, seed: int = 20260902) -> dict:
    """Max drawdown distribution under iid reshuffling of the trade sequence (same trades, random order)."""
    net = np.asarray(net, dtype=float)
    if len(net) < 2:
        return {}
    rng = np.random.default_rng(seed)
    dds = np.empty(n_sim)
    for k in range(n_sim):
        e = np.cumsum(rng.permutation(net))
        dds[k] = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], e])) - np.concatenate([[0.0], e])))
    hist = float(np.max(np.maximum.accumulate(np.concatenate([[0.0], np.cumsum(net)])) - np.concatenate([[0.0], np.cumsum(net)])))
    return {"historical": hist, "p50": float(np.percentile(dds, 50)), "p90": float(np.percentile(dds, 90)),
            "p95": float(np.percentile(dds, 95)), "p99": float(np.percentile(dds, 99)), "p_exceed_hist": float(np.mean(dds >= hist))}


def daily_stats(trades: pl.DataFrame, all_trade_dates: list[dt.date], account_size: float) -> dict:
    """Daily net P&L over ALL eligible trade dates (zero on no-trade days), mean, t-stat, hit rate, annualised Sharpe."""
    if trades.is_empty():
        return {}
    d = trades.group_by("trade_date").agg(pl.sum("net_usd").alias("pnl"), pl.sum("gross_usd").alias("gross"))
    full = pl.DataFrame({"trade_date": all_trade_dates}).join(d, on="trade_date", how="left").fill_null(0.0).sort("trade_date")
    p = full["pnl"].to_numpy()
    traded = d["pnl"].to_numpy()
    n = len(p); mean = p.mean(); sd = p.std(ddof=1) if n > 1 else float("nan")
    t = mean / (sd / math.sqrt(n)) if sd and sd > 0 else float("nan")
    ret = p / account_size
    return {"n_days": n, "n_traded_days": int(len(traded)), "mean_daily_usd": float(mean), "mean_daily_ret": float(ret.mean()),
            "t_stat": float(t), "hit_rate_traded_days": float(np.mean(traded > 0)) if len(traded) else float("nan"),
            "hit_rate_all_days": float(np.mean(p > 0)), "sharpe_ann": float(mean / sd * math.sqrt(252)) if sd and sd > 0 else float("nan"),
            "gross_mean_daily_usd": float(full["gross"].mean())}


def _period_key(col: pl.Expr, by: str) -> pl.Expr:
    ct = col.dt.convert_time_zone("America/Chicago")
    return {"year": ct.dt.year().cast(pl.Utf8), "quarter": ct.dt.year().cast(pl.Utf8) + "-Q" + ((ct.dt.month() - 1) // 3 + 1).cast(pl.Utf8),
            "month": ct.dt.strftime("%Y-%m"), "hour": ct.dt.hour().cast(pl.Utf8).str.zfill(2), "dow": ct.dt.strftime("%a")}[by]


def bucket(trades: pl.DataFrame, by: str, key_expr: pl.Expr | None = None) -> pl.DataFrame:
    if trades.is_empty():
        return pl.DataFrame()
    key = key_expr if key_expr is not None else _period_key(pl.col("entry_ts"), by)
    t = trades.with_columns(key.alias(by))
    return (t.group_by(by).agg(pl.len().alias("n"), (pl.col("net_usd") > 0).mean().alias("wr"), pl.sum("gross_usd").alias("gross"),
                               pl.sum("net_usd").alias("net"), pl.mean("net_usd").alias("avg"), pl.mean("r_multiple").alias("avg_r"),
                               pl.sum("gross_pts").alias("pts")).sort(by))


def pct_profitable(trades: pl.DataFrame, by: str) -> float:
    b = bucket(trades, by)
    return float((b["net"] > 0).mean()) if not b.is_empty() else float("nan")


def vol_quintile_table(trades: pl.DataFrame, daily_ctx: pl.DataFrame) -> pl.DataFrame:
    """daily_ctx: [trade_date, atr14_prior, trend_prior]. Quintiles of the CAUSAL prior-14-session range ATR."""
    if trades.is_empty() or daily_ctx.is_empty():
        return pl.DataFrame()
    ctx = daily_ctx.with_columns(((pl.col("atr14_prior").rank("ordinal") - 1) * 5 // pl.len()).alias("vol_q"))
    t = trades.join(ctx.select("trade_date", "vol_q", "trend_prior"), on="trade_date", how="left")
    return bucket(t, "vol_q", pl.col("vol_q").cast(pl.Utf8)), bucket(t, "trend", pl.col("trend_prior"))


def daily_context(bars_daily: pl.DataFrame) -> pl.DataFrame:
    """bars_daily: [trade_date, high, low, close] per session (front contract). Prior-only features:
    atr14_prior = mean session range of the previous 14 sessions; trend_prior = UP if previous close > 20-session
    SMA of previous closes else DOWN. Both are known before the session opens."""
    d = bars_daily.sort("trade_date").with_columns((pl.col("high") - pl.col("low")).alias("rng"))
    d = d.with_columns(pl.col("rng").shift(1).rolling_mean(14, min_samples=10).alias("atr14_prior"),
                       (pl.col("close").shift(1) > pl.col("close").shift(1).rolling_mean(20, min_samples=15)).alias("_up"))
    return d.with_columns(pl.when(pl.col("_up").is_null()).then(pl.lit("NA")).when(pl.col("_up")).then(pl.lit("UP")).otherwise(pl.lit("DOWN")).alias("trend_prior")).select("trade_date", "atr14_prior", "trend_prior")


def clustering(trades: pl.DataFrame) -> dict:
    if trades.is_empty():
        return {}
    net = trades.sort("exit_ts")["net_usd"].to_numpy()
    tot = net.sum()
    top5 = np.sort(net)[-5:].sum()
    days = trades.group_by("trade_date").agg(pl.sum("net_usd").alias("p")).sort("p", descending=True)
    months = bucket(trades, "month")
    best_m = float(months["net"].max()) if not months.is_empty() else float("nan")
    return {"share_top5_trades": float(top5 / tot) if tot > 0 else float("nan"), "share_top5_days": float(days["p"].head(5).sum() / tot) if tot > 0 else float("nan"),
            "best_month_share": float(best_m / tot) if tot > 0 else float("nan"), "n_trades": int(len(net)),
            "sufficiency": "OK" if len(net) >= 100 else ("LOW (<100)" if len(net) >= 30 else "INSUFFICIENT (<30)")}


def outlier_dependence(trades: pl.DataFrame) -> dict:
    """Result with the largest / top-3 / top-5 winners removed, and the share of total net P&L held by the top 1/5/10 % of trades."""
    if trades.is_empty():
        return {}
    net = np.sort(trades["net_usd"].to_numpy())[::-1]
    tot = float(net.sum()); n = len(net)
    def excl(k):
        return float(net[k:].sum()) if n > k else float("nan")
    def top_share(frac):
        k = max(1, int(math.ceil(frac * n)))
        return float(net[:k].sum() / tot) if tot != 0 else float("nan")
    return {"total": tot, "excl_top1": excl(1), "excl_top3": excl(3), "excl_top5": excl(5),
            "share_top1pct": top_share(0.01), "share_top5pct": top_share(0.05), "share_top10pct": top_share(0.10),
            "expectancy_excl_top3": float(net[3:].mean()) if n > 3 else float("nan")}


def daily_pnl_series(trades: pl.DataFrame, all_days: list) -> pl.DataFrame:
    d = trades.group_by("trade_date").agg(pl.sum("net_usd").alias("pnl")) if not trades.is_empty() else pl.DataFrame({"trade_date": [], "pnl": []})
    return pl.DataFrame({"trade_date": all_days}).join(d, on="trade_date", how="left").fill_null(0.0).sort("trade_date")


def bucket_analysis(series: dict[str, pl.DataFrame]) -> dict:
    """series: name -> [trade_date, pnl] over a COMMON date list. Equal-risk = inverse of daily P&L std (no optimisation)."""
    names = list(series)
    if len(names) < 2:
        return {"note": "fewer than two strategies"}
    df = series[names[0]].select("trade_date")
    for n in names:
        df = df.join(series[n].rename({"pnl": n}), on="trade_date", how="left").fill_null(0.0)
    X = df.select(names).to_numpy()
    corr_d = np.corrcoef(X.T)
    m = df.with_columns(pl.col("trade_date").dt.strftime("%Y-%m").alias("ym")).group_by("ym").agg([pl.sum(n) for n in names]).sort("ym")
    corr_m = np.corrcoef(m.select(names).to_numpy().T) if m.height > 2 else np.full((len(names), len(names)), np.nan)
    lose = X < 0
    pair_lose = {f"{a}|{b}": float(np.mean(lose[:, i] & lose[:, j])) for i, a in enumerate(names) for j, b in enumerate(names) if j > i}
    all_lose = float(np.mean(lose.all(axis=1)))
    sd = X.std(axis=0, ddof=1); w = np.where(sd > 0, 1.0 / np.where(sd > 0, sd, 1), 0.0); w = w / w.sum()
    port = (X * w).sum(axis=1)
    eq = np.cumsum(port); dd = float(np.max(np.maximum.accumulate(np.concatenate([[0], eq])) - np.concatenate([[0], eq])))
    sharpe = float(port.mean() / port.std(ddof=1) * math.sqrt(252)) if port.std(ddof=1) > 0 else float("nan")
    return {"names": names, "daily_corr": corr_d.tolist(), "monthly_corr": corr_m.tolist(), "pairwise_both_lose": pair_lose, "all_lose_share": all_lose,
            "equal_risk_weights": {n: float(x) for n, x in zip(names, w)}, "portfolio_max_dd_usd_weighted": dd, "portfolio_sharpe": sharpe,
            "portfolio_total_weighted": float(port.sum()), "n_days": int(len(port))}
