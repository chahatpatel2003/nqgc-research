# Exact specifications for strategies C–F (as implemented) and ambiguities

## C — NQ rest-of-day → last-30-minute momentum (Baltussen, Da, Lammers, Martens, JFE 2021)
Paper (audit/baltussen2021.txt, Table 1 and Appendix): NQ trading day 09:30–16:00 EST; ROD = previous close → 30 min before close;
LH = last 30 min; timing strategy = long LH if r_ROD > 0, short if < 0. Implemented exactly as the task specified:
`prev_close` = last print at/before 16:00:00 ET on the previous trade date for today's front contract (roll days: targeted raw query for
the new front's previous-day print); `P_1530` = last print at/before 15:30:00 ET; signal at the 15:30:00 boundary; entry = first print
strictly after the boundary + slippage; exit = last print at/before 16:00:00 ET − slippage; zero → no trade; one trade/day; no stop/target/filters.
Days: NQ trade dates with a 16:00 ET close (52 early-close days, the 2026-06-17 partial day and the 2025-11-28 hole excluded).
Ambiguity: none material. (The paper's Sharpe for NQ is not reproduced here because the paper trades 1974–2020 index/futures data with
different costs; only the rule is tested.)

## D — GC rest-of-day → last-30-minute momentum (same paper; Table 1: COMEX GC 08:20–13:30 EST)
1-minute bars only. `prev_close` = close of the last completed bar with ts_close ≤ 13:30:00 ET on the previous eligible day;
`P_1300` = close of the last completed bar with ts_close ≤ 13:00:00 ET (the 12:59 bar, known at 13:00:00); entry = open of the first
bar with ts_open ≥ 13:00:00 ET + slippage; exit = close of the last bar with ts_close ≤ 13:30:00 ET − slippage. Excluded: roll-switch dates
(37), thin roll days (51), holes, early closes (the 12:00/13:30 CT closures make the 13:30 ET window absent or degenerate).
Ambiguity: on GC the 13:00→13:30 ET window is the post-London, pre-COMEX-settlement half hour in the electronic session, not a
floor close; the paper's "trading hours based on volume patterns" is honoured, but the 13:30 ET "close" is a wall-clock boundary, not a fixing.

## E — NQ 1-minute TORB (Tsai et al., IEEE Access 2019; rules per the task text — the paper PDF could not be fetched, abstract only)
OR = prints with 09:30:00 ≤ ts < 09:31:00 ET (front contract); OR_HIGH/OR_LOW = max/min; after 09:31:00 the first print strictly above
OR_HIGH → long, strictly below OR_LOW → short, whichever first; signal = that print's ts_event; entry = next print + slippage;
exit = last print at/before 16:00:00 ET − slippage; one trade/day; no stop/target/filters; breakouts after 16:00 ET ignored.
Ambiguity: the paper's "timely" window (maximum delay for the breakout) was not recoverable from the abstract; per the task, no timely cut-off is applied.

## F — NQ Noise-Area momentum, LONG ONLY (Zarattini, Aziz, Barbon 2024, SSRN 4824172; full text in audit/zarattini2024.txt)
Equations (verbatim from the paper): move_{t−i,HH:MM} = |Close_{t−i,HH:MM}/Open_{t−i,09:30} − 1|, i = 1..14; σ_{t,HH:MM} = mean_i(move);
UB = max(Open_t, Close_{t−1,16:00}) × (1 + σ); LB = min(Open_t, Close_{t−1,16:00}) × (1 − σ). "Trading is restricted to semi-hourly intervals,
specifically at HH:00 and HH:30." "Positions are unwound either at market Close or if there is a crossover to the opposite boundary…
Stop losses can also be triggered only on semi-hourly intervals." Final model: "Long TrailingStop = max(UB, VWAP)", VWAP from market hours
only; "as soon as the price crosses either the current band or the VWAP, the position is closed."
Implemented: 1-min bars 09:30–16:00 ET from front ticks; checks at 10:00, 10:30, …, 15:30 ET using the last completed 1-min close; LONG when flat
and close > UB; exit when close < max(UB, VWAP) at a check; forced flat at the 16:00 ET boundary; fills at the next bar open + slippage;
re-entry allowed at later checks; 1 contract (the paper's vol-target sizing omitted — sizing, not signal); σ history restarts at each phase boundary
(first 14 eligible sessions of a phase are warm-up).
Ambiguities (flagged): (a) whether the trailing stop is evaluated only at semi-hourly checks (paper says stops trigger only semi-hourly — used) or
continuously; (b) whether re-entry after a stop is allowed (paper does not forbid; its trade counts imply > 1 trade/day — allowed);
(c) the first check time (10:00 ET used; at 09:30 σ = 0).

## Cost tiers (all strategies)
| tier | NQ per contract | GC per contract |
|---|---|---|
| GROSS | $0 | $0 |
| BASE | fees $2.40/side + 1 tick/side slippage on market & stop fills = **$14.80 RT (0.74 pt)** | fees $2.57/side + 1 tick/side = **$25.14 RT** |
| STRESS | fees + 3 ticks/side = **$34.80 RT (1.74 pt)** | fees + 3 ticks/side = **$65.14 RT** |
