# CONTRACT / ROLLOVER AUDIT

## NQ — individual contracts (trades parquet + DBN batch)
* Representation: every expiry as its own symbol/instrument_id; nothing is continuous or adjusted. 28 outrights and 63 calendar spreads seen 2021–2026.
* Overlap: the next quarterly is liquid ~2 weeks before expiry; the third-out contract trades a few lots per day; far months (NQZ6 from 2023, NQZ9, NQZ7, NQM7, NQH7) have single-digit prints and absurd prices — never eligible as front.
* Expiry behaviour: last print of each front at 13:29/14:29 UTC of the third Friday (08:30 CT cash open, settlement).

### Proposed and implemented roll rule (causal)
`front(D) = argmax volume over outrights on the most recent completed trade date before D` (ties → nearer expiry).
* Uses only D−1 information; applied identically in backtest and live.
* Bootstrap day 2021-01-04 has no prior day → `bootstrap=True`, untradeable.
* Detected roll days (new front from that date): 2021-03-16 NQM1 · 2021-06-15 NQU1 · 2021-09-14 NQZ1 · 2021-12-13 NQH2 · 2022-03-15 NQM2 · 2022-06-14 NQU2 · 2022-09-13 NQZ2 · 2022-12-13 NQH3 · 2023-03-14 NQM3 · 2023-06-13 NQU3 · 2023-09-12 NQZ3 · 2023-12-12 NQH4 · 2024-03-12 NQM4 · 2024-06-18 NQU4 · 2024-09-17 NQZ4 · 2024-12-18 NQH5 · 2025-03-19 NQM5 · 2025-06-16 NQU5 · 2025-09-16 NQZ5 · 2025-12-16 NQH6 · 2026-03-17 NQH6→NQM6 · 2026-06-16 NQU6 (full table: `data_cache/nq_front_map.parquet`, `configs/calendar_observed_NQ.yaml`). This is 1 session after the true volume crossover — the price of not looking ahead.
* Roll day itself: `tradeable=False` (indicators spanning the contract switch are meaningless; the engine also refuses to hold across a symbol change).
* No back-adjustment, ever. A trading day never mixes contracts, so levels are real prices. Multi-day indicators (e.g. 20-day ATR) must be built from per-day statistics of the contract that was front on each day, or reset at rolls — never from a stitched price series.

## GC — vendor continuous `GC.v.0` (only source)
* Representation: one series, `symbol='GC.v.0'`, `instrument_id` identifies the underlying contract; 51 segments = 50 rolls 2016–2025 (contract months G, J, M, Q, V, Z; ~5 per year).
* Roll mechanics observed: switch at **00:00 UTC** (mid-session); **unadjusted** price jump (median |gap| 5.9 pts, max 57.7 pts); the outgoing contract's final UTC day is thin (135–992 bars, holes).
* Causality: Databento's `.v.0` selects the contract by the previous day's volume — causal by specification. It cannot be verified from the drive because no per-contract GC data exists. Treated as an unverified vendor assumption (flagged).
* Implemented handling: `roll_switch_date` (date containing the switch) and `thin_last_day` flagged per trade date → `tradeable=False`; indicators reset on `instrument_id` change (TR uses no prior close across segments); no attempt to back-adjust. Positions are never carried across a roll.

## Micro contracts
No MNQ/MGC data exists. Micro backtests use NQ/GC prices with the micro multiplier — the price path is the same underlying, but micro books are thinner; slippage assumptions for micros should be at least as conservative as for the minis.

## Recommendation
Buy per-contract GC data (Databento GLBX.MDP3 `GC.FUT` trades or 1-min OHLCV by contract) before any GC strategy is frozen: it would (a) verify the vendor roll, (b) allow a clean causal roll like NQ's, (c) remove the mid-session switch. Cost is small relative to the risk of trading a series whose construction cannot be audited.
