# Lookahead / leakage safeguards — what is implemented and how it is verified

Core rule: at timestamp T the strategy may only know what existed at or before T.

| # | risk | safeguard | where | verified by |
|---|---|---|---|---|
| 1 | lookahead through bar timestamps | bars carry `ts_open` and `ts_close`; the strategy is invoked at `ts_close[i]` with `bars[0..i]` only (`BarContext`) | `engine.py`, `bars.py` | `test_strategy_cannot_see_future`, `check_bar_semantics` |
| 2 | same-bar execution | orders created at close of bar i are only evaluated from bar i+1; `LeakageError` if an order is evaluated in its own bar or a fill precedes its signal | `engine.py` | `test_market_fills_next_bar_open_plus_slippage`, `fills_after_signals` assertion in `run_backtest.py` |
| 3 | intrabar stop/target ordering from OHLC | both-touched → tick sequence (`TickResolver`) or conservative 'worst' + `ambiguous=True`; 'best' not offered; intrabar entries never take a same-bar target without ticks | `engine.py`, `configs/costs_default.yaml` | `test_both_touched_without_resolver_is_stop_and_ambiguous`, `test_tick_resolver_decides_order`, `test_intrabar_entry_target_not_taken_same_bar_without_resolver` |
| 4 | future volatility (ATR) | `atr()` uses completed bars ≤ i only; TR resets at session/contract boundaries | `indicators.py` | truncation + perturbation tests |
| 5 | future session high/low | `session_running_extremes` = cummax/cummin through bar i; final-session values are never exposed; prior-session levels are shifted by one trade date | `indicators.py` | `test_session_extremes_are_running_not_final`, `test_prior_session_levels_are_previous_day` |
| 6 | future swings/pivots | `confirmed_pivots` returns `confirmed_idx = pivot_idx + right`; `known_last_pivot` only exposes a pivot from `confirmed_idx` onward | `indicators.py` | `test_pivots_known_only_after_confirmation` (+ truncation) |
| 7 | future VWAP | `session_vwap` is a cumulative ratio within the trade date | `indicators.py` | truncation test |
| 8 | final value of a developing indicator (OR, VWAP, day range) | opening range exposed only for bars with `ts_close ≥ OR end`; all cumulative indicators are running values | `indicators.py` | `test_opening_range_unavailable_before_end` |
| 9 | forward-filling from the future | `regularize` fills synthetic bars from the previous bar only | `bars.py` | `test_regularize_fills_from_past_only` |
| 10 | survivorship-like contract selection | front month for date D chosen from D-1 volume only; bootstrap day untradeable; day never mixes contracts; no back-adjustment; GC roll-switch and thin days untradeable | `contracts.py`, `run_backtest.py` | roll table in `configs/calendar_observed_*.yaml`; front map built once under logged infrastructure access |
| 11 | holdout contamination | `Access` windows on the trade date; validation needs a frozen spec; holdout needs spec + unlock phrase; ledger + access log | `guard.py`, `protocol.py` | `test_guard.py` |
| 12 | data-file boundary leakage (files cut at 00:00 UTC mid-session) | loaders select by trade date across file boundaries, never by file | `data.py` | smoke test: 2 trade dates → exactly 2×1380 bars |
| 13 | time-zone / DST errors | `zoneinfo` everywhere; trade date = CT + 7h; DuckDB predicate cross-checked against Python on DST edge timestamps | `calendar.py`, `guard.py` | `test_calendar.py`, predicate check in smoke |
| 14 | indicator computed with centred/future windows by accident | every indicator must pass `truncation_test` and `perturbation_test` before use (policy in `strategies/_template.py`) | `leakage.py` | `test_indicators.py` |
| 15 | non-determinism | no randomness in the engine; seeds in config for MC/bootstrap; manifests store configs, code hash, data fingerprint | `protocol.py` | `test_deterministic_and_truncation_invariant` |
| 16 | gross-only judgement | fees and slippage always applied; gross and net both reported; ambiguous trades counted separately | `stats.py` | `test_summary_and_breakdowns` |
| 17 | silent bad prints | outright tick alignment asserted on load; jump audit documented; GC OHLC sanity asserted | `smoke_real_data.py`, audit | audit tables |
| 18 | writes to raw data | `assert_writable_target` in every writer; T9 opened read-only | `paths.py` | manual review + sha256 manifest |

Not yet implemented (later phases): Monte-Carlo reshuffle, bootstrap CIs, parameter perturbation, walk-forward harness, regime slicing. They will consume the ledger and must not touch the engine.
