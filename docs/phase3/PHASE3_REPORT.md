# PHASE 3 — R4 rebuilt causally from raw NQ prints (2026-09-02)

Locked windows untouched: NQ 2026-06-18..08-14 and GC 2025 were never read (`runs/ACCESS_LOG.jsonl`). No parameter was selected.
Engine: `src/nqgc/levels_r4.py` (+ `scripts/phase3/r4_driver.py`); tests `tests/test_r4_causal.py`; tables `docs/phase3/PHASE3_TABLES.md`;
diagnostics `runs/phase3/DIAGNOSTICS_P14.md`; raw results `runs/phase3/results.json`, `old_vs_causal.json`; ledgers `runs/phase3/trades_*.parquet`.

## 1. Proof the new zone engine is causal
* Every zone carries `pivot_ts`, `confirm_ts` (open of the confirmation minute) and `available_ts = confirm_ts + 60 s` (the confirmation
  needs that minute's low/high, so the zone exists only after the bar completes). Taps are rejected before `available_ts` (assertion and test).
* Taps are known at `tap_sec + 1`; R4 fires are decided at `fire_sec + 1`; entries fill at the close of the next second (frozen convention).
* `test_truncation_random_timestamps`: 12 random (session, T) points around real taps — the engine run on prints known at T reproduces
  EXACTLY (frame equality) the zones with `available_ts <= T`, the taps known at T and the fires decided by T of the full run. Passed.
* Component tests (all pass): pivot confirmation index and availability; ATR from sessions S-15..S-2 only (min 5); zone width formula;
  zone birth ordering; invalidation by age (30 sessions) and tap count (6); re-arm (out-of-band close + 900 s) and first-touch second;
  contract roll (zone screened at price + adj; adjustment table built from the basis session only, >= 200 print pairs per roll);
  session reset (later sessions cannot alter earlier outputs).
* Other look-ahead sources removed: `n_fwd` uses the scheduled 16:00 CT close, not the last print; ATR excludes holiday sessions (as
  the frozen daily table did); the universe dedup keeps the FIRST tap of a cluster (the frozen rule kept the OLDEST zone, which needs
  later taps and is not causal); the P6 `t0` filter (close 901 s before the tap outside the band) is applied as in the frozen corpus.
* Fidelity to the frozen layer on 2021-01..03: ATR and half-width identical on all 2,844 matched zones; confirmation minute identical on
  88 %; full-sample counts 60,429 zones / 335,824 taps vs 61,354 / 341,797 in the frozen layer.

## 2. Old fires eliminated by legitimate availability
Frozen fire stream (tap <= 3): 6,610 fires, of which **848 (12.8 %)** had the tap inside the zone's confirmation minute — impossible causally.
Causal universe (displacement 10, tap <= 3): 5,867 fires; per year old / old-leaked / causal / same-tap-second:
2021 702/120/595/372 · 2022 1,231/107/1,115/753 · 2023 758/116/638/482 · 2024 1,095/149/941/702 · 2025 1,734/231/1,580/1,087 · 2026H1 1,090/125/998/675.

## 3. Old leaked vs causal — the exact comparison (P14 cell, base cost)
| phase | old evaluator (leaked stream) | Phase-2 tick replay of old stream | Phase-2 replay, taps >= 1 min after confirmation | **Phase-3 causal rebuild** |
|---|---|---|---|---|
| development | 2,585 / +0.210 R / PF 1.31 | 2,562 / +0.214 / 1.33 | 2,244 / +0.135 / 1.20 | **2,275 / −0.050 / 0.93** |
| validation-1 | 1,050 / +0.102 / 1.15 | 1,043 / +0.152 / 1.22 | 903 / +0.020 / 1.03 | **907 / −0.077 / 0.90** |
| validation-2 | 2,703 / +0.223 / 1.34 | 2,671 / +0.263 / 1.40 | 2,336 / +0.184 / 1.27 | **2,500 / −0.048 / 0.94** |

Why the causal rebuild is worse than "old minus leaked fires": the leaked touch in the confirmation minute also SEEDED the zone's state in the
old engine (tap count 1, 900 s lockout, re-arm required). That suppressed the immediate re-tests of a fresh pivot. The causal engine, having
no such touch, trades them. Trade-level reconciliation on the causal P14 ledger (zero cost): 3,499 events also present in the old age >= 1 stream
earn +0.178 R (old evaluator on the same events: +0.206 R — the executor is confirmed); 2,180 causal-only events earn **−0.289 R (PF 0.64, WR 21 %)**,
negative in every year (−0.26 to −0.35). Of those, 1,686 are cluster-representative differences (the frozen dedup kept an older zone's later
tap 64 % of the time) at −0.22 R, and 441 are immediate re-tests with no old fire nearby at **−0.63 R, WR 11 %**. The old edge therefore came
from two leak effects: profitable impossible entries (+0.75 R on 12.8 % of fires) and leak-driven suppression of the worst re-tests.

## 4–5. Results of P14 and the eight H2 cells (full tables in PHASE3_TABLES.md)
Full eligible sample 2021-01-05..2026-06-17 (1,408 sessions), expR / PF / n:
| cell | zero cost | base ($14.80 RT, 0.74 pt) | stress ($34.80, 1.74 pt) | 2× stress ($64.80, 3.24 pt) |
|---|---|---|---|---|
| P14 ck2 S12.5/T30 | −0.001 / 1.00 / 5,679 | −0.053 / 0.93 / 5,682 | −0.120 / 0.85 | −0.231 / 0.73 |
| H2 ck0 S15/T30 | −0.001 / 1.00 / 5,668 | −0.042 / 0.94 | −0.100 / 0.86 | −0.188 / 0.76 |
| H2 ck0 S15/T40 | +0.004 / 1.01 / 5,596 | −0.040 / 0.95 | −0.101 / 0.87 | −0.189 / 0.78 |
| H2 ck0 S17.5/T30 | −0.006 / 0.99 / 5,635 | −0.040 / 0.94 | −0.090 / 0.87 | −0.141 / 0.81 |
| H2 ck0 S17.5/T40 | −0.000 / 1.00 / 5,546 | −0.038 / 0.95 | −0.094 / 0.87 | −0.152 / 0.81 |
| H2 ck0 S20/T30 | +0.002 / 1.00 / 5,594 | −0.031 / 0.95 | −0.073 / 0.89 | −0.115 / 0.83 |
| H2 ck0 S20/T40 | +0.007 / 1.01 / 5,495 | −0.027 / 0.96 | −0.070 / 0.90 | −0.120 / 0.84 |
| H2 ck0 S25/T30 | −0.006 / 0.99 / 5,506 | −0.029 / 0.95 | −0.065 / 0.89 | −0.101 / 0.84 |
| H2 ck0 S25/T40 | −0.007 / 0.99 / 5,378 | −0.032 / 0.95 | −0.068 / 0.90 | −0.109 / 0.84 |
P14 base-cost full sample: WR 29.2 %, expR −0.053 R [95 % CI −0.094, −0.013], net −303 R (−$75,799 on 1 contract), max DD 319 R, avg win $591 /
avg loss −$262, largest win $595 / largest loss −$765, Sharpe −1.25, Sortino −1.31, hold 4.1 min, longest losing streak 17, profitable
months 33 % / quarters 27 % / years 0 %, Monte-Carlo max DD p50/p90/p95/p99 = 338/374/388/414 R.

## 6. Year-by-year (P14 cell, expR / PF)
| | 2021 | 2022 | 2023 | 2024 | 2025 | 2026H1 |
|---|---|---|---|---|---|---|
| zero cost | +0.039 / 1.06 | +0.013 / 1.02 | −0.054 / 0.93 | −0.021 / 0.97 | +0.001 / 1.00 | +0.010 / 1.01 |
| base cost | −0.024 / 0.97 (576) | −0.036 / 0.95 (1,093) | −0.101 / 0.87 (606) | −0.077 / 0.90 (907) | −0.059 / 0.92 (1,527) | −0.030 / 0.96 (973) |
No year is positive after costs in any cell; before costs the best year is +0.04 R.

## 7. Cost sensitivity
Zero → base costs move every cell by −0.04 to −0.05 R (0.74 pt on a 12.5–25 pt stop); the sign is already non-positive at zero cost, so the
result does not hinge on a slippage choice. 2× stress (−0.10 to −0.23 R) is reported for completeness.

## 8. Parameter neighbourhood (base cost; diagnostics only)
P14 cell, full sample expR: displacement 8/9/10/11/12 → −0.048/−0.050/−0.053/−0.045/−0.054; stop 10/12.5/15 → −0.074/−0.053/−0.045; target
25/30/35 → −0.066/−0.053/−0.058; pivot thresholds ×0.8/×1.2 → −0.070/−0.068; re-arm 600/900/1200 s → −0.081/−0.053/−0.066; hysteresis ×0.5/×1.5 →
−0.058/−0.044; no dedup → −0.059. H2 S15/T30 behaves the same (−0.035 to −0.069). **The whole neighbourhood is flat and negative: there is no
plateau and no spike — the original values are not a lucky point; the family has no edge.**

## 9. Diagnostic patterns (P14, base; `runs/phase3/DIAGNOSTICS_P14.md`)
Checked hour, half-hour, weekday, month, ATR quintile, ATR-percentile quintile, trend regime, distance to VWAP, distance to open, 30-min approach,
zone age, zone age in sessions, pivot scale, tap number, fire speed. Nothing recurs: the previous "08:00–10:00 CT" and "down-trend" observations
do not survive (08:00 hour −0.013 R over 1,100 trades, 4/6 years above the yearly mean only because the mean is negative; DOWN regime −0.037 vs
UP −0.072, both negative every year except 2026 DOWN +0.02). The only buckets with CI > 0 are 06:00 CT (n = 100, two years only) and the 08:00
half-hour (n = 72); both are too small and not recurring. Zone age 5–30 min is the most consistent bucket (+0.023 R, 5/6 years above the yearly
mean) but its CI includes zero and the adjacent buckets are negative.

## 10–11. Verdict
**FAIL.** The corrected, fully causal R4 has no residual edge: zero-cost expectancy is within ±0.007 R of zero on 5,400–5,700 trades for all nine
original cells, every cost tier and every parameter neighbour is negative, no year is positive after costs, and no diagnostic bucket recurs.
The old +0.19–0.31 R results were produced by the chronology leak (impossible entries plus leak-shaped state that filtered out the worst re-tests).

## 12–13. Pre-registered improvement hypotheses (NOT TESTED)
Only one candidate met most of the five criteria; it is registered with its weaknesses stated. A second candidate (cluster seniority: skip a tap when an
older active zone lies within 0.05 ATR) is NOT registered because its evidence cannot be separated from the first and its neighbourhood is unknown.
* **H-R4-P3-1 (state seeding, causal reconstruction of the old lockout):** at `available_ts`, if the confirmation minute's range overlapped the band, seed the
  zone as already tapped once (`taps = 1`, `last_tap_ts` = that touch second, `armed = False`) without trading that touch; everything else as frozen.
  Reason: the immediate re-test of a fresh pivot is a momentum bounce, not a rejection. Evidence: in every year 2021–2026 the events the old engine kept
  earn +0.10..+0.25 R while the events it suppressed earn −0.26..−0.35 R (contaminated evidence: it comes from the leaked universe; the best causal proxy,
  Phase-2's age >= 1 replay, gave +0.135 / **+0.020** / +0.184 R at base cost — 2024 ≈ 0). Neighbourhood of the 900 s lockout: unverified (criterion 5 not met).
  Status: PRE_REGISTERED_NOT_TESTED. One run on validation-1, then validation-2, if approved.
