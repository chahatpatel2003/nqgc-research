# TIMEZONE / SESSION AUDIT (verified from the data, 2026-09-02)

## Stored timezone
* NQ trades, NQ MBP-1, NQ DBN batch, GC bars: all timestamps are **UTC nanoseconds**, tz-aware in the parquet metadata (`timestamp[ns, tz=UTC]`); DBN carries raw UTC ns.
* Proof from behaviour, not metadata: the Sunday Globex open appears at **23:00 UTC in winter** (e.g. NQ 2021-01-03 23:00, GC 2016-01-03 23:00) and **22:00 UTC in summer** (NQ 2023-07-02 22:00, GC 2016-07-31 22:00) — exactly 17:00 America/Chicago under both CST and CDT. Friday last prints at 20:59:59 UTC (summer) / 21:59:59 UTC (winter) = 15:59:59 CT.
* Caveat found during the audit: DuckDB renders timestamps in the *session* zone (this machine: America/Los_Angeles) unless `SET TimeZone='UTC'` — the framework's connections set it explicitly; the first audit tables had to be corrected for this. Never trust a printed timestamp without its offset.

## Conventions in the framework
* Internal clock: UTC. Conversions only via `zoneinfo` (`America/Chicago` for CME, `America/New_York` available). No fixed offsets exist in the code base.
* **CME trade date** = calendar date of (CT wall clock + 7 h). 17:00 CT Sunday → Monday's trade date. Verified against DuckDB predicate on DST-edge timestamps (2024-03-10, 2024-11-03).
* Half-year parquet files are cut at 00:00 UTC = 18:00/19:00 CT, inside the session. All selection is by trade date.

## Observed session structure
| | NQ (CME) | GC (COMEX) |
|---|---|---|
| Globex open | 17:00 CT (Sun–Thu) | 17:00 CT |
| close | 16:00 CT | 16:00 CT |
| maintenance | 16:00–17:00 CT: zero prints | 16:00–17:00 CT: zero bars (26 stray 16:00 settlement bars in 10 yrs) |
| intraday halt | **15:15–15:30 CT: no prints on any day up to 2021-06-25; prints every minute from 2021-06-28 onward** (CME removed the equity-index halt). Any strategy logic around 15:15 must be regime-aware | none |
| RTH used here | 08:30–15:00 CT (US cash equity hours) | 07:20–12:30 CT (legacy pit hours) — configurable; gold has no official RTH |
| holiday sessions | MLK, Presidents, Memorial, Juneteenth (from 2022), Independence, Labor, Thanksgiving: close 12:00 CT; day after Thanksgiving / Christmas Eve / Jul 3: 12:15 CT; Good Friday 2021/2023/2026: open until 08:15 CT (jobs report); 2025-01-09 (Carter mourning): 08:30 CT | same holidays: 12:00 CT ≤2021, **13:30 CT ≥2022**; day after Thanksgiving & Christmas Eve 12:45 CT |
| full closures | 12 (NQ 2021–26) | 29 (GC 2016–25) incl. Good Friday every year |
| DST transitions | handled by zoneinfo; Sunday-open timestamps shift 22:00↔23:00 UTC on the DST weekends as expected | same |

All observed dates are machine-generated into `configs/calendar_observed_NQ.yaml` and `configs/calendar_observed_GC.yaml`
(holidays, early closes, partial sessions, holes, roll flags). Manual corrections go in `configs/calendar_overrides.yaml`.
The engine flattens 5 minutes before an observed early close, and never earlier than the configured `flatten_by`.
