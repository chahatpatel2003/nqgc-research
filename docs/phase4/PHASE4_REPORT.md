# PHASE 4 — multi-strategy screening (2026-09-02)

Splits unchanged (NQ dev 2021-01-04..2023-12-31, val-1 2024, val-2 2025-01-01..2026-06-17; GC dev 2016..2023, val 2024). Locked windows (NQ 2026-06-18..08-14, GC 2025) never read. Costs per contract: ZERO; BASE NQ $14.80 RT (0.74 pt) / GC $25.14 RT; STRESS NQ $34.80 / GC $65.14; 2×STRESS NQ $64.80 / GC $125.14. Master table: `docs/phase4/MASTER_TABLE.md`; per-strategy reports: `runs/phase4/*/REPORT.md`; specs: `docs/phase4/SPEC_*.md`.

## 1. Specifications used
* A — Noise-Area long only: unchanged Phase-2 implementation of Zarattini/Aziz/Barbon 2024 (`SPEC_A_NOISE_AREA_LONG.md`).
* D — ORB retracement / volume profile: `dws-data/nas-orb-backtester` (commit 03b28ee), mechanics recovered from the code (`SPEC_D_ORB_RETRACE_VP.md`): ORB 09:30–09:45 ET, VP 24 rows / 70 % value area from the ORB bars, direction = first 1-min close beyond the ORB, confirmation = close beyond ORB + t % of ORB size, retrace entry at VAH/POC/VAL, stop = ORB extreme, target = ORB extreme + 1 × ORB size, EOD 16:00 ET. Grid = the repo's own (t ∈ {10,15,20,25,30} × level ∈ {VAH,POC,VAL}); all 15 cells reported.
* F — GC fifth-half-hour → last-half-hour timing (Wen et al. 2020 for gold, construction of Gao et al. 2018) (`SPEC_F_GC_INTRADAY_MOMENTUM.md`).
* G — GC Crabel Stretch ORB, 08:20–13:30 ET day session, 10-day stretch, multiple 1, exit at the session close (`SPEC_G_GC_CRABEL_ORB.md`).
* B, C, E, H — SPEC_NOT_RECOVERABLE (see the four spec files): Early Bird paper paywalled (abstract only); no S/R first-touch repository exists anywhere on this machine or in any prior transcript; the gap-reversal futures papers (Fung/Mok/Lam 2000, Grant/Wolf/Yu 2005) are paywalled and the only obtained text is a stock-market thesis; no exact published GC intraday mean-reversion rule exists (Mesfin 2026 reports OU failures on MGC without defining the signal).

## 2. Implementation ambiguities
* D: the repo's `instruments/config.py` is missing → spread_pct, stop_buffer_pct, entry_cutoff, force_close and the "filtered" (market-structure) variant selection are unknown; run with spread 0, buffer 0, no entry cutoff, force close 16:00 ET, unfiltered. The README headline (+0.42 R long / +0.56 R short, "filtered") is therefore not reproducible.
* F: ETF (GLD) window mapped to GC on the same ET clock; the predictor half-hour was chosen in-sample by the paper.
* G: multiple 1 (Crabel) rather than 2 (oxfordstrat replication); entry allowed inside the opening minute.
* A: unchanged Phase-2 ambiguities (semi-hourly stop checks, re-entry, first check 10:00 ET).

## 3. Leakage / execution issues found in original sources
* D repository: entry fills at the touched level (optimistic), stop and target fills at exact levels with no slippage, "filtered" results rely on a partial-bar market-structure tracker whose config is absent. Core rule (VP from ORB bars, close-based confirmation, target disabled on the entry bar, stop priority) is causal. Repository-faithful vs corrected (trade-through fills + slippage) differ by only 0.01–0.04 R per cell — the repo's optimism is small; its headline numbers come from the missing filter, not from fills.
* Phase-3 recap (already reported): the archived R4 level layer had a confirmation-minute availability leak. No leakage found in the published rules of A, F, G.

## 4–6. Survived / failed / decayed (BASE cost)
| strategy | dev | val-1 | val-2 | verdict | why |
|---|---|---|---|---|---|
| A Noise-Area long | +$256 (n 336, PF 1.64) | +$102 (n 91, PF 1.20) | +$134 (n 146, PF 1.19) | **MARGINAL** | pooled OOS +$122/trade with CI [−210, +551]; OOS net $28.9k becomes **−$7.3k without the single 2025-04-09 trade (+$36.2k)**; top 1 % of trades = 176 % of OOS profit; 2026-H1 −$84/trade (PF 0.90); monthly hit rate fell 75 % (2021) → 33 % (2026). Cost-robust (2× stress OOS +$17k). **Decayed / single-trade dependent.** |
| D ORB-retrace family (15 cells) | 14/15 positive, +0.04..+0.19 R | 7/15 negative, −0.09..+0.17 R | 15/15 positive, +0.16..+0.33 R, PF 1.21–1.52 | **MARGINAL** (family) | pooled family by year: 2021 +0.08, 2022 +0.18, 2023 +0.05, 2024 +0.02, 2025 +0.33, 2026-H1 +0.08 R; 8 of 22 quarters negative (2023-Q2 −0.24, 2024-Q1 −0.23, 2025-Q2 −0.14, 2026-Q2 −0.36 vs 2025-Q1 +0.73); excl. top-5 winners still positive in every cell; 2× stress OOS positive in every cell; one cell (T15_val) meets every PASS condition but is 1 of 15 correlated cells (2024 +0.01 R, 2026-H1 −0.015 R) — multiplicity, not a PASS of the family. |
| G GC Crabel ORB | −$2 (gross +$23, PF 1.08 gross) | +$18 (PF 1.04) | locked | **FAIL** | gross edge ≈ 1 tick; negative at stress; validation profit = a handful of trades (top 1 % = 345 % of net). |
| F GC 5th-half-hour momentum | −$26 (PF 0.63; gross ≈ 0) | +$1 (PF 1.01) | locked | **FAIL** | no gross edge; the ETF finding does not transfer to GC futures. |
| B, C, E, H | — | — | — | NOT TESTED | specifications not recoverable. |

## 7. Correlation
A and the D family are uncorrelated out of sample: daily P&L correlation −0.04, monthly −0.18; both lose on 5.6 % of OOS days; every D cell vs A: −0.01 to −0.08. The 15 D cells are one exposure (same days, same direction).

## 8. Equal-risk bucket (only strategies profitable after base costs; D as the equal-weight average of its 15 cells, no cell selected)
Weights (inverse daily volatility): A 0.40, D-family 0.60. Out of sample (2024 + 2025-2026H1, 610 days): total +$41.4k per weighted contract, Sharpe 1.25, max drawdown $11.4k; full sample Sharpe 1.47. Caveat: A's OOS contribution is essentially one trade, so the bucket's OOS Sharpe is not a robust estimate; the D family carries it in 2025.

## 9. Diagnostic hypotheses for the next phase (NOT tested; each needs a pre-registered single run)
1. **D — entry cutoff at 12:00 CT.** Pooled family expectancy by entry hour (CT): 08:00 +0.10, 09:00 +0.19, 10:00 +0.07, 11:00 +0.37, 12:00 −0.27, 13:00 +0.17, 14:00 −0.22 R. The repository clearly had an `entry_cutoff` (it records `entry_delay_mins`); a cutoff is spec-faithfulness as much as an improvement. Market reason: late retracements after a morning breakout are no longer "retracements", they are range failures.
2. **D — short vs long.** Shorts +0.17 R (n 5,395) vs longs +0.09 R (n 5,653) pooled; the README also reports a stronger short side. Reason: down-side breakouts in an index are faster and less crowded. Must be checked for per-year recurrence before any restriction.
3. **A and D — trend-regime dependence.** Both do better when the prior close is above its 20-session mean (A: UP $269 vs DOWN $108 per trade; D: UP +0.15 vs DOWN +0.09 R) and both had their best year in 2025. Reason: momentum/breakout families need trending tape. Also worth a single run: the paper's ORIGINAL two-sided noise-area rule (long+short) to test whether the long-only restriction is itself the source of A's fragility.
