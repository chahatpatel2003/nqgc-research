"""THE mandatory reporting block. Every accuracy figure in Phase 5 comes from `block()`.

pred : +1 BUY, −1 SELL, 0 NO BIAS
y    : +1 / −1 label, 0 = FLAT (choppy: neither direction was the better bias; excluded from accuracy, counted as
       eligible and as a prediction), null = undefined
y_t1 : the plain net-sign label (12:00 vs 09:30 open) — printed for every block so that no target can drift away from
       the practical question.
"""
from __future__ import annotations
import math

import numpy as np
import polars as pl


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c - h, c + h)


def block(pred, y, y_t1=None) -> dict:
    pred = np.asarray(pred, dtype=float)
    y = np.asarray(y, dtype=float)
    y_t1 = y if y_t1 is None else np.asarray(y_t1, dtype=float)
    n = int(pred.size)
    made = pred != 0
    buy = pred > 0
    sell = pred < 0
    dec = made & ~np.isnan(y) & (y != 0)
    correct = dec & (pred == y)
    wrong = dec & (pred != y)
    flat_pred = made & (y == 0)
    undefined = made & np.isnan(y)
    nd = int(dec.sum())
    c = int(correct.sum())
    cb, nb = int((correct & buy).sum()), int((dec & buy).sum())
    cs, ns = int((correct & sell).sum()), int((dec & sell).sum())
    up_share = float((y[dec] > 0).mean()) if nd else float("nan")
    acc = c / nd if nd else float("nan")
    buy_acc = cb / nb if nb else float("nan")
    sell_acc = cs / ns if ns else float("nan")
    # balanced accuracy over true classes among decisive predicted days
    tp = int((correct & (y > 0)).sum()); pos = int((dec & (y > 0)).sum())
    tn = int((correct & (y < 0)).sum()); neg = int((dec & (y < 0)).sum())
    bal = 0.5 * ((tp / pos if pos else float("nan")) + (tn / neg if neg else float("nan")))
    dec1 = made & ~np.isnan(y_t1) & (y_t1 != 0)
    c1 = int((dec1 & (pred == y_t1)).sum())
    n1 = int(dec1.sum())
    lo, hi = wilson(c, nd)
    return {
        "eligible": n, "predictions": int(made.sum()), "buy": int(buy.sum()), "sell": int(sell.sum()), "no_bias": int((~made).sum()),
        "correct": c, "wrong": int(wrong.sum()), "pred_on_flat": int(flat_pred.sum()), "pred_on_undefined": int(undefined.sum()),
        "accuracy": acc, "ci_lo": lo, "ci_hi": hi, "coverage": float(made.sum() / n) if n else float("nan"),
        "buy_dec": nb, "buy_correct": cb, "buy_accuracy": buy_acc, "sell_dec": ns, "sell_correct": cs, "sell_accuracy": sell_acc,
        "always_buy_same_days": up_share, "best_constant_same_days": max(up_share, 1 - up_share) if nd else float("nan"),
        "lift_vs_always_buy": acc - up_share if nd else float("nan"), "balanced_accuracy": bal,
        "sell_base_rate_same_days": (1 - up_share) if nd else float("nan"),
        "t1_predictions": n1, "t1_correct": c1, "t1_accuracy": c1 / n1 if n1 else float("nan"),
        "t1_always_buy_same_days": float((y_t1[dec1] > 0).mean()) if n1 else float("nan"),
    }


def _pct(v):
    return "n/a" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{100 * v:.2f}%"


def text(b: dict, title: str = "") -> str:
    lines = [f"[{title}]" if title else ""]
    lines += [
        f"Total eligible days:      {b['eligible']}",
        f"BUY/SELL predictions:     {b['predictions']}   (BUY {b['buy']}, SELL {b['sell']})",
        f"NO BIAS days:             {b['no_bias']}",
        f"Correct days:             {b['correct']}",
        f"Wrong days:               {b['wrong']}" + (f"   (+{b['pred_on_flat']} predictions on FLAT-labelled days, excluded from accuracy)" if b['pred_on_flat'] else ""),
        f"Accuracy:                 {b['correct']}/{b['correct'] + b['wrong']} = {_pct(b['accuracy'])}   [Wilson 95% {_pct(b['ci_lo'])} – {_pct(b['ci_hi'])}]",
        f"Coverage:                 {b['predictions']}/{b['eligible']} = {_pct(b['coverage'])}",
        f"BUY accuracy:             {b['buy_correct']}/{b['buy_dec']} = {_pct(b['buy_accuracy'])}",
        f"SELL accuracy:            {b['sell_correct']}/{b['sell_dec']} = {_pct(b['sell_accuracy'])}   (SELL base rate on same days {_pct(b['sell_base_rate_same_days'])})",
        f"Always-BUY on same days:  {_pct(b['always_buy_same_days'])}   lift = {_pct(b['lift_vs_always_buy'])}   best constant {_pct(b['best_constant_same_days'])}   balanced acc {_pct(b['balanced_accuracy'])}",
        f"Net-sign (T1) accuracy on the same predictions: {b['t1_correct']}/{b['t1_predictions']} = {_pct(b['t1_accuracy'])}   (always-BUY {_pct(b['t1_always_buy_same_days'])})",
    ]
    return "\n".join(lines)


TABLE_COLS = ["eligible", "predictions", "correct", "wrong", "no_bias", "accuracy", "coverage", "buy_dec", "buy_accuracy", "sell_dec", "sell_accuracy", "always_buy_same_days", "lift_vs_always_buy", "t1_accuracy"]


def table(rows: list[tuple[str, dict]], label: str = "Period") -> str:
    hdr = f"| {label} | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |"
    sep = "|" + "---|" * 15
    out = [hdr, sep]
    for name, b in rows:
        out.append(f"| {name} | {b['eligible']} | {b['predictions']} | {b['correct']} | {b['wrong']} | {b['no_bias']} | {_pct(b['accuracy'])} | {_pct(b['coverage'])} | "
                   f"{b['buy_dec']} | {_pct(b['buy_accuracy'])} | {b['sell_dec']} | {_pct(b['sell_accuracy'])} | {_pct(b['always_buy_same_days'])} | {_pct(b['lift_vs_always_buy'])} | {_pct(b['t1_accuracy'])} |")
    return "\n".join(out)


def by_group(df: pl.DataFrame, group: str, pred_col: str, y_col: str, t1_col: str = "y_T1") -> list[tuple[str, dict]]:
    rows = []
    for g in sorted(df[group].unique().to_list()):
        s = df.filter(pl.col(group) == g)
        rows.append((str(g), block(s[pred_col].to_numpy(), s[y_col].to_numpy(), s[t1_col].to_numpy())))
    return rows


def full_report(df: pl.DataFrame, pred_col: str, y_col: str, title: str, t1_col: str = "y_T1", period_col: str | None = None) -> tuple[str, dict]:
    """Text block for the whole frame, per-year table, per-period table (folds) and BUY / SELL sub-blocks."""
    b = block(df[pred_col].to_numpy(), df[y_col].to_numpy(), df[t1_col].to_numpy())
    parts = [text(b, title), "", "Per calendar year:", table(by_group(df, "year", pred_col, y_col, t1_col), "Year")]
    res = {"all": b, "year": dict(by_group(df, "year", pred_col, y_col, t1_col))}
    if period_col and period_col in df.columns:
        rows = by_group(df, period_col, pred_col, y_col, t1_col)
        parts += ["", f"Per {period_col}:", table(rows, period_col)]
        res[period_col] = dict(rows)
    return "\n".join(parts), res
