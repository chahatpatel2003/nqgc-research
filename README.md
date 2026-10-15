# nqgc-research — leak-safe NQ/GC futures research framework (generation 1)

Created 2026-09-02. Phase 1 deliverable: **data audit + deterministic, leakage-protected backtest framework**. No strategies exist yet, by design.

Raw data lives on the external T9 drive and is **never written to** (`nqgc.paths.assert_writable_target`).

## Read these first
* `docs/DATA_INVENTORY.md` — what exists, exact paths, rows, coverage
* `docs/DATA_QUALITY.md` — every defect found
* `docs/TIMEZONE_SESSIONS.md` — verified timezone, sessions, halts, holidays
* `docs/CONTRACTS_ROLLS.md` — contract representation and the causal roll rule
* `docs/SPLITS.md` — development / validation / holdout and the contamination disclosure
* `docs/ARCHITECTURE.md`, `docs/LEAKAGE_SAFEGUARDS.md`, `docs/RESEARCH_PROTOCOL.md`
* `docs/PRIOR_BACKTEST_RISKS.md` — what could have invalidated earlier work

## Layout
```
configs/            instruments, costs, sessions, splits, prop-firm rules, observed calendars (generated)
src/nqgc/           paths, guard, calendar, contracts, data, bars, indicators, execution, risk, engine, stats, protocol, leakage
scripts/            build_calendar_{gc,nq}.py, run_backtest.py, freeze_spec.py, hash_raw_data.py, smoke_real_data.py, audit helpers
strategies/         _template.py (copy to create a strategy)
tests/              31 tests: DST, guard, bar semantics, indicator causality, engine timing/ambiguity/rules, costs, stats
audit/              raw audit outputs (json/log/md) + RAW_DATA_MANIFEST.json
runs/               one folder per run (manifest, trades, stats) + ACCESS_LOG.jsonl + HOLDOUT_LEDGER.md
specs/              frozen strategy specs (immutable)
HYPOTHESIS_LEDGER.csv
```

## Setup / verify
```bash
cd ~/Desktop/nqgc-research
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e .   # or the packages in pyproject
.venv/bin/python -m pytest -q                      # 31 passed
.venv/bin/python scripts/smoke_real_data.py         # ~1 min, needs T9 mounted
.venv/bin/python scripts/run_backtest.py strategies/_template.py --phase development --start 2023-03-13 --end 2023-03-17
```
