# Backtest engine architecture (generation 1, 2026-09-02)

```
raw T9 (read-only) ──► nqgc.data (guarded loaders, trade-date predicates)
                         │
                         ▼
   nqgc.contracts (causal front-month map / GC roll flags)   nqgc.calendar (UTC↔CT, trade date, sessions, observed holidays)
                         │
                         ▼
   nqgc.bars  (ts_open / ts_close availability semantics; no future fill)
                         │
                         ▼
   nqgc.indicators (causal; pivots carry confirmed_at)  ──► truncation/perturbation tests (nqgc.leakage)
                         │
                         ▼
   nqgc.engine.Backtester  ◄── nqgc.execution.CostModel (configs/costs_*.yaml)
        │                 ◄── nqgc.risk.PropFirmRules / AccountState (configs/propfirm_*.yaml)
        │                 ◄── TickResolver (NQ trade prints) for intrabar ordering
        ▼
   trade ledger (gross & net, R, MAE/MFE, ambiguity flags) ──► nqgc.stats ──► runs/<run_id>/{manifest,trades,stats}
                                                                  ▲
   nqgc.protocol: StrategySpec freeze (code hash), RunManifest, guard access log, holdout ledger
```

## Modules

| module | responsibility | key guarantee |
|---|---|---|
| `paths.py` | dataset locations, read-only assertion | any write path resolving under `/Volumes/T9` raises |
| `guard.py` | `Access(phase, instrument, spec_id, unlock)` | window clipped on CME trade date; validation needs a frozen spec; holdout needs spec + unlock phrase; every access logged |
| `calendar.py` | tz conversion via `zoneinfo`, trade date = CT clock + 7h, session labels, observed calendar | no fixed UTC offsets anywhere; DST unit-tested at both 2024 transitions |
| `contracts.py` | NQ front month = highest volume on the previous completed trade date; GC segment/roll flags | causal by construction; bootstrap day flagged |
| `data.py` | DuckDB/polars loaders; DBN decoder for the 2026 batch | trade-date predicate verified against the Python reference for DST edge cases |
| `bars.py` | trades→bars, GC 1m→bars, resample, regularize | `ts_close` is the availability time; synthetic bars filled from the past only; `check_bar_semantics` on entry to the engine |
| `indicators.py` | ATR/VWAP/rolling/session extremes/prior session/OR/confirmed pivots | each function passes `truncation_test` and `perturbation_test` |
| `execution.py` | tick size/value, per-side fees, slippage per order type, limit 'through' rule, fill price rules | nothing hardcoded; all from `configs/` |
| `risk.py` | sizing (fixed / $ risk / % risk), prop-firm account state (DLL, trailing DD, HWM, breaches) | parameters only |
| `engine.py` | event loop; fills strictly after signals; intrabar ambiguity handling; forced flatten; roll/session exits | `LeakageError` on any fill before its signal; strategy context bounded to bars[0..i] |
| `stats.py` | all required metrics + breakdowns; gross and net always | ambiguous trades reported separately |
| `protocol.py` | spec freezing (immutable JSON with code hash), run manifests, data fingerprint | reproducibility: same inputs + config ⇒ same ledger (tested) |
| `leakage.py` | truncation / perturbation / engine-truncation / fills-after-signals | used by tests and by `scripts/run_backtest.py` |

## Timing model
* Bar i: `[ts_open, ts_close)`. Strategy sees bar i at `ts_close[i]`.
* Market order → fills at `open[i+1]` ± slippage (`execution_lag_bars = 1`). The open of bar i+1 is the first print at/after `ts_close[i]`.
* Limit → fills in the first later bar whose range trades **through** the limit by ≥ 1 tick (`limit_fill_rule: through`); at the limit or at a better open.
* Stop → triggers on touch; fills at trigger (or the open if gapped through) + slippage.
* Position exits in bar j: stop touched / target traded-through / max-hold / flatten time / rule breach / roll / session end.
* Both stop and target inside one bar: `TickResolver` (NQ) decides from the actual print sequence; without it → `intrabar_ambiguity: worst` (stop first) and `ambiguous=True`.
* Entry inside a bar (stop/limit) without tick data: a touched stop counts as a loss; a touched target is not taken that bar.

## Multi-strategy portfolios
Each strategy runs alone and produces a ledger; portfolio construction (later phase) combines ledgers on the
common timeline under one `AccountState` so daily-loss / trailing rules apply jointly. Not built yet — by design
(no strategies exist yet).
