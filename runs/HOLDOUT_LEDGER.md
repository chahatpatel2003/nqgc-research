# HOLDOUT LEDGER — every holdout access, permanent record

- 2026-09-02T21:25:25+00:00 | HOLDOUT ACCESS | instrument=GC | spec=abc | purpose=unit test
- 2026-09-02T21:26:07+00:00 | HOLDOUT ACCESS | instrument=GC | spec=abc | purpose=unit test
- 2026-09-02T21:27:57+00:00 | HOLDOUT ACCESS | instrument=GC | spec=abc | purpose=unit test
- 2026-09-02T21:28:28+00:00 | HOLDOUT ACCESS | instrument=GC | spec=abc | purpose=unit test
- 2026-09-02T21:31:59+00:00 | HOLDOUT ACCESS | instrument=GC | spec=abc | purpose=unit test
- 2026-09-02T21:37:43+00:00 | HOLDOUT ACCESS | instrument=GC | spec=abc | purpose=unit test
- 2026-09-02T21:53:11+00:00 | LOCKED-PHASE ACCESS [NON-VIRGIN / STRATEGY-SPECIFIC HOLDOUT — researcher viewed this period in unrelated research; LOCKED] | instrument=GC | spec=abc | purpose=unit test
- 2026-09-02T22:41:46+00:00 | LOCKED-PHASE ACCESS [NON-VIRGIN / STRATEGY-SPECIFIC HOLDOUT — researcher viewed this period in unrelated research; LOCKED] | instrument=GC | spec=abc | purpose=unit test

> NOTE 2026-09-02: every entry above with purpose=unit test was produced by tests/test_guard.py constructing an Access object; no loader was called and no locked-period data was read. The tests now write to a temporary directory. No strategy has accessed a locked phase.
