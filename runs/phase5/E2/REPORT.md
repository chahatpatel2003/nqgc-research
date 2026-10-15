# E2 — feature bank v1 (development), leakage audits

Feature matrix: `runs/phase5/E2/features_development.parquet` sha256[:16] = `9af2928605831f00`; rows 752 (RTH sessions), eligible 728; features 136.

Leakage test suite (`tests/test_bias_leakage.py`): **ALL PASSED**

```
.........                                                                [100%]
```

## Label-correlation audit (|corr| with same-day T1/T3/T5 on eligible development days; flag threshold 0.30)

Flagged features: 0

Largest 15 |corr| (audit view only; NOT a selection step — the walk-forward screen is E3):

| feature | corr T1 | corr T3 | corr T5 | missing |
|---|---|---|---|---|
| f_eu_rng_r | -0.099 | -0.068 | -0.007 | 0.0% |
| f_prev_T4a | -0.004 | -0.096 | +0.032 | 0.1% |
| f_eu_big_imb | +0.094 | +0.064 | +0.077 | 0.0% |
| f_third_friday | -0.063 | -0.089 | -0.035 | 0.0% |
| f_gap_pct | +0.070 | +0.007 | +0.082 | 0.0% |
| f_on_share_above_prev_close | +0.051 | +0.032 | +0.081 | 0.0% |
| f_last30_vwap_dist_r | +0.074 | +0.038 | +0.081 | 0.0% |
| f_on_rng_r | -0.080 | -0.057 | -0.019 | 0.0% |
| f_prev_half_day | +0.071 | +0.079 | +0.018 | 0.0% |
| f_asia_ret_r | +0.050 | +0.048 | +0.078 | 0.0% |
| f_eu_nrev | -0.032 | -0.078 | +0.025 | 0.0% |
| f_on_drawdown_r | -0.076 | -0.029 | -0.044 | 0.0% |
| f_prev_up_minute_share | -0.002 | -0.075 | -0.001 | 0.0% |
| f_on_share_above_start | +0.049 | +0.044 | +0.075 | 0.0% |
| f_prev_gap_r | +0.028 | +0.074 | +0.048 | 0.0% |

Features with > 20% missing on eligible days: none
