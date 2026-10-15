# Phase 5 — feature bank v1 (`src/nqgc/bias/features.py`)

All features for day D are computed from (i) NQ front-contract prints with timestamp < 09:30:00.000 ET on D,
(ii) RTH statistics of sessions strictly before D, (iii) deterministic calendar facts. Nothing else.

Notation: `R20` = median 09:30–12:00 range of the previous 20 RTH sessions (points). `σ20` = standard deviation of
daily close-to-close returns over the previous 20 RTH sessions (fraction). `p0929` = last print before 09:30 ET.
"Cont" prices subtract the causal cumulative roll spread `adj` (Phase-3 `nq_roll_adjust.parquet`), so cross-day
differences never contain a contract roll. Suffix `_r` = divided by R20, `_s` = divided by σ20 (in return units).
`sgn` = Databento aggressor side (B = buy aggressor, A = sell aggressor); imbalance = (buy − sell) / (buy + sell) in contracts.

## A. Pre-open windows (6 windows × 9 = 54)

Windows on trade date D (ET): `asia` = session start (≈18:00 previous evening) → 02:00; `eu` = 02:00 → 08:30;
`data` = 08:30 → 09:00; `last30` = 09:00 → 09:30; `pre4` = 04:00 → 09:30; `on` = session start → 09:30.

| feature | definition |
|---|---|
| `f_{w}_ret_r` | (last print − first print) of the window / R20 |
| `f_{w}_rng_r` | (high − low) / R20 |
| `f_{w}_rv_ratio` | √Σ(5-min log returns²) / median of the same quantity over the previous 20 RTH sessions |
| `f_{w}_vol_ratio` | contracts traded / 20-session median |
| `f_{w}_n_ratio` | number of prints / 20-session median |
| `f_{w}_imb` | aggressor volume imbalance |
| `f_{w}_big_imb` | aggressor imbalance of prints ≥ 10 lots |
| `f_{w}_vwap_dist_r` | (p0929 − window VWAP) / R20 |
| `f_{w}_nrev` | zigzag reversals ≥ 0.25·R20 on 1-min closes |

Plus `f_on_ret_pct` (overnight return as a fraction of the session-start price).

## B. Previous session's post-close window 16:00–17:00 ET (3)
`f_pc_ret_r`, `f_pc_vol_ratio`, `f_pc_imb` (same definitions, on the last RTH session's post-close prints).

## C. Overnight extras (26)

| feature | definition |
|---|---|
| `f_on_pos_in_range` | (p0929 − overnight low) / (overnight high − low) |
| `f_on_min_since_high`, `f_on_min_since_low` | minutes from the overnight extreme to 09:30 |
| `f_on_high_vs_prev_high_r`, `f_on_low_vs_prev_low_r` | overnight extreme vs previous RTH extreme (cont) / R20 |
| `f_on_drawup_r`, `f_on_drawdown_r` | (p0929 − overnight low) / R20, (overnight high − p0929) / R20 |
| `f_on_run5` | signed length of the terminal run of same-sign 5-min changes |
| `f_on_max5m_r` | largest absolute 5-min move overnight / R20 |
| `f_shock_0830_r` | (last print ≤ 08:35 − last print ≤ 08:30) / R20 (the 08:30 data reaction) |
| `f_shock_retrace` | (p0835 − p0929) / (p0835 − p0830), clipped to ±3 (1 = shock fully retraced) |
| `f_gap_close_r`, `f_gap_settle_r`, `f_gap_pct` | p0929 vs previous close / previous settlement proxy (VWAP of the last 30 s), cont |
| `f_on_rng_vs_prev_rng` | overnight range / previous RTH range |
| `f_on_x_prev_sign` | sign(overnight return) × sign(previous RTH return) |
| `f_on_coverage` | share of the 930 overnight minutes with ≥ 1 print |
| `f_on_share_above_prev_close`, `f_on_share_above_start` | share of overnight 1-min closes above the previous close / the session start |
| `f_eu_x_asia_sign`, `f_last30_x_on_sign` | sign agreements between windows |
| `f_on_vol_last_hour_share` | volume 08:30–09:30 / overnight volume |
| `f_on_mean_size_ratio` | mean trade size overnight / 20-session median |
| `f_on_rng_med20_r` | 20-session median overnight range / R20 |
| `f_R20_pct` | R20 / p0929 |

## D. Previous RTH session (25)

`f_prev_rth_ret_pct`, `f_prev_rth_ret_r`, `f_prev_clv` (close location in range), `f_prev_rng_r`, `f_prev_am_ret_r`
(09:30→12:00), `f_prev_pm_ret_r` (12:00→close), `f_prev_last_hour_ret_r`, `f_prev_trend_day` (|close − open| / range),
`f_prev_gap_r` (previous open vs the close before it), `f_prev_rth_vol_ratio`, `f_prev_last_hour_imb`,
`f_prev_settle_minus_close_r`, `f_prev_up_minute_share`, `f_prev_dd_from_high_r`, `f_prev_new20_high`,
`f_prev_new20_low` (previous session's extreme beyond the 20 sessions before it), `f_prev_half_day`,
`f_prev_am_x_pm_sign`, and the previous session's nine labels `f_prev_T1 … f_prev_T7`.

## E. Multi-day context and calendar (26)

`f_ret_2d_s`, `f_ret_5d_s`, `f_ret_10d_s`, `f_ret_20d_s` (close-to-close momentum ending at the previous close, in σ20
units), `f_pos_20d`, `f_pos_60d` (p0929 within the 20/60-session high–low range), `f_rv20` (σ20), `f_rv20_chg`
(σ20 / σ20 five sessions earlier), `f_rv5_over_rv20`, `f_mean_clv_5`, `f_n_up_5`, `f_n_up_10`, `f_streak` (signed run of
RTH signs ending at the previous session), `f_gap_fill_share_10` (share of the last 10 sessions whose gap was filled
inside 09:30–12:00), `f_am_drift_20` (mean 09:30–12:00 return of the last 20 sessions), `f_am_upshare_20`,
`f_am_autocorr_20` (lag-1 autocorrelation of 09:30–12:00 returns over 20 sessions), `f_dow`, `f_month`,
`f_first_td_month`, `f_last_td_month`, `f_third_friday`, `f_days_to_expiry` (trading days to the front contract's third
Friday), `f_roll_day`, `f_prev_holiday_session`, `f_after_holiday_gap` (calendar gap longer than a normal weekday/weekend).

## F. Sequence input (not in the matrix)
`runs/phase5/E0/seq1m_development.npy`: 929 one-minute log returns per day from 18:00 ET to 09:30 ET (0 where no print),
used only by the sequence models (E6). The design's "690" was an arithmetic slip; 18:00 → 09:30 is 930 minutes.

## Fold-internal transforms (E3+, never on the full sample)
rolling 250-session z-scores and ranks (window ending at D−1), pairwise products of the top-20 screened features,
interactions with the volatility-regime tercile.
