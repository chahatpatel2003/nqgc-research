# DATA INVENTORY — T9 drive, inspected 2026-09-02 (read-only)

Drive: `/Volumes/T9` (Samsung T9, exFAT, 931 GiB, 278 GiB used). 131,130 files in the three data folders.
Nothing on the drive was modified; sha256 of the raw files is being written to `audit/RAW_DATA_MANIFEST.json`.

## A. NQ — Databento GLBX.MDP3 trade prints (individual contracts)  ← PRIMARY NQ SOURCE
| item | value |
|---|---|
| path | `/Volumes/T9/nq data/raw/trades/{2021_H1 … 2026_H1}.parquet` (11 files, 13.92 GB) |
| format | Parquet (parquet-cpp-arrow 24.0.0), pandas index `ts_recv`, ~65k-row row groups |
| schema | `ts_event`,`ts_recv` timestamp[ns, tz=UTC]; `rtype` u8 (=0, MBP-0/trade); `publisher_id` u16 (=1); `instrument_id` u32; `action` (='T'); `side` ('A' sell-aggressor,'B' buy-aggressor,'N'); `depth` u8 (=0); `price` f64 (index points, NOT 1e-9 fixed); `size` u32; `flags` u8; `ts_in_delta` i32; `sequence` u32; `symbol` |
| rows | **547,020,258** (per file 42.6–60.0 M) |
| coverage (ts_event) | 2021-01-03 23:00:00 UTC → 2026-06-17 03:03:02 UTC (**trade date 2026-06-17 is partial**: ends 22:03 CT the previous evening) |
| trade dates | 1,411 (2021-01-04 … 2026-06-17); 12 full-holiday closures, 52 early closes (see `configs/calendar_observed_NQ.yaml`) |
| contracts | every listed NQ expiry that traded: 28 outrights (NQH1 … NQH7) + 63 calendar spreads (`NQxn-NQym`). Files are NOT continuous — several expiries coexist every day |
| file cut | half-year files are cut at 00:00 UTC, i.e. **inside** a Globex session (18:00/19:00 CT); the H1/H2 boundary must never be treated as a session boundary |
| duplicates | `NQ_HOLDOUT/2025_H2.parquet` and `NQ_HOLDOUT/2026_H1.parquet` are byte-identical (sha256) copies of the raw files |

## B. NQ — Databento DBN batch (trades), NEW since the last project
| item | value |
|---|---|
| path | `/Volumes/T9/nq data/NQ_HOLDOUT/GLBX-20260815-69WTYRKTDB/glbx-mdp3-YYYYMMDD.trades.dbn.zst` (51 daily files, 269 MB) + `metadata.json`, `manifest.json` (sha256 per file), `condition.json` (all days "available") |
| query | dataset GLBX.MDP3, schema trades, symbols `NQ.FUT` (parent → all NQ outrights and spreads), stype_out instrument_id, encoding dbn+zstd, split by day |
| rows | **16,207,061** records, all rtype 0 / action T; price is 1e-9 fixed-point (÷1e9 → points) |
| coverage | 2026-06-17 22:00:00 UTC → 2026-08-14 20:59:58 UTC (trade dates 2026-06-18 … 2026-08-14, 41 trade dates) |
| symbols | NQU6 16.15 M rows; NQZ6 35.8 k; NQM6 4.3 k (to its 06-19 expiry); spreads 14 k |
| gap vs parquet | parquet ends 2026-06-17 03:03 UTC, batch starts 2026-06-17 22:00 UTC → **trade date 2026-06-17 is unusable** (RTH missing) |

## C. NQ — Databento MBP-1 (top-of-book + trades)
| item | value |
|---|---|
| path | `/Volumes/T9/nq data/raw/mbp1/{2021_H1 … 2025_H1}.parquet` (9 files, **222.1 GB**) |
| schema | trades schema + `bid_px_00, ask_px_00` f64, `bid_sz_00, ask_sz_00, bid_ct_00, ask_ct_00` u32; rtype = 1; actions A/C/M/T (+R at snapshots); flags 130 (F_LAST|F_MBP) normal, 168 snapshot rows at each file start with stale `ts_event` |
| rows | **7,893,313,081** (row-group footers; not re-scanned) |
| coverage (ts_recv) | 2021-01-01 00:00 UTC → **2025-06-30 23:59:59 UTC. No MBP-1 exists after 2025-06-30.** Row-group scan: no non-weekend gap > 2 h |
| boundary | 2023_H2 last record == 2024_H1 first record (one duplicated boundary row); H1/H2 cuts at 00:00 UTC |
| includes | all expiries and spreads; book prices for illiquid months can be absurd (asks to 2.1 M) — filter by symbol and action before use |

## D. GC — Databento GC.v.0 continuous 1-minute OHLCV  ← ONLY GC SOURCE
| item | value |
|---|---|
| path | `/Volumes/T9/Gc:Xauusd/gc/gc_{2016…2023}.parquet` + `Holdout/gc_2024.parquet`, `Holdout/gc_2025.parquet` (10 files, 54.4 MB); `Holdout/gc_2024_jan.parquet` is a verified identical subset of gc_2024 (ignored) |
| format | Parquet (parquet-cpp-arrow 21.0.0), index `ts_event` |
| schema | `ts_event` timestamp[ns, UTC] = **bar OPEN time**; `rtype` = 33 (OHLCV-1M); `publisher_id` = 1; `instrument_id` u32 (changes at rolls); `open,high,low,close` f64; `volume` u64; `symbol` = 'GC.v.0' everywhere |
| rows | **3,486,356** bars (≈348 k / year) |
| coverage | 2016-01-03 23:00 UTC → 2025-12-31 21:59 UTC; **2,580 trade dates**; only minutes with trades are present (no empty bars) |
| contracts | 51 instrument segments (50 vendor rolls); no individual-contract data for GC exists on the drive |
| resolution | 1-minute only — no ticks, no quotes, nothing finer (minimum spacing exactly 60 s, zero sub-minute records) |

## E. Present but NOT NQ/GC futures (recorded for completeness, not used)
| dataset | path | what |
|---|---|---|
| Dukascopy `USATECHIDXUSD` (NAS100 CFD) | `/Volumes/T9/DATA/NAS 100 Data/{raw (45,823 .bi5), parquet (117 monthly), processed (117)}` | CFD tick quotes 2012-02 → 2026-05, bid/ask; broker-priced index CFD, not CME NQ; different hours, no rolls, no volume |
| Dukascopy XAUUSD spot | `/Volumes/T9/DATA/XAUUSD Data` and identical copy in `/Volumes/T9/Gc:Xauusd/XAUUSD Data` | 1-min bid OHLC 2021-06-29 → 2026-06-28 + raw .bi5 ticks (29,565 files) |
| MT5 EA files | `/Volumes/T9/DATA/Gold Data` | `.ex5`/`.set` — not data |
| derived layers of the previous nq-levels project | `/Volumes/T9/nq data/nq_levels/{bars_1s, daily, profiles, sealed_holdout_1/2, …}` (2.7 GB) | derived, research-contaminated; never used as input here |

## Not present
* No MNQ or MGC data (micro contracts). MNQ/MGC backtests must use NQ/GC prices with micro multipliers (documented assumption; micro books are thinner, fills can be worse).
* No GC tick/quote data; no NQ MBP-1 after 2025-06-30; no NQ data after 2026-08-14; no GC data after 2025-12-31.
