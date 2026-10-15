# Research protocol (generation 1)

## Phases
| phase | window (trade dates) | allowed use | access |
|---|---|---|---|
| A development | NQ 2021-01-04..2023-12-31, GC 2016-01-04..2023-12-31 | implementation, debugging, limited hypothesis discovery, in-sample diagnostics | `Access("development")` |
| B validation | 2024-01-01..2024-12-31 (both) | ONE run per frozen spec to decide whether a modification is legitimate | frozen `spec_id` required |
| C holdout | NQ 2025-01-01..2026-08-14, GC 2025-01-01..2025-12-31 | ONE run per frozen spec, after validation passed, never for tuning | `spec_id` + unlock phrase + ledger entry |

Embargo: trades entering within 5 trade dates after a boundary are dropped from the later split's statistics.

## Lifecycle of a strategy
1. Write `strategies/<name>.py` from `_template.py`: RULES text, PARAMS, indicators. Register a row in `HYPOTHESIS_LEDGER.csv` (status=registered) BEFORE running anything.
2. Development runs (`--phase development`) as needed; every run is saved under `runs/`.
3. `scripts/freeze_spec.py` → immutable `specs/<name>_v<ver>_<spec_id>.json` with package + strategy file hashes. Any code change afterwards requires a new version.
4. Exactly one validation run (`--phase validation --spec-id`). Record the pre-registered gate and the outcome in the ledger. FAIL → back to step 1 with a new version; the validation year has now been seen once for this family — say so in the ledger.
5. Holdout: only for specs that passed validation; one run; result is final for this generation. Observed holdout results can never inform a modification that is tested on the same holdout.

## Pattern investigation rule (winners/losers by time, regime, weekday…)
Discover on development → write the rule and its gate into the ledger → one validation run → freeze → one holdout run. Never: look at holdout, change, re-run holdout.

## What a spec contains
strategy_name, version, instrument, timeframe, rules (plain language), parameters, dataset split, hypothesis id, entry/exit definitions, date frozen, package code hash, strategy file hash, spec_id (hash of the canonical spec).

## Reproducibility
`runs/<run_id>/manifest.json` records: engine/cost/prop-firm configs, all config files, package code hash, raw-data fingerprint (size+mtime of every raw file; sha256 manifest in `audit/RAW_DATA_MANIFEST.json`), seed, Python/package versions. The engine is deterministic; randomness (Monte Carlo, bootstrap) always takes the configured seed.

## Contamination disclosure carried into this generation
Earlier projects on this machine already observed parts of the holdout windows with other strategy families
(NQ 2025-H1 once by a Topstep search; NQ 2025-H2 by an order-flow study; NQ 2026-01..06 once by a levels study;
GC 2016–2025 by a levels/zones study). The only never-observed raw data on disk is NQ trades 2026-06-18..2026-08-14.
This generation's holdout is therefore "unseen by these strategies", not "unseen by the researcher". See docs/SPLITS.md.
