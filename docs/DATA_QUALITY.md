# DATA QUALITY FINDINGS (full-content audit, 2026-09-02)

## NQ trades (547 M rows, every file fully scanned — audit/trades_audit.json, audit/trades_audit_summary.md)
| check | result |
|---|---|
| nulls / size ≤ 0 / price ≤ 0 on outrights | none. `price ≤ 0` rows (431 k in 2021–22H1) are all calendar spreads (negative spread prices are legitimate) |
| tick alignment | **100 % of outright prints are multiples of 0.25.** All off-tick prints (2.13 M) are calendar spreads (spread tick 0.05) |
| `ts_recv` order | non-decreasing in every file (files are in capture order) |
| `ts_event` order | rare inversions (≈1 in 3 M) → every consumer sorts by `(ts_event, sequence, file row)` |
| `ts_event > ts_recv` (impossible in principle) | 2023_H1: 413,996 rows (0.8 %), 2025_H2: 2,243, otherwise ≤ 200 — capture-clock skew, max 125 ms; recorded, not corrected |
| feed latency `ts_recv−ts_event` | median 235–302 µs, p99 3–18 ms, worst 1.7 s (2025_H2) |
| `flags` | 0 except `4` (F_MAYBE_BAD_BOOK) on 29,600 rows (2022_H1), 3,892 (2022_H2), 87,604 (2025_H2), 86,706 (2026_H1). Book-consistency flag; trades unaffected. `F_LAST` never set |
| identical repeated prints | 342–478 k exact-duplicate groups per file: Databento emits one record per fill; an aggressor sweeping equal resting orders yields identical rows. **Kept** (dropping them understates volume) |
| `(ts_event, sequence)` not unique | 2.1–3.8 M groups per file — `sequence` is per-event, not per-fill. Never use it as a unique key |
| print-to-print jumps > 1 % on outrights | 18–131 per half-year, **all in illiquid deferred months** (NQZ6, NQZ9, NQH3 in 2022, NQU5 in 2024 …) where a 1-lot prints against a stale level. None found on the front month at > 0.5 % in sampled days. The front-contract filter removes them; a causal bad-print guard (price vs. last N prints of the same contract) is still available in the engine's bar builder if needed |
| session structure | 17:00 → 16:00 CT with the 16:00–17:00 maintenance break; 1,380 traded minutes on a normal day; **the 15:15–15:30 CT equity-index halt is visible in the data only until mid-2021** (see TIMEZONE_SESSIONS.md) — after that, prints exist in every minute |
| holidays (no data) | 2021-12-24, 2022-04-15, 2022-12-26, 2023-01-02, 2023-12-25, 2024-01-01, 2024-03-29, 2024-12-25, 2025-01-01, 2025-04-18, 2025-12-25, 2026-01-01 — all CME closures. **No unexplained missing weekday.** |
| early closes (12:00 / 12:15 CT holiday sessions; 08:15 Good-Friday sessions 2021/2023/2026; 08:30 on 2025-01-09) | 52, listed in `configs/calendar_observed_NQ.yaml` |
| data holes inside sessions | **one**: 2025-11-28, 02:48 → 13:30 UTC (646 min, overnight before the Black-Friday half-day). Same hole exists in GC → vendor outage |
| partial sessions | 2026-06-17 (parquet ends 03:03 UTC; DBN batch starts 22:00 UTC) → excluded |
| file boundaries | cut at 00:00 UTC mid-session; loaders select on the trade date, never on the file |

## NQ DBN batch (16.2 M rows, fully decoded)
Same semantics as the parquet trades; `ts_recv` monotone; front contract NQU6; spreads present (off-tick prints are spreads only). 41 complete trade dates 2026-06-18 … 2026-08-14. Manifest sha256 present for every file (not yet cross-verified — see hash manifest).

## NQ MBP-1 (footers + row-group statistics + sampled row groups)
* 7.89 bn rows, continuous 2021-01-01 → 2025-06-30, no non-weekend gap > 2 h at row-group granularity.
* Sampled RTH row group (2024-03-13): actions C 46 % / A 44 % / T 7 % / M 3 %; spread 1 tick 65 %, 2 ticks 34 %; 91 % of buy-aggressor trades print at the ask, 91 % of sell-aggressor at the bid (consistent book).
* Boundary duplicate row between 2023_H2 and 2024_H1; snapshot rows (flags 168) at each file start carry stale `ts_event` — must be filtered by `flags & 32`.
* Not scanned row-by-row in this phase (would take ≈ 1 h per pass); the prior project's finding that `sequence` ties within a sweep require `(ts_event, sequence, row)` ordering is consistent with what was sampled.

## GC 1-minute bars (3.49 M rows, fully scanned)
| check | result |
|---|---|
| duplicate timestamps | 0 |
| spacing | minimum exactly 60 s; 99.3 % of consecutive bars are 60 s apart; larger gaps = no-trade minutes, breaks, closures |
| OHLC sanity (H ≥ max(O,C), L ≤ min(O,C), H ≥ L, prices > 0) | 0 violations |
| tick alignment (0.1) | 0 violations in O/H/L/C |
| zero / null volume | 0 |
| 1-min close-to-close jumps > 1 % | 22 — **all at vendor roll switches (00:00 UTC) or Sunday opens after macro events**; largest −3.1 % at 2020-03-01 23:00 UTC (Sunday open, COVID) |
| bar range > 1.5 % | 7 (2021-08-08 22:57 UTC flash crash 2.6 %; NFP/CPI/FOMC minutes) — genuine |
| holidays (no data) | 29, all CME closures (Good Friday, Christmas, New Year) **plus 2020-02-28 which is a normal Friday → vendor hole** |
| early closes | 73 observed: Monday holidays 12:00 CT (≤2021) / 13:30 CT (≥2022); day-after-Thanksgiving & Christmas Eve 12:45 CT; Thanksgiving 12:00/13:00 — listed in `configs/calendar_observed_GC.yaml` |
| data holes inside sessions | 2019-02-27 (18:43→21:45 CT), 2020-02-27/28 (hole spanning the whole 02-28 session), 2020-06-30 (09:10→19:00 CT), 2024-11-28 (Thanksgiving thin), 2025-11-28 (02:48→13:30 UTC, same as NQ), 2018-04-29 (Sunday open 30 min late), 2018-08-05 (one stray bar at 16:59 CT Sunday), plus ~10 roll-day thin windows |
| stray 16:00 CT bars | 26 bars stamped 16:00 CT (after the close) — settlement prints; harmless, excluded by session labels (MAINT) |

## GC continuous-contract artefacts (the important ones)
1. **Roll switches happen at 00:00 UTC = 18:00/19:00 CT, inside the Globex session.** 50 switches in 10 years (≈5/year: G, J, M, Q, Z and sometimes V). Median absolute switch gap 5.9 pts, max 57.7 pts (2025-07-31). Any return, ATR, VWAP or level that spans 00:00 UTC on a roll date is contaminated by the basis jump.
2. **The vendor rule lags one day**: the last UTC day of each segment is spent on the outgoing contract while volume has already migrated. Those 51 trade dates have 135–992 bars instead of ~1,380 (sparse, wide) and some contain multi-hour holes. They are flagged `thin_last_day` and are untradeable by default.
3. `GC.v.0` cannot be reproduced or audited from the drive: no individual-contract GC data exists. The roll rule is causal per the vendor's specification (previous day's volume) but could not be independently verified here.
