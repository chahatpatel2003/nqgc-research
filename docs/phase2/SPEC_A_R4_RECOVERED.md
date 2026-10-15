# STRATEGY A — R4 "tap-and-go": recovered frozen specification

Source project: `~/Desktop/trading agents /nq-levels` (formerly `~/Desktop/nq-levels`). All 23 files/derived layers listed in its
`HOLDOUT_FREEZE_MANIFEST.json` (Phase 17A, 2026-08-15) hash-match the files on disk today (verified 2026-09-02), so the code below is
the frozen code. Where the project itself contained several R4 variants, every variant is listed with its status.

| rule | exact content | supplied by |
|---|---|---|
| Data / clock | front contract = highest volume on the previous session (causal); 1-s bars from prints (bad-print filter vs strictly prior prints); prices in ticks; sessions = CME trade dates (17:00 CT open) | `src/nqlevels/build/roll.py`, `build/tape.py`, `configs/cme_calendar.yaml` |
| Volatility scale | `atr_t` = rolling 14-session mean of the session range, **shifted by one session** (prior sessions only) | `src/nqlevels/build/daily.py::add_rolling_scales` |
| Level construction | zigzag pivots on 1-minute bars at reversal thresholds 0.15 / 0.35 / 0.75 × ATR; a pivot HIGH becomes a resistance zone at its **confirmation minute** (first bar where the reversal from the extreme ≥ threshold), never at the extreme itself | `features/zones.py::zigzag_confirmed`, `make_zones`; RESEARCH_PLAN §18.2 |
| Band | half-width = clip(base_range/2, 4 ticks, 0.03 × ATR) where base_range = high–low of the 10 minutes ending at the pivot; prices stored roll-free (minus the session's chain adjustment) and shifted back into the current contract's scale on use | `features/zones.py` (BASE_MIN, HW_FLOOR_T, HW_CAP_ATR) |
| Level availability | zone usable from its confirmation minute (`form_min`) in the confirmation session, any time in later sessions; retired after 30 sessions or 6 taps | `features/interactions.py` (MAX_AGE_SESSIONS, MAX_TAPS) |
| Tap ("first touch") definition | screening on 1-min bars (bar low ≤ zhi and high ≥ zlo); the tap second = first 1-s bar inside that minute whose range overlaps the band; a new tap requires the zone to be armed: a 1-min close outside the band by max(8 ticks, half-width) since the previous tap AND ≥ 900 s since the previous tap; `tap_no` counts taps per zone across sessions | `features/interactions.py::process_session` (REARM_S, hysteresis) |
| Role filter | resistance role = approach from below (`app_side_above == 0`, using the close one second before the tap vs the zone mid); ≥ 1800 s of session left (`n_fwd >= 1800`) | `scripts/build_p14_fire.py`, `features/interactions.py::approach_features` |
| R4v10 confirmation ("go") | within 60 s of the tap second t, the first second f whose 1-s LOW is ≥ 10.0 pts (40 ticks) below the zone's near (lower) edge; decision at the end of second f | `scripts/p14_common.py` (R4_TICKS = 40, R4_WIN = 60, `fire_rows_for_session`); RESEARCH_PLAN §20.2 (a) |
| Entry | SHORT, market; fill = close of second f+k+1 for checkpoint k (ck0 → second f+1, ck2 → second f+3) | `p14_common.py` (CKPTS, `ck{k}_epx = cl[f+k+1]`), EXPERIMENT_LOG P14-387 |
| Stop / target | fixed points from the fill: stop above at fill + S, target below at fill − T; first passage on 1-s highs/lows; **same-second tie = stop** | `p14_common.py` (S_GRID/T_GRID, `first_cross`), `run_p18_stageb.py::h2_eval`, RESEARCH_PLAN §21.1 |
| Expiry / invalidation | if neither level is hit: exit at the session's last 1-s close (`ck_endpx`) | `p14_common.py`, `h2_eval` (`end`) |
| Session restriction | none (all sessions; `n_fwd ≥ 1800` only) | `build_p14_fire.py` |
| Portfolio rule | one open trade at a time, chronological (a fire during an open trade is skipped) | `run_p18_stageb.py::h2_eval`, `run_p14_final.py::portfolio` |
| Costs (old) | flat 1.0 pt round trip subtracted from every trade; stress +0.5 pt | `h2_eval(extra_cost)`, RESEARCH_PLAN §21.1 |
| Filters | tap_no ≤ 3 (chosen on pooled 2022–26, stated as such in P13-382); no speed/mono/model filters in the pure-price cells | EXPERIMENT_LOG P13-384, P18-403 |

## The three R4 variants that existed, and which are reproduced
| variant | definition | old result | status |
|---|---|---|---|
| **BALANCED / F4 (model-gated)** | above + HGB walk-forward probability gate + `fire_s ≤ 24 s`, `mono ≥ 0.27`; S12.5/T30 | dev +0.31..+0.45 R; **HOLDOUT A 2026-06-18..08-14: −0.133 R, PF 0.83 (FAIL)** | NOT mechanical (ML gate); P13-384 found its earlier gated numbers were look-ahead; already consumed the 2026-06-18+ window. Not reproduced. |
| **P14 "ungated tap≤3" cell** | tap ≤ 3, ck2 (fill at second f+3), S 12.5 / T 30 | 2022-01..2026-06: n 5,672, **+0.191 R, PF 1.28**, DD 53.4 R, every year +0.10..+0.27 | pure price rule → **reproduced (cell P14_ck2_S12.5_T30)** |
| **H2 "R4 wide-bracket" family** | tap ≤ 3, ck0 (fill at second f+1), S ∈ {15, 17.5, 20, 25} × T ∈ {30, 40} | all 8 cells positive in 10/10 half-year blocks (worst +0.00..+0.06); nested walk-forward pooled **+0.193 R** (worst block 0.000); "only surviving positive construction, never externally validated" | not one frozen cell; **all 8 cells reproduced, none selected** |
| FADE-1 (no R4) | first-touch fade at the near edge | P18 +0.342 R → **withdrawn** (P24: outcome model understated adverse; true ≈ −0.03 R) | not R4; not run |

## Ambiguities found (reported, not guessed)
1. "R4 TAP-AND-GO" is not a name used in the source project. The pure-price R4 constructions are the P14 cell and the H2 family; the model-gated Balanced strategy is the one that was actually frozen for the holdout and it already failed there. This report reproduces the pure-price cells only and labels them.
2. The old result window is 2022-01-01 → 2026-06-17 (2021 was fire-dataset warm-up); the new splits cut at 2023-12-31/2024/2025-06-17. Both views are reported.
3. The old evaluator fills targets on a 1-second LOW TOUCH and stops on a 1-second HIGH TOUCH at the exact level with no slippage; the new engine requires trade-through for targets and adds slippage to stops. The difference is decomposed in the results (legacy-cost tier isolates fills from costs).
