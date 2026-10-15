# Phase 5 — NQ pre-open directional bias: pre-registered research design

Written 2026-09-02, BEFORE any feature or model was built. Only the eligible-day counts and target
base rates in section 1 were computed (descriptive statistics on development + validation years, no
model, no holdout access). Everything below is the plan we implement against; deviations must be
recorded in `docs/phase5/DEVIATIONS.md` with a reason and date.

Objective: at 09:29:59 ET on day D, using NQ prints only, output BUY / SELL / NO BIAS for the
09:30–12:00 ET window, and report for every experiment: total eligible days, predictions made,
NO BIAS days, correct, incorrect, accuracy = correct / predictions, coverage = predictions / eligible.

---

## 0. What the data can and cannot support (read first)

| fact | value |
|---|---|
| NQ trade prints | 2021-01-04 → 2026-06-17 (parquet) + 2026-06-18 → 2026-08-14 (DBN batch) |
| eligible sessions with a full 09:30–12:00 window (early closes excluded) | 2021: 250, 2022: 250, 2023: 248, 2024: 249, 2025: 247, 2026-H1: 114 → 1,358; DBN tail ≈ 41 → ≈ 1,399 |
| base rate P(12:00 price > 09:30 open) | 53.8% overall; 52.0 / 50.8 / 55.2 / 55.0 / 53.0 / 59.6 by year |
| base rate P(MFE > MAE from the open) | 49.0% overall; 44.8 / 46.8 / 52.4 / 45.8 / 51.0 / 58.8 |
| agreement of those two labels | 85.3% of days |
| median absolute 09:30→12:00 return | 0.47%; 25th percentile 0.23%; median range 179 pts |
| MBP-1 (book) data | ends 2025-06-30 → cannot be used (would be absent in validation/holdout) |

Statistical power (binomial, two-sided 95%):

| predictions n | half-width of the accuracy CI at p≈0.55 |
|---:|---:|
| 100 | ±9.8% |
| 250 | ±6.2% |
| 500 | ±4.4% |
| 1,000 | ±3.1% |

Detecting a true 58% model against the 53.8% always-BUY baseline with 80% power needs ≈1,100
predictions — most of the whole out-of-sample record. Consequences, stated now so that nobody is
surprised later:

1. The always-BUY baseline is already at 54–60% depending on the year. Every accuracy figure is
   reported next to the naive baseline on the same predicted days; the quantity we optimise is the
   **lift** = accuracy − baseline accuracy on the same days, with BUY and SELL sides reported separately.
2. Claims above ~62% on hundreds of days are treated as evidence of leakage until proven otherwise
   (section 7, automatic leakage audit).
3. NO BIAS filtering can raise accuracy only on the covered subset. A 70% figure on 60 predictions
   is noise; the report always prints the counts.

---

## 1. Splits for this project (`configs/splits_bias.yaml`, enforced by `nqgc.guard`)

| tier | window | eligible days | use |
|---|---|---:|---|
| Development (design) | 2021-01-04 → 2023-12-31 | 748 | all design decisions, via *internal* walk-forward: train 2021 → predict 2022 by quarter; train 2021–22 → predict 2023 by quarter (498 internally predicted days) |
| Walk-forward validation | 2024-01-02 → 2025-12-31 | 496 | ≤ 5 FROZEN recipes, expanding-window retrain each quarter (8 folds); selects 1 recipe by a pre-declared rule |
| Final holdout (LOCKED) | 2026-01-02 → 2026-08-14 | ≈ 155 | run ONCE with the single selected recipe; ledger entry |

Disclosure: 2026-01-02 → 2026-06-17 was viewed in Phases 2–4 as strategy P&L (validation-2 of the
ORB-retrace and noise-area strategies). No directional-bias statistic was ever computed on it, but it is
not virgin at the "researcher has seen this period" level. 2026-06-18 → 2026-08-14 (41 days) is virgin
for everything except the old R4 "Balanced" test. The holdout report is split into the two sub-windows.
The holdout is too small to confirm a small edge (±8% at n=155); its role is to refute a large claim.

Rule for the 2024–2025 validation: nothing computed on it may change a recipe. If a validation result
suggests a change, the change is recorded as a hypothesis for a *future* data window, not applied.

---

## 2. Eligibility and the mandatory reporting block

Eligible day D: NQ front contract has ≥ 1,000 prints in [09:30, 12:00) ET, ≥ 90% of the 18:00 → 09:29
overnight minutes contain prints, and D is not an early-close session. Days after the vendor hole
(2025-11-28) and days whose overnight session is truncated by a holiday are kept but flagged
(`f_after_holiday`); they are eligible.

Every experiment prints, for every period (each calendar year, training, each walk-forward fold,
combined OOS, holdout) and for ALL / BUY-only / SELL-only:

```
Total eligible days:      N
BUY/SELL predictions:     P      (BUY: b, SELL: s)
NO BIAS days:             N − P
Correct:                  C      (BUY correct: cb, SELL correct: cs)
Incorrect:                P − C
Accuracy:                 C / P  = xx.xx%   [Wilson 95% CI]
Coverage:                 P / N  = xx.xx%
Baseline on same days:    always-majority accuracy on the P predicted days
Lift:                     accuracy − baseline
```

Implemented once in `bias/report.py` and used by every script; no experiment may report accuracy any
other way.

---

## 3. Target definitions (all computed from prints at/after 09:30:00 ET only; module `bias/targets.py`)

Notation: `P_open` = first print at or after 09:30:00.000 ET; `P_1200` = last print ≤ 12:00:00 ET;
`H`, `L` = max/min print in [09:30, 12:00]; `R20` = median 09:30–12:00 range of sessions D−20..D−1
(known at 09:29 on D); `ret` = P_1200 / P_open − 1.

| id | label rule | FLAT (excluded from accuracy, counts as eligible) |
|---|---|---|
| T1 net | sign(P_1200 − P_open) | exact tie only |
| T2a / T2b thresholded net | +1 if P_1200 − P_open ≥ +k·R20, −1 if ≤ −k·R20 | in between; k = 0.10 (T2a), 0.25 (T2b) |
| T3 dominant excursion | sign((H − P_open) − (P_open − L)) | \|MFE − MAE\| < 0.05·R20 |
| T4a / T4b first-hit | which of P_open ± k·R20 is hit first | neither hit by 12:00; k = 0.25 (T4a), 0.50 (T4b) |
| T5 path trend | sign of OLS slope of 1-min closes vs time | R² < 0.10 |
| T6 time-in-direction | side (above/below P_open) holding the majority of 1-min bars | majority share < 60% |
| T7 clean directional day | label only if T1, T3 and T5 agree | any disagreement |

Target selection rule (pre-declared, decided on development-internal walk-forward only): choose the
target with the highest **development-internal lift over its own naive baseline at 60% coverage**
using the best of the linear models in E4, subject to (i) ≥ 300 internal predictions, (ii) lift ≥ 0
in both 2022 and 2023, (iii) tradability: on correctly-labelled days the median favourable excursion
must exceed 0.5·R20 (a label that is "correct" but gives the user nothing to trade is useless).
Ties → the simpler definition (T1 before T2 before T3...). The chosen target is fixed before E5.
Every other target is still reported for every experiment as a secondary column (cheap, informative),
but never used for selection after this point.

---

## 4. Feature bank (module `bias/features/`; every function takes `cutoff_ns` = 09:30:00 ET of day D, exclusive)

All price features are on the causal front contract; returns that span a contract roll use the causal
roll spread (`data_cache/nq_roll_adjust.parquet`, built in Phase 3). Rolling statistics use sessions
≤ D−1 (daily table with `shift(1)`) or prints < cutoff (intraday). Scales: `R20` above and
`σ20` = std of daily RTH log returns over D−20..D−1.

**A. Prior RTH session (D−1)** — 16 features
`rth_ret`, `rth_ret/σ20`, `clv` (close location in range), `range/R20`, `am_ret` (09:30–12:00 of D−1),
`pm_ret` (12:00–16:00), `last_hour_ret`, `trend_day` = |close−open|/range, `gap_prev` (D−1 open vs D−2
close), `rth_volume/median20`, `last_hour_aggressor_imbalance`, `settle_minus_close`, `rth_up_minutes_share`,
`rth_max_drawdown_from_high`, `rth_new_20d_high/low` flags.

**B. Overnight (16:00 ET D−1 → 09:29:59 D), also per sub-session {16:00–18:00, 18:00–02:00 Asia,
02:00–08:30 Europe, 08:30–09:00 data window, 09:00–09:29 last 30 min}** — ≈ 70 features
per window: return / σ20, range / R20, realized vol (5-min) ratio to its 20-day median, volume ratio to
20-day median, signed aggressor volume imbalance, large-trade (≥ 10 lots) imbalance, VWAP distance
(price at 09:29 vs window VWAP) / R20, number of ≥ 0.25·R20 reversals.
Whole-overnight extras: position of the 09:29 price inside the overnight range, minutes since
overnight high / low, overnight high/low vs prior RTH high/low/close (breakout flags), drawup and
drawdown from overnight extremes, length and sign of the last directional run (5-min bars), the 08:30
shock (return 08:30–08:35 / σ20, its sign, and share retraced by 09:29), gap = 09:29 price vs D−1 16:00
close and vs D−1 settlement (in R20 units), `gap_vs_overnight_range` (gap through overnight extremes).

**C. Multi-day context** — ≈ 30 features
2/5/10/20-day RTH returns / σ, position in 20/60-day range, 20-day realized vol and its 5-day change,
5-day mean CLV, count of up RTH days in last 5/10, streak length, share of last 10 gaps filled within
the 09:30–12:00 window, prior-20-day mean 09:30–12:00 return and up-share (seasonal drift),
autocorrelation of 09:30–12:00 returns over 20 days, D−1's 09:30–12:00 label (all 7 targets, lagged),
calendar: day-of-week, month, first/last trading day of month, third Friday, roll week, day after holiday.
Scheduled-event calendars (FOMC, CPI) are NOT market data but are external → **excluded**.

**D. Sequence representation** — raw inputs, not hand features
overnight 1-min log-return vector 18:00 → 09:29 (690 values, zero-filled at holiday truncations), and
its 5-min aggregation (138 values); used by E6 only.

**E. Transforms** (computed inside each training fold, never on the full sample)
rolling 250-day z-score and rank (window ending at D−1), pairwise products of the top-20 univariate
features (E3 output), sign interactions with the vol-regime flag.

Estimated bank: ~180 base features, ~1,500 hypotheses after transforms and both polarities. Built
once into `runs/phase5/feature_matrix.parquet` (one row per eligible day, columns `f_*`), targets into
`targets.parquet` (columns `y_*`), joined only by date. Feature-matrix hash goes in every result.

---

## 5. Model families (fixed, small hyper-parameter grids chosen now)

| id | family | grid (≤ 4 configs) | notes |
|---|---|---|---|
| M0 | naive baselines | — | always-BUY; sign(D−1 RTH); sign(overnight); sign(09:00–09:29); anti-sign(overnight); seasonal-drift sign |
| M1 | univariate rules | sign rule at the training median; extreme-tercile rule (middle → NO BIAS) | both polarities; thousands of hypotheses; multiplicity-corrected (section 8) |
| M2 | logistic regression | L2 with C ∈ {0.01, 0.1, 1}; elastic-net C=0.1, l1_ratio 0.5 | on z-scored features; also on top-20 screened features (screen inside the fold) |
| M3 | Gaussian naive Bayes / LDA | none | robust in low-signal settings |
| M4 | random forest / extra trees | 500 trees, max_depth {3, 5}, min_leaf 30 | |
| M5 | gradient boosting (sklearn HistGB) | depth 3, lr 0.03, iters {100, 300}, min_leaf 30, l2 1.0 | early stopping on the last 15% of the training window (chronological) |
| M6 | kNN | k ∈ {50, 100} on the top-10 screened features | |
| M7 | sequence: random-convolution kernels (ROCKET-style, 2,000 kernels) + ridge | ridge α ∈ {1, 10, 100} | on the overnight 1-min / 5-min return vector; cheap, no deep-learning dependency |
| M8 | MLP | 1 hidden layer 32, α 1e-2, early stop | sklearn; a deep sequence model (GRU) only if M7 shows signal |
| M9 | regime-conditioned | 2-state Gaussian HMM on daily (RTH return, log range) fitted inside the fold → posterior as a feature; separate M2 per vol tercile | |
| M10 | ensembles | mean of calibrated probabilities of the best config of M2, M4, M5, M7; logistic stacking with fold-internal CV | NO BIAS when members disagree (section 6) |

Every fitted object (scaler, screen, model, calibrator, threshold) lives inside `Recipe.fit(train_rows)`;
`Recipe.predict(row)` sees one day. Random seeds fixed; results deterministic.

---

## 6. NO BIAS (confidence) filtering

1. Each recipe outputs `p = P(label = +1)` calibrated on the last 20% of the training window
   (chronological Platt scaling; isotonic if ≥ 400 calibration days).
2. Decision: BUY if p ≥ 0.5 + τ, SELL if p ≤ 0.5 − τ, else NO BIAS.
3. τ is set inside the training window to hit a pre-declared coverage level; the coverage level is part
   of the recipe, from the grid {40%, 60%, 80%, 100%}. It is never tuned on validation or holdout.
4. Alternative gates, each a separate pre-declared recipe variant: (a) ensemble agreement ≥ 3 of 4
   members; (b) choppy-day gate: a fold-internal ridge regression predicts |ret| / R20, and the
   lowest-tercile predictions become NO BIAS regardless of direction.
5. The coverage–accuracy curve (accuracy at 100/80/60/40%) is reported for every recipe. If accuracy
   does not rise monotonically as coverage falls on the development-internal folds, the NO BIAS
   mechanism is declared uninformative for that recipe and the 100%-coverage variant is used.
6. Asymmetry check: SELL-side accuracy is judged against (1 − up-share); a recipe whose SELL accuracy
   is below the SELL base rate in development is limited to BUY / NO BIAS outputs (and reported as such).

---

## 7. Leakage safeguards (each is a test in `tests/test_bias_leakage.py`)

1. **Print cutoff**: every feature function receives `cutoff_ns` and asserts `max(ts used) < cutoff_ns`;
   the matrix builder records the max timestamp touched per day.
2. **Truncation test** (the Phase-3 R4 test, reused): for 40 random days, features built from the
   dataset physically truncated at 09:29:59.999 ET equal those built from the full dataset, bit-for-bit.
3. **Daily-table truncation**: for 40 random days, rolling/lagged daily features recomputed from the
   daily table truncated at D−1 equal the stored row.
4. **Schema separation**: features `f_*`, targets `y_*`; the harness refuses a feature matrix containing
   any `y_` column, and the fit function receives `X` and `y` for training rows only.
5. **Fold isolation**: the fold object exposes only rows with date ≤ fold_start − 1 day for fitting;
   scalers, screens, calibrators, τ and HMMs are fitted inside `fit`. A test fits on shuffled-future
   rows and asserts the predictions change (i.e., that the recipe really sees only what it is given).
6. **Time-shift test**: features shifted forward by one day (using D+1's features for D) must
   collapse a real model to baseline accuracy; if it does not, the target leaked into the features.
7. **Label-permutation null**: circular-block permutation of labels (block 20 days) × 500 → the
   distribution of accuracy for the same pipeline; the real pipeline is reported with its permutation p-value.
8. **Automatic leakage audit**: any development-internal accuracy > 62% at ≥ 80% coverage, or lift
   > 8 points, triggers tests 2, 3, 6 and 7 before the result is written to the registry.
9. **Contract roll**: overnight returns spanning the causal roll use the roll spread; a test checks
   roll-day overnight returns are within 3·σ20 (no spread jumps).
10. **Holdout lock**: `configs/splits_bias.yaml` phase `holdout` is `locked: true`; the feature matrix
    for locked dates is not built until the single unlock (ledger entry with the recipe hash).
11. **Time zones**: all ET boundaries via `zoneinfo` (DST-tested in Phase 1); trade-date mapping
    reused from the framework.

---

## 8. Overfitting safeguards

1. This document is the pre-registration: experiment list, grids, target and recipe selection rules.
2. **Multiplicity** for the univariate screen (E3): the family-wise null = distribution of the
   *maximum* accuracy over all hypotheses under label permutation (500 draws). A rule is reported as
   significant only above the 95th percentile of that maximum. All hypotheses are logged, not just winners.
3. **Minimum evidence to advance**: ≥ 300 development-internal predictions, lift over the best naive
   baseline with a 90% block-bootstrap CI excluding 0, lift ≥ 0 in both 2022 and 2023.
4. **Candidate cap**: ≤ 5 frozen recipes enter validation; 1 enters the holdout. Validation selection
   rule: highest pooled validation lift at the recipe's own coverage with ≥ 250 predictions; ties → the
   simpler family (lower M-number). If no recipe has lift > 0 with CI excluding 0 on validation, the
   holdout is still run with the top-ranked recipe and the project reports a negative.
5. **Consistency**: lift ≥ 0 in ≥ 3 of the 4 out-of-sample years (2022, 2023 internal; 2024, 2025) is
   required to call anything "genuine".
6. **Feature stability**: a screened feature counts as stable if selected in ≥ 70% of folds; recipes
   relying on unstable features are flagged.
7. **Winner's rank**: every result states how many hypotheses/recipes were tried before it
   (`tries` column in the registry) and the family-wise p-value.
8. **Calibration**: reliability curve on out-of-sample folds; a recipe whose 60%-coverage bucket is not
   more accurate than its 100%-coverage bucket has a broken confidence signal (section 6.5).
9. **No re-runs**: a validation or holdout run is written once; re-running with any change creates a
   new registry entry with a new hash and is reported as such.

---

## 9. Automated hypothesis framework (`src/nqgc/bias/`)

```
bias/
  targets.py        # 7 label definitions from ≥09:30 prints; y_* columns
  features/         # prior_rth.py, overnight.py, context.py, sequence.py — each fn(day, prints, cutoff_ns)
  matrix.py         # builds feature_matrix.parquet + targets.parquet once; hashes; max-ts-touched audit
  folds.py          # dev-internal folds (quarterly, expanding), validation folds, holdout (locked)
  recipe.py         # Recipe(fit/predict) wrapper: scaler → screen → model → calibrator → τ
  hypotheses.py     # generator: sign rules, tercile rules, interactions over the feature bank
  null.py           # block permutation nulls, max-null, time-shift test, block bootstrap
  report.py         # THE mandatory block (all / BUY / SELL; per year / fold / period) with Wilson CIs
  registry.py       # append-only runs/phase5/registry.jsonl: spec hash, matrix hash, tries, results
  run_*.py          # E0…E10 drivers
```

Throughput: the matrix is built once from the tick cache (≈ 15 min); each hypothesis or recipe then
evaluates on 1,400 rows in milliseconds → thousands of hypotheses and hundreds of recipe × fold fits
run in minutes, with all outputs in the registry and per-experiment markdown reports under
`runs/phase5/<experiment>/`.

---

## 10. Order of experiments

| step | what | data | output |
|---|---|---|---|
| E0 | eligibility table, all 7 targets, base rates by year, target agreement matrix, tradability stats (MFE/MAE by label) | development | `runs/phase5/E0/` |
| E1 | naive baselines M0 with the full reporting block for every target | development | sets the bar |
| E2 | feature bank v1 build + leakage tests 1–3, 6, 9; feature-matrix hash frozen | development (+ validation rows built but not read) | matrix v1 |
| E3 | univariate screen (M1) over all hypotheses × 7 targets on dev-internal walk-forward, max-null; **target chosen by the section-3 rule** | dev-internal | significant-feature list, target choice |
| E4 | linear models M2/M3 on all features and on fold-screened top-20 | dev-internal | |
| E5 | tree ensembles M4/M5, kNN M6 | dev-internal | |
| E6 | sequence models M7 (M8 only if M7 shows lift) | dev-internal | |
| E7 | regime conditioning M9 | dev-internal | |
| E8 | ensembles M10, coverage curves, choppy gate, calibration; **freeze ≤ 5 recipes** with hashes in `docs/phase5/FROZEN_CANDIDATES.md` | dev-internal | frozen recipes |
| E9 | walk-forward validation 2024–2025 (8 quarterly folds, expanding) of the frozen recipes; select 1 by the section-8.4 rule | validation | full report per fold / year / side |
| E10 | holdout: one run of the selected recipe, 2026-01-02 → 2026-08-14, reported as two sub-windows; ledger entry | holdout (unlock) | final report |

After E10: `docs/phase5/PHASE5_REPORT.md` with every reporting block, the full registry summary
(number of hypotheses tried, winner's rank, permutation p-values), and an honest verdict. If nothing
beats the always-BUY baseline out of sample, that is the result.
