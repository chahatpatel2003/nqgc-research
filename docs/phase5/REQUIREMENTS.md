# Phase 5 — explicit requirements (user, 2026-09-02) and how each is enforced

1. **The product is not a trading strategy.** It outputs only BUY / SELL / NO BIAS. Enforced: no P&L, entries, stops
   or targets are computed anywhere in `src/nqgc/bias/`; the only tradability statistic is descriptive (E0: excursion in
   the labelled direction), used to reject targets that stop representing the practical question.
2. **The prediction exists at 09:29:59 ET and applies to 09:30–12:00 ET NQ only.** Enforced: every feature function
   receives `cutoff_ns = 09:30:00.000 ET` and the builder records `max_ts_pre` (the last print timestamp touched);
   the build asserts `max_ts_pre < cutoff` for every day. Targets use prints in [09:30, 12:00] only.
3. **Directional accuracy is the objective**, not P&L/Sharpe/RR. Enforced: the selection rules in the design use
   lift over the naive baseline; no P&L metric exists in the reports.
4. **Every result prints**: eligible days, predictions made, BUY count, SELL count, NO BIAS count, correct days, wrong
   days, accuracy, coverage, BUY accuracy, SELL accuracy, naive baseline accuracy on the exact same predicted days.
   Enforced: one function, `nqgc.bias.report.block`, produces this and every script uses it (also per year and per side).
5. **No credit for base-rate BUY drift.** Enforced: "always-BUY on the same predicted days" and "best constant on the
   same days" are printed next to every accuracy; lift = accuracy − always-BUY; SELL accuracy is judged against the
   SELL base rate; balanced accuracy is printed.
6. **NO BIAS matters** (75% on 60% of days beats 56% on 100%). Enforced: every recipe reports the accuracy-vs-coverage
   frontier at the pre-declared coverage grid {40, 60, 80, 100}%.
7. **Low coverage must not manufacture accuracy.** Enforced: counts are always printed first; a Wilson 95% CI accompanies
   every accuracy; the advancement rule requires ≥ 300 development-internal predictions and ≥ 250 validation predictions.
8. **Every target must still answer "was BUY or SELL the better bias for 09:30–12:00?"** Enforced: every reporting block
   also prints the plain net-sign (T1) accuracy on the same predictions, and the E0 tradability table shows the excursion
   in the labelled direction per target; a target whose labelled direction does not deliver a favourable excursion
   ≥ 0.5·R20 (median) is rejected.
9. **The 2026 tail stays untouched during E0–E8.** Enforced: `configs/splits_bias.yaml` locks 2026-01-01..2026-08-14
   (guard + ledger); no script in E0–E8 loads any 2026 print; validation prints (2024–2025) are not loaded before E9.
10. **Unusually high accuracy (70%+, certainly 80–90%+) triggers audits automatically.** Enforced: the harness (E3+)
    runs the truncation, daily-truncation, label-permutation and alignment audits before writing any result with
    development-internal accuracy > 62% at ≥ 80% coverage or lift > 8 points, and flags it `AUDIT` in the registry.
11. **Do not stop at the first significant model.** Enforced: E3–E8 run the whole pre-registered hypothesis space; the
    registry records every hypothesis, and the report states the winner's rank among all tries.
12. **Preserve all results, including failures; never silently modify rules after seeing results.** Enforced: append-only
    `runs/phase5/registry.jsonl`; every deviation from the pre-registered design is written to `docs/phase5/DEVIATIONS.md`
    with date and reason before the changed code is run.
