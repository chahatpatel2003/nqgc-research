# STRATEGY B — "NQ HF09C M30 trend pullback": NOT RECOVERABLE EXACTLY (not run)

## What the search found
* No file named or containing `HF09C` exists anywhere under `~` (Desktop, `trading agents /*`, `nq_strategy_research`, Claude project folders) or on `/Volumes/T9`. Searched by filename and by content (grep) across all `.py/.md/.json/.yaml/.csv/.txt` files, excluding virtualenvs.
* The only references are two memory notes of the earlier AURUM gold project (`~/.claude/projects/-Users-<user>-Desktop-long-term-bto-/memory/hf09c-execution-and-data-model.md`, `hf09cj-rejected-phase9.md`). They say the code lived in `~/Desktop/long term bto ` as `hf09c_live.py`, `backtester.py`, `strategies.py`, `execution_engine.py`, with ledgers in `runs/stability_c_trades.csv` and `runs/hf09c_{train,val,test}_trades.csv`. That folder now contains only the later GC-zones project (batch specs, `aurum/batch1..9`); none of those files or ledgers exist any more. The market data it used (`~/Desktop/MARKET DATA`, XAUUSD Dukascopy ticks) is also gone from that path.
* Search also covered `gold_trading_AGENT`, `Ai-trading-agent/gold`, `TRADING SYSYEM NQ PART 1` and `NQ (TOPSTEP)`: no HF09C, no M30 EMA pullback specification.

## What is known (memory note only — a summary, not the frozen rule set)
* Instrument: **XAUUSD spot (IC Markets MT5 / Dukascopy ticks), not NQ.**
* M30 bars; EMA(20/200) pullback, long and short; entries 12:00–20:00 UTC ("NY"); SL = 2.5 × ATR(14, Wilder); TP = exactly +2R; up to 3 concurrent positions; no daily flatten; Friday 20:00 UTC flatten + holiday calendar; signals at M30 bar close, tick-level execution.
* Reported baseline (research ledger, 2022–2026, 1,862 trades): 42.7 % win, +0.19 R expectancy, +353.8 R, PF 1.35, max DD 28.4 R.
* HF09CJ (25 % partial at +2R + chandelier trail) was rejected in "Phase 9" — the user's instruction to avoid it is consistent with the notes.

## What is missing (each one changes the strategy)
1. The pullback trigger itself: what defines a "pullback to EMA20" (touch? close beyond and back? wick? how many bars?) and the trend condition on EMA200 (price vs EMA200? EMA20 vs EMA200? EMA50 role — the note says EMA20/50/200 were recomputed).
2. Entry price convention (bar close vs next bar open vs stop order), and whether entries require the pullback bar to close in the trend direction.
3. Position-stacking rules for the ≤3 concurrent trades and their interaction with the SL/TP of earlier trades.
4. Holiday calendar and the exact Friday flatten mechanics (the note records ~22 weekend-spanning residual trades).
5. The frozen parameter file / version / hash. None exists on disk.

## Decision
Per the task rule ("if the specification cannot be recovered exactly, report that and do not fabricate it"), Strategy B is **not implemented**. Reconstructing an EMA-pullback rule from the two-line summary would be a new strategy, not a reproduction, and it would also be a cross-instrument transplant (gold spot → NQ futures) with no prior NQ result to compare against.

## If the user still wants an NQ M30 EMA-pullback test
It must be registered as a NEW hypothesis in `HYPOTHESIS_LEDGER.csv` with a freshly written rule set (development data only), not labelled HF09C.
