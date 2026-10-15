# NQ/GC Research: a Leak-Safe Framework and a Re-Audit of Earlier Results

Generation-1 research framework for **NQ (Nasdaq-100) and GC (gold) futures**, built from scratch with one goal: **find out which earlier backtest results were real**.

It starts with a full data audit and a deterministic, leakage-protected backtest engine. It then re-tests prior strategies, published academic and practitioner rules, and an open-source strategy under one protocol, logging every hypothesis in a ledger. The headline result is a correction. **An earlier "edge" of +0.19 to +0.31 R per trade was produced by a chronology leak**, and the corrected, fully causal version has zero edge.

| | |
|---|---|
| **Instruments** | NQ (Databento trades, 2021 → 2026) · GC (1-minute bars, 2016 → 2025) |
| **Stack** | Python 3.12, Polars, DuckDB, PyArrow, NumPy, pandas, databento-dbn, pytest |
| **Scale** | ~6.8k lines of Python · 16 ledgered hypotheses · 5 phases with written reports |
| **Tests** | 53 pytest tests: 36 pass, 17 skip without the market data |

---

## The protocol

- **Data truth first.** These documents come before any strategy:
  - [`docs/DATA_INVENTORY.md`](docs/DATA_INVENTORY.md), [`docs/DATA_QUALITY.md`](docs/DATA_QUALITY.md) and [`docs/TIMEZONE_SESSIONS.md`](docs/TIMEZONE_SESSIONS.md): every file, defect, session, halt and holiday.
  - [`docs/CONTRACTS_ROLLS.md`](docs/CONTRACTS_ROLLS.md): the causal roll rule.
- **Splits with a contamination disclosure.** [`docs/SPLITS.md`](docs/SPLITS.md) defines development, validation-1, validation-2 and holdout. It also states openly which periods earlier projects had already looked at.
- **Leakage safeguards in the engine.** See [`docs/LEAKAGE_SAFEGUARDS.md`](docs/LEAKAGE_SAFEGUARDS.md):
  - every entry is stamped with when its information became available;
  - ambiguous same-bar stop/target outcomes are resolved conservatively;
  - raw data is write-protected (`nqgc.paths.assert_writable_target`).
- **Frozen specs and an access log.** Strategies are frozen in `specs/` before testing. Each run gets its own manifest in `runs/`. Every holdout access is recorded in `runs/ACCESS_LOG.jsonl` and `runs/HOLDOUT_LEDGER.md`.
- **One ledger for every idea.** [`HYPOTHESIS_LEDGER.csv`](HYPOTHESIS_LEDGER.csv) records each hypothesis: rule text, parameters, gates, validation result, holdout result, and "not recoverable" when the source could not be found. Nothing was fabricated to fill a gap.

## Results

| Phase | What was tested | Verdict |
|---|---|---|
| 2 | Recover and reproduce prior strategies; test published rules ("return over the last 30 minutes" on NQ and GC, NQ opening-range breakout, NQ noise-area) | **R4 tap-and-go reproduced, but 12.8 % of signals used a zone one minute before it was knowable.** The last-30-minutes rules failed on NQ (val −$99 and −$152 per trade) and on GC. The opening-range breakout failed by rule. NQ noise-area was marginal |
| 3 | The corrected, **fully causal R4** | **FAIL.** Zero-cost expectancy within ±0.007 R of zero on 5,400–5,700 trades in all nine cells; every cost tier negative. The old +0.19–0.31 R came from impossible entries ([report](docs/phase3/PHASE3_REPORT.md)) |
| 4 | Eight public strategy specs (A–H) on NQ and GC, including an open-source ORB-retrace strategy | Noise-area long **marginal**: pooled out-of-sample +$122/trade, CI [−210, +551], negative without its largest winner. ORB-retrace **marginal**. GC momentum and Crabel ORB **fail**. Four specs not recoverable ([master table](docs/phase4/MASTER_TABLE.md)) |
| 5 | Pre-open directional bias for NQ (BUY / SELL / NO BIAS at 09:29:59 ET), designed before any model existed | Development stage only. On the primary net-direction target, none of 16 naive rules beats always-BUY. A 136-feature causal matrix was built and passed its leakage tests. Validation not yet run ([design](docs/phase5/RESEARCH_DESIGN.md)) |

The lesson carried forward: **the most valuable output of a backtest framework is the ability to kill a result**, including your own earlier ones.

## Repository layout

```
├── TECHNICAL_README.md     original README: reading order, layout, setup
├── HYPOTHESIS_LEDGER.csv   every hypothesis and its verdict
├── configs/                instruments, costs, sessions, splits, prop-firm rules, observed calendars
├── src/nqgc/               paths and guard, calendar, contracts, data, bars, indicators, execution, risk, engine, stats, protocol, leakage
├── strategies/_template.py copy to create a strategy
├── specs/                  frozen strategy specifications (immutable)
├── scripts/                calendar builds, run_backtest.py, freeze_spec.py, phase drivers (phase2 … phase5)
├── audit/                  data audit outputs and raw-data manifest
├── runs/                   per-run manifests and stats, phase results, holdout ledger and access log
├── docs/                   protocol documents; phase2 … phase5 reports and specs
└── tests/                  DST, guard, bar semantics, indicator causality, engine timing/ambiguity, costs, stats
```

## Running it

```bash
git clone https://github.com/chahatpatel2003/nqgc-research.git
cd nqgc-research
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e .
.venv/bin/python -m pytest -q
```

**Data is not included.** Databento files are licensed. Trade-level run outputs (parquet), large audit dumps and run logs (which contain local paths and account identifiers) stay private, as do four academic papers used as sources. Tests that need the market data are skipped.

## Third-party material

- **Market data:** Databento NQ and GC data and Dukascopy XAUUSD (licensed; not included).
- **Published strategies re-tested here**, implemented independently from their published descriptions: Baltussen, Da, Lammers and Martens (*Journal of Financial Economics*, 2021) for the last-30-minutes rules; Zarattini, Aziz and Barbon (2024, "Beat the Market") for the noise-area rule; Toby Crabel's opening-range breakout. The papers themselves are not included.
- **Open-source ORB-retrace strategy:** a third-party backtester on GitHub was audited and its rule re-implemented. None of its code is included (checked: no shared code sequences).
- **Topstep:** prop-firm rules are modelled from Topstep's public documentation; this project is not affiliated with Topstep.
- **Open-source libraries** are installed as dependencies under their own licences; none are copied into this repository.

## Notes

- Assembled on 2026-10-14 from the original working folder. File contents are byte-identical to that snapshot (SHA-256 verified), except 2 files where a hardcoded local path was made portable: one document, and `audit/trades_audit.py`, which now keeps its DuckDB scratch space in `$NQGC_SCRATCH` (default: the system temp folder).
- Research software only. Nothing here is investment advice.

© Chahat Patel. All rights reserved. This notice covers the original code, documentation and research results in this repository. It does not extend to the third-party material listed above, which belongs to its respective owners. No license to reuse this code is granted; it is published for review.
