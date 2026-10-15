"""Automated leakage checks. These are the tests that decide whether a computation is causal.

truncation_test  : f(bars[:k]) must equal f(bars)[:k] for every cut k — a value cannot change because
                   later bars exist.
perturbation_test: replacing all bars after k with garbage must not change values at or before k.
engine_truncation: running the engine on bars[:k] must reproduce every trade that closed before k.
fills_after_signals: every fill timestamp strictly after its signal timestamp.
"""
from __future__ import annotations
import numpy as np
import polars as pl


def _eq(a, b) -> bool:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return a.shape == b.shape and np.array_equal(np.isnan(a), np.isnan(b)) and np.allclose(np.nan_to_num(a), np.nan_to_num(b), rtol=0, atol=1e-9)


def truncation_test(fn, bars: pl.DataFrame, cuts: list[int] | None = None) -> list[int]:
    """fn(bars) -> array (or DataFrame with numeric columns). Returns the list of cut points that FAILED."""
    full = fn(bars)
    n = bars.height
    cuts = cuts or sorted({max(1, n // 7), n // 3, n // 2, (2 * n) // 3, n - 1})
    failed = []
    for k in cuts:
        part = fn(bars.slice(0, k))
        if isinstance(full, pl.DataFrame):
            ok = all(_eq(part[c].to_numpy(), full[c].to_numpy()[:k]) for c in full.columns)
        elif isinstance(full, tuple):
            ok = all(_eq(p, f[:k]) for p, f in zip(part, full))
        else:
            ok = _eq(part, np.asarray(full)[:k])
        if not ok:
            failed.append(k)
    return failed


def perturbation_test(fn, bars: pl.DataFrame, k: int, seed: int = 0) -> bool:
    """True if values at index <= k are unchanged when all later bars are replaced by random garbage."""
    rng = np.random.default_rng(seed)
    base = fn(bars)
    n = bars.height
    garbage = bars.slice(k + 1, n - k - 1)
    if garbage.is_empty():
        return True
    scale = rng.uniform(0.5, 1.5, garbage.height)
    g = garbage.with_columns([(pl.col(c) * pl.Series(scale)).alias(c) for c in ("open", "high", "low", "close")])
    g = g.with_columns(pl.max_horizontal("open", "high", "low", "close").alias("high"), pl.min_horizontal("open", "high", "low", "close").alias("low"))
    pert = fn(pl.concat([bars.slice(0, k + 1), g]))
    if isinstance(base, pl.DataFrame):
        return all(_eq(base[c].to_numpy()[: k + 1], pert[c].to_numpy()[: k + 1]) for c in base.columns)
    if isinstance(base, tuple):
        return all(_eq(b[: k + 1], p[: k + 1]) for b, p in zip(base, pert))
    return _eq(np.asarray(base)[: k + 1], np.asarray(pert)[: k + 1])


def fills_after_signals(trades: pl.DataFrame) -> pl.DataFrame:
    """Rows violating entry_ts >= signal_ts (must be empty). Equality = fill on the first print of the next bar."""
    if trades.is_empty():
        return trades
    return trades.filter(pl.col("entry_ts") < pl.col("signal_ts"))


def engine_truncation_test(run_fn, bars: pl.DataFrame, k: int) -> tuple[bool, str]:
    """run_fn(bars) -> trades frame. Trades that exited before bar k must be identical when the engine only sees bars[:k]."""
    full = run_fn(bars)
    part = run_fn(bars.slice(0, k))
    cols = ["signal_ts", "entry_ts", "exit_ts", "entry_px", "exit_px", "net_usd", "exit_reason"]
    f = full.filter(pl.col("exit_idx") < k - 1).select(cols)
    p = part.filter(pl.col("exit_idx") < k - 1).select(cols)
    if f.height != p.height:
        return False, f"trade count differs: full={f.height} truncated={p.height}"
    if f.is_empty():
        return True, "no trades before cut"
    ok = f.equals(p)
    return ok, "identical" if ok else "trade ledgers differ before the cut"
