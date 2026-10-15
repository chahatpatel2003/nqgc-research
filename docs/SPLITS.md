# PROPOSED DATE SPLITS (generation 1) — on CME trade dates

| | NQ | GC | rationale |
|---|---|---|---|
| **Development** | 2021-01-04 → 2023-12-31 (3 yrs, ~750 sessions: 2021 bull, 2022 bear/high-vol, 2023 bull) | 2016-01-04 → 2023-12-31 (8 yrs) | all regimes available before the boundary; GC gets its long history |
| **Validation** | 2024-01-01 → 2024-12-31 | 2024-01-01 → 2024-12-31 | one full year, same window for both instruments so a portfolio can be validated jointly |
| **Final holdout** | 2025-01-01 → 2026-08-14 (≈ 400 sessions; MBP-1 only to 2025-06-30) | 2025-01-01 → 2025-12-31 | most recent regime (2025 tariff shock, 2026), aligned across instruments |
| embargo | 5 trade dates after each boundary | 5 | intraday strategies; removes boundary-straddling trades |

Enforced by `Access` on the trade date; validation needs a frozen spec; holdout needs the unlock phrase and a ledger entry.

## Honest contamination disclosure (must be read before trusting any holdout number)
Earlier projects on this machine already looked at parts of these holdout windows with *other* strategy families:
* NQ 2025-H1: one-shot test of a Topstep threshold-rule search (failed).
* NQ 2025-H2: opened by an order-flow / event-time study (all negative).
* NQ 2026-01 → 2026-06: one-shot levels-display test (failed).
* GC 2016–2025: a zones/levels study used 2016–2023 (discovery/validation) and sealed 2024/2025; a Topstep search touched GC 1-min families 2016–2025.
* **Never observed by anything: NQ trades 2026-06-18 → 2026-08-14 (41 sessions).**

Consequences: (1) the holdout is unseen by *these* strategies but not by the researcher; (2) any strategy that resembles a previously tested family (1-min threshold rules, order-flow imbalance, level-reaction fades) inherits that exposure; (3) the cleanest possible final check is the 41 virgin NQ sessions, which is far too few for a verdict on its own. The honest mitigation is to keep buying forward data: every month that passes adds virgin holdout for both instruments, and GC needs a 2026 extension before any GC holdout claim can be called clean.

## Alternative considered and rejected
Rolling the holdout forward (e.g. dev ≤2024, val 2025, holdout 2026+) would leave only 6–7 months of NQ holdout and zero GC holdout. Rejected until more data is purchased.
