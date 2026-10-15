# PHASE 2 — baseline truth for six strategy implementations (2026-09-02)

Splits (CME trade dates): NQ development 2021-01-04..2023-12-31, validation-1 2024, validation-2 2025-01-01..2026-06-17,
**virgin holdout 2026-06-18..2026-08-14 LOCKED (never read)**; GC development 2016..2023, validation 2024, **2025 LOCKED (non-virgin,
strategy-specific holdout; never read)**. `runs/ACCESS_LOG.jsonl` and `runs/HOLDOUT_LEDGER.md` record every access; the only
locked-phase entries are guard unit tests that construct an Access object without loading data.

Cost tiers per contract: GROSS $0 · BASE NQ $14.80 RT (fees + 1 tick/side; 0.74 pt), GC $25.14 RT · STRESS NQ $34.80 RT (1.74 pt), GC $65.14 RT.
Engine: `nqgc.tick_engine` (signals at timestamps; fills at the next print; stops at/through + slippage; targets need trade-through; exact print order) for A/C/E;
`nqgc.engine` bar engine (next-bar-open fills) for F; bar conventions for D. No parameter was searched anywhere in this phase.

## 1. Recovered specification — A (R4) and B (HF09C)
* **A** — see `docs/phase2/SPEC_A_R4_RECOVERED.md` (rule-by-rule with the source file for each). Frozen code verified by 23/23 sha256 matches with the
  nq-levels `HOLDOUT_FREEZE_MANIFEST.json`; the frozen fire stream reproduces from raw ticks (299/299 sampled fires: fire second and both entry
  checkpoints exact); the front-contract choice agrees with this project's causal front map on all 1,370 sessions.
* **B** — **not recoverable** (`docs/phase2/SPEC_B_HF09C_NOT_RECOVERABLE.md`). HF09C was an XAUUSD spot M30 EMA(20/200) pullback in the AURUM project;
  its source (`hf09c_live.py`, `strategies.py`, `execution_engine.py`) and ledgers no longer exist on this machine or on T9; only two memory notes remain.
  Not implemented, per instruction.

## 2. Specifications C–F: `docs/phase2/SPEC_CDEF.md` (paper equations quoted; the noise-area paper's full text is in `audit/zarattini2024.txt`, Baltussen in `audit/baltussen2021.txt`).

## 3. Ambiguities found before testing
| strategy | ambiguity | handling |
|---|---|---|
| A | "R4 tap-and-go" is not a name in the source; three R4 constructions existed (model-gated Balanced — not mechanical, already failed the 2026-06-18+ window; P14 pure-price cell; H2 8-cell family, never a single frozen cell) | P14 cell + all 8 H2 cells reproduced, none selected; Balanced excluded |
| A | old evaluator fills targets on a 1-s LOW TOUCH with zero slippage | decomposed: touch vs through vs slippage tiers |
| A | **zone availability**: zones are stamped at the START of the confirmation minute although confirmation needs that minute's low | corrected variant run (taps ≥ 1 min after confirmation); reported alongside |
| B | rule set not recoverable | not run |
| D | 13:30 ET is a wall-clock boundary in the electronic session, not a settlement | used as specified |
| E | the paper's "timely" cut-off not recoverable from the abstract | none applied, per task text |
| F | stop evaluated only at semi-hourly checks (paper) vs continuously; re-entry after a stop | paper reading used: semi-hourly; re-entry allowed |

## 4–7. Results (BASE cost unless stated; full tables incl. gross/stress, bootstrap CIs, MC drawdowns, buckets in `runs/phase2/<strategy>/REPORT.md`)

### A — R4, as frozen (contains the confirmation-minute leak)
| cell | dev n / expR / PF | val-1 n / expR / PF | val-2 n / expR / PF | stress val-1 / val-2 expR |
|---|---|---|---|---|
| P14 ck2 S12.5/T30 | 2,562 / +0.214 / 1.33 | 1,043 / +0.152 / 1.22 | 2,671 / +0.263 / 1.40 | +0.08 / +0.18 |
| H2 ck0 S15/T30 | 2,553 / +0.192 / 1.31 | 1,035 / +0.204 / 1.34 | 2,666 / +0.270 / 1.46 | +0.14 / +0.21 |
| H2 ck0 S15/T40 | 2,491 / +0.213 / 1.31 | 1,017 / +0.237 / 1.35 | 2,622 / +0.319 / 1.49 | +0.17 / +0.27 |
| H2 ck0 S17.5/T30 | 2,530 / +0.192 / 1.34 | 1,025 / +0.207 / 1.37 | 2,656 / +0.268 / 1.49 | +0.15 / +0.23 |
| H2 ck0 S17.5/T40 | 2,456 / +0.21 / 1.34 | 1,004 / +0.23 / 1.37 | 2,606 / +0.31 / 1.51 | +0.16 / +0.27 |
| H2 ck0 S20/T30 | 2,509 / +0.16 / 1.30 | 1,019 / +0.16 / 1.30 | 2,641 / +0.26 / 1.51 | +0.14 / +0.22 |
| H2 ck0 S20/T40 | 2,432 / +0.18 / 1.30 | 996 / +0.19 / 1.32 | 2,586 / +0.31 / 1.54 | +0.16 / +0.27 |
| H2 ck0 S25/T30 | 2,465 / +0.13 / 1.27 | 1,004 / +0.13 / 1.27 | 2,614 / +0.21 / 1.48 | +0.11 / +0.19 |
| H2 ck0 S25/T40 | 2,370 / +0.15 / 1.27 | 974 / +0.16 / 1.29 | 2,547 / +0.25 / 1.47 | +0.13 / +0.22 |
P14 cell detail (base): dev WR 36.8 %, bootstrap 95 % CI of mean R [+0.148, +0.278], net $136,927, max DD $5,948 (23.8 R), MC p95 DD $10,417, daily t 6.4, 89 % profitable months;
val-1 CI [+0.057, +0.251], net $39,679, 83 % profitable months; val-2 CI [+0.199, +0.327], net $175,444, 89 % profitable months. Avg hold 3–6 min, 3–5 trades/day, ~5 % of fires skipped by the one-open rule.

### A — R4 CORRECTED (tap ≥ 1 minute after zone confirmation; 12.8 % of fires removed)
| cell | dev expR / PF (n) | val-1 expR / PF (n) | val-2 expR / PF (n) | stress val-1 / val-2 |
|---|---|---|---|---|
| P14 ck2 S12.5/T30 | +0.135 / 1.20 (2,244) | **+0.020 / 1.03** (903) | +0.184 / 1.27 (2,336) | −0.048 / +0.102 |
| H2 ck0 S15/T30 | +0.115 / 1.18 (2,239) | +0.084 / 1.13 (895) | +0.177 / 1.28 (2,332) | +0.013 / +0.119 |
| H2 ck0 S15/T40 | +0.149 / 1.21 (2,191) | +0.097 / 1.14 (884) | +0.208 / 1.30 (2,298) | +0.039 / +0.154 |
The removed 12.8 % of fires earned +0.746 R (PF 2.50, WR 54 %) under the old evaluator and held half of the old total points (6,782 of 13,570 on 2022–26).

### C — NQ ROD → last 30 min
| phase | n | WR | $/trade [95 % CI] | net $ | PF | daily t / Sharpe | months > 0 |
|---|---|---|---|---|---|---|---|
| dev | 748 | 50.8 % | +30 [−34, +92] | +22,495 | 1.10 | 0.96 / 0.55 | 58 % |
| val-1 | 249 | 46.6 % | −99 [−226, +25] | −24,640 | 0.74 | −1.53 / −1.54 | 33 % |
| val-2 | 361 | 45.2 % | −152 [−274, −29] | −54,963 | 0.70 | −2.39 / −1.99 | 22 % |
Gross is also negative OOS (val-1 −$21k, val-2 −$50k): the failure is not a cost artefact. Shorts lost −$45k in val-2.

### D — GC ROD → last 30 min
| phase | n | WR | $/trade [95 % CI] | net $ | PF | gross net $ |
|---|---|---|---|---|---|---|
| dev 2016–23 | 1,946 | 44.1 % | −26 [−35, −17] | −50,102 | 0.70 | −1,180 |
| val 2024 | 245 | 46.5 % | −5 [−46, +34] | −1,149 | 0.96 | +5,010 |
Every development year negative net; gross ≈ zero. The half-hour move is smaller than one GC round trip.

### E — NQ 1-minute TORB
| phase | n | WR | $/trade [95 % CI] | net $ | PF | daily t / Sharpe | years > 0 |
|---|---|---|---|---|---|---|---|
| dev | 748 | 48.1 % | −144 [−382, +92] | −107,595 | 0.89 | −1.18 / −0.68 | 2021 +15k, 2022 −113k, 2023 −10k |
| val-1 | 249 | 53.0 % | +312 [−95, +737] | +77,720 | 1.29 | 1.47 / 1.48 | 2024 + |
| val-2 | 361 | 50.4 % | +266 [−260, +808] | +96,017 | 1.16 | 0.99 / 0.83 | 2025 +67k, 2026 +30k |
Max DD in development $148k on one contract; MC p95 $205k. Hold ≈ 6.5 h. All OOS CIs include zero.

### F — NQ Noise-Area, long only
| phase | n | WR | $/trade [95 % CI] | net $ | PF | daily t / Sharpe | months > 0 | max DD |
|---|---|---|---|---|---|---|---|---|
| dev | 336 | 49.1 % | +256 [+104, +418] | +86,082 | 1.64 | 3.28 / 3.44 | 72 % | $10,433 |
| val-1 | 91 | 49.5 % | +102 [−206, +402] | +9,288 | 1.20 | 0.65 / 1.24 | 67 % | $16,847 |
| val-2 | 146 | 41.8 % | +134 [−362, +774] | +19,619 | 1.19 | 0.54 / 0.85 | 39 % | $29,589 |
Stress tier stays positive (val-1 +$7.5k, val-2 +$16.7k). 2025 +$24.8k, 2026 −$5.2k. Top-5 trades = 149 % of val-1 net and 308 % of val-2 net (one $36k trade).

## 8–9. Ranking and verdicts (pre-declared rules in `scripts/phase2/aggregate.py`; table in `runs/phase2/RANKING.md`)
PASS = base net > 0 in dev and every OOS phase, PF ≥ 1.15 in each OOS phase, pooled-OOS bootstrap CI > 0, ≥ 100 OOS trades, stress OOS net > 0.
| rank (pooled OOS $/trade, base) | strategy | verdict | note |
|---|---|---|---|
| 1 | A — R4 as frozen (all 9 cells) | PASS **on paper — INVALID**: contains the confirmation-minute leak | not a candidate in this form |
| 2 | A — R4 corrected, H2 S15/T40 | **MARGINAL** | OOS +0.16 R pooled, CI > 0; val-1 PF 1.14 < 1.15; stress val-1 ≈ 0 |
| 3 | A — R4 corrected, H2 S15/T30 | **MARGINAL** | val-1 PF 1.13 |
| 4 | A — R4 corrected, P14 S12.5/T30 | **MARGINAL** | val-1 +0.02 R / PF 1.03; stress val-1 negative |
| 5 | F — Noise-Area long | **MARGINAL** | positive in all phases and tiers, but OOS CI includes 0 and n = 237 |
| 6 | E — TORB | **FAIL** (dev negative) | OOS positive but CI includes 0; regime-driven |
| 7 | D — GC ROD | **FAIL** | |
| 8 | C — NQ ROD | **FAIL** | |
No strategy is a PASS after the R4 correction.

## 10. R4 / H2 old vs new — the discrepancy explained (decomposition in `runs/phase2/A_R4/decomposition_P14cell.json`, window 2022-01-01..2026-06-17)
| step | n | expR | PF | what changed |
|---|---|---|---|---|
| OLD evaluator, 1.0 pt flat (P14-392 reported +0.191 / 1.28 / n 5,672) | 5,671 | +0.192 | 1.28 | reproduced from the frozen grids: the old number is real for the old rules |
| OLD evaluator, zero cost | 5,671 | +0.272 | 1.44 | cost only |
| NEW tick engine, gross, target on TOUCH | 5,609 | +0.282 | 1.45 | fill at the first print after the decision boundary instead of the close of the next second: +0.010 R (the short fills ~1 s earlier in a falling market) |
| NEW gross, target THROUGH by 1 tick | 5,607 | +0.275 | 1.44 | −0.007 R: 12 fewer target fills |
| NEW base (fees + 1 tick/side) | 5,610 | +0.222 | 1.34 | −0.053 R |
| NEW stress (fees + 3 ticks/side) | 5,619 | +0.148 | 1.21 | −0.074 R |
| NEW base 2021–26 per-phase sums, as frozen → **confirmation-minute fires removed** | 6,276 → 5,483 | +0.225 → **+0.137** | 1.33 → **1.20** | the leak: −0.09 R; 2024 goes to ≈ 0 |
 Timezone, roll, contract selection, session boundaries, tick ordering and data holes produced NO difference (front contract identical on 1,370/1,370 sessions; fire seconds identical 299/299; 62 fewer trades come from the one-open-trade rule interacting with slightly different exit timestamps and from days excluded by the calendar). The old result therefore survives execution realism almost intact, and does NOT survive the availability correction in 2024.

## 11. Diagnostic patterns worth investigating next (diagnostics only — nothing was filtered)
* **R4 (corrected P14, base)**: profit concentrated in 08:00–10:00 CT (val-2 08:00 hour +$52.6k of $175k uncorrected) and in DOWN-trend regimes (val-2 DOWN +0.32 R vs UP +0.20 R; dev DOWN +0.24 vs UP +0.19); 2024 is the weak year in every cell; hours 11:00–12:00 CT ≈ 0; highest volatility quintile best in dev (+0.30 R) but not in val-1. All consistent with a "fast rejection in a falling tape" effect rather than a level effect.
* **F**: dev Sharpe 3.4 → OOS ~1; UP-regime days carry it (dev UP +$55k vs DOWN +$31k; val-1 DOWN −$6k; val-2 DOWN +$2k); Fridays −$25k in val-2; 2026 negative; single-trade dependence in OOS. Question for the next phase: is the long-only edge a 2021–23 bull-market artefact?
* **E**: 2022 −$113k (bear year), OOS gains in DOWN regimes (+$103k val-2) — the opposite sign of F's dependence; Mondays −$79k in dev. Unstable by construction (no stop, 6.5 h hold).
* **C**: negative in every OOS bucket; shorts worst; nothing to pursue.
* **D**: gross ≈ 0 in every year; nothing to pursue.

## 12. Which strategy should enter the hypothesis-improvement phase
**A (R4) — but only after its zone layer is re-derived causally in this project** (zigzag confirmation at bar close, tap engine, R4 fire) instead of replaying the old derived fire stream. The corrected pure-price cells are the only implementations with a pooled-OOS bootstrap CI above zero at base cost (+0.14 to +0.16 R on ~3,200 OOS trades) and 2025–26 remains clearly positive, but 2024 is ≈ breakeven and the stress tier erases val-1. Priority questions for that phase (to be pre-registered, tested once on validation-1, then validation-2): (i) does the effect exist on zones formed ≥ N minutes earlier only; (ii) hour-of-day and tape-regime dependence; (iii) is a wider bracket (H2 S15/T40) structurally better or just 2025-fitted.
**F** is the runner-up (positive in every phase and tier, but under-powered and single-trade dependent). C, D, E should not be improved.
