"""Performance statistics. Everything is computed from the trade ledger produced by the engine.
NET figures include configured fees; GROSS figures exclude them. Both are always reported.
Ambiguous trades (intrabar stop/target order unknown, no tick data) are counted under the
conservative rule AND reported separately so their influence is visible."""
from __future__ import annotations
import math

import numpy as np
import polars as pl


def _max_dd(equity: np.ndarray) -> float:
    if len(equity) == 0:
        return 0.0
    peak = np.maximum.accumulate(np.concatenate([[0.0], equity]))
    return float(np.max(peak - np.concatenate([[0.0], equity])))


def _streaks(x: np.ndarray) -> tuple[int, int]:
    best_w = best_l = cur_w = cur_l = 0
    for v in x:
        if v > 0:
            cur_w += 1; cur_l = 0
        elif v < 0:
            cur_l += 1; cur_w = 0
        else:
            cur_w = cur_l = 0
        best_w, best_l = max(best_w, cur_w), max(best_l, cur_l)
    return best_w, best_l


def _ratio(num, den):
    return float(num / den) if den not in (0, 0.0) and not math.isnan(den) else float("nan")


def summary(trades: pl.DataFrame, account_size: float = 50000.0, session_minutes_per_day: float = 1380.0, n_trade_dates: int | None = None) -> dict:
    if trades.is_empty():
        return {"trades": 0}
    t = trades.sort("exit_ts")
    net = t["net_usd"].to_numpy(); gross = t["gross_usd"].to_numpy(); r = t["r_multiple"].to_numpy()
    wins, losses = net[net > 0], net[net < 0]
    be = int(np.sum(net == 0))
    n = len(net)
    eq = np.cumsum(net)
    daily = (t.group_by("trade_date").agg(pl.sum("net_usd")).sort("trade_date"))["net_usd"].to_numpy()
    n_days = n_trade_dates or len(daily)
    dmean, dstd = daily.mean(), daily.std(ddof=1) if len(daily) > 1 else float("nan")
    downside = daily[daily < 0]
    dd_std = math.sqrt(np.mean(downside ** 2)) if len(downside) else float("nan")
    sharpe = _ratio(dmean, dstd) * math.sqrt(252) if not math.isnan(dstd) else float("nan")
    sortino = _ratio(dmean, dd_std) * math.sqrt(252) if not math.isnan(dd_std) else float("nan")
    mdd = _max_dd(eq)
    years = max(n_days / 252.0, 1e-9)
    annual_ret = net.sum() / years
    calmar = _ratio(annual_ret, mdd)
    r_valid = r[~np.isnan(r)]
    r_eq = np.cumsum(r_valid)
    hold = t["hold_minutes"].to_numpy()
    out = dict(
        trades=n, win_rate=float(np.mean(net > 0)), loss_rate=float(np.mean(net < 0)), breakeven_rate=be / n,
        avg_r=float(r_valid.mean()) if len(r_valid) else float("nan"), expectancy_usd=float(net.mean()), expectancy_r=float(r_valid.mean()) if len(r_valid) else float("nan"),
        gross_pnl=float(gross.sum()), net_pnl=float(net.sum()), fees=float(t["fees_usd"].sum()), slippage_cost=float(t["slippage_usd"].sum()),
        profit_factor=_ratio(wins.sum(), -losses.sum()) if len(losses) else float("inf"),
        avg_winner=float(wins.mean()) if len(wins) else float("nan"), avg_loser=float(losses.mean()) if len(losses) else float("nan"),
        largest_winner=float(wins.max()) if len(wins) else float("nan"), largest_loser=float(losses.min()) if len(losses) else float("nan"),
        max_drawdown_usd=mdd, max_drawdown_r=_max_dd(r_eq) if len(r_eq) else float("nan"), max_drawdown_pct_account=mdd / account_size,
        sharpe_daily_ann=sharpe, sortino_daily_ann=sortino, calmar=calmar,
        consecutive_wins=_streaks(net)[0], consecutive_losses=_streaks(net)[1],
        long_trades=int((t["side"] == 1).sum()), short_trades=int((t["side"] == -1).sum()),
        avg_mae_pts=float(t["mae_pts"].mean()), avg_mfe_pts=float(t["mfe_pts"].mean()), median_mae_pts=float(t["mae_pts"].median()), median_mfe_pts=float(t["mfe_pts"].median()),
        avg_hold_minutes=float(hold.mean()), median_hold_minutes=float(np.median(hold)),
        exposure=float(hold.sum() / (n_days * session_minutes_per_day)) if n_days else float("nan"),
        trades_per_day=n / n_days if n_days else float("nan"), trade_dates_with_trades=int(t["trade_date"].n_unique()),
        ambiguous_trades=int(t["ambiguous"].sum()), tick_resolved_trades=int(t["tick_resolved"].sum()),
        gross_expectancy_usd=float(gross.mean()), n_days=n_days,
    )
    return out


def breakdown(trades: pl.DataFrame, by: str) -> pl.DataFrame:
    """by: 'month' | 'quarter' | 'year' | 'session' | 'hour' | 'dow' | 'side' | 'exit_reason'"""
    t = trades
    ent = pl.col("entry_ts").dt.convert_time_zone("America/Chicago")
    key = {"month": ent.dt.strftime("%Y-%m"), "quarter": (ent.dt.year().cast(pl.Utf8) + "-Q" + ((ent.dt.month() - 1) // 3 + 1).cast(pl.Utf8)),
           "year": ent.dt.year(), "session": pl.col("session"), "hour": ent.dt.hour(), "dow": ent.dt.weekday(),
           "side": pl.col("side"), "exit_reason": pl.col("exit_reason")}[by]
    return (t.with_columns(key.alias(by)).group_by(by).agg(
        pl.len().alias("trades"), (pl.col("net_usd") > 0).mean().alias("win_rate"), pl.sum("gross_usd").alias("gross"),
        pl.sum("net_usd").alias("net"), pl.mean("net_usd").alias("expectancy_usd"), pl.mean("r_multiple").alias("avg_r"),
        pl.sum("fees_usd").alias("fees"), pl.sum("ambiguous").alias("ambiguous")).sort(by))


def full_report(trades: pl.DataFrame, account_size: float = 50000.0, n_trade_dates: int | None = None) -> dict:
    rep = {"summary": summary(trades, account_size, n_trade_dates=n_trade_dates)}
    if not trades.is_empty():
        for by in ("year", "quarter", "month", "session", "hour", "dow", "side", "exit_reason"):
            rep[by] = breakdown(trades, by).to_dicts()
    return rep
