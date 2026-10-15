# PHASE 4 — master table (BASE cost unless stated; expectancy = net $/trade on 1 contract; dev/val1/val2)

| # | strategy | source | instr | rule recoverable | trades | dev exp $ | val1 exp $ | val2 exp $ | PF | max DD $ | Sharpe | outlier dependence | cost robustness | pooled-OOS mean [95% CI] | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | D NQ ORB-retrace VP T15_poc | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 439/144/203 | 113.8 | 13.4 | 314.7 | 1.23/1.03/1.47 | 18,799/13,321/20,254 | 1.29/0.17/2.42 | OOS excl top1/3/5: 58,974/46,249/36,283 of 65,799; top1/5/10%: 37/126/205% | OOS net gross/base/stress/2x: 68,755/65,799/63,219/59,349 | [9, 385] | **MARGINAL** |
| 2 | D NQ ORB-retrace VP T15_val | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 435/144/199 | 130.3 | 80.7 | 267.4 | 1.27/1.17/1.42 | 15,163/12,166/24,415 | 1.49/0.98/2.13 | OOS excl top1/3/5: 58,133/46,243/36,168 of 64,819; top1/5/10%: 36/124/203% | OOS net gross/base/stress/2x: 67,705/64,819/62,339/58,619 | [8, 374] | **PASS** |
| 3 | D NQ ORB-retrace VP T10_poc | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 472/160/219 | 67.4 | -31.1 | 340.0 | 1.13/0.94/1.52 | 26,112/17,590/21,673 | 0.76/-0.40/2.61 | OOS excl top1/3/5: 62,676/49,950/39,985 of 69,501; top1/5/10%: 35/127/213% | OOS net gross/base/stress/2x: 72,730/69,501/66,681/62,451 | [9, 357] | **MARGINAL** |
| 4 | D NQ ORB-retrace VP T10_val | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 470/161/215 | 87.7 | 43.5 | 273.2 | 1.17/1.09/1.43 | 18,470/11,915/24,900 | 1.00/0.52/2.17 | OOS excl top1/3/5: 59,065/46,845/36,494 of 65,750; top1/5/10%: 37/131/220% | OOS net gross/base/stress/2x: 68,920/65,750/63,020/58,925 | [-0, 353] | **MARGINAL** |
| 5 | D NQ ORB-retrace VP T15_vah | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 436/146/205 | 55.9 | 116.5 | 203.1 | 1.11/1.26/1.30 | 28,835/8,629/21,767 | 0.66/1.44/1.67 | OOS excl top1/3/5: 52,600/43,345/34,384 of 58,630; top1/5/10%: 34/122/210% | OOS net gross/base/stress/2x: 61,600/58,630/56,060/52,205 | [-11, 345] | **MARGINAL** |
| 6 | D NQ ORB-retrace VP T25_val | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 376/128/178 | 125.7 | 4.4 | 274.8 | 1.28/1.01/1.45 | 12,988/17,630/24,805 | 1.50/0.06/2.26 | OOS excl top1/3/5: 42,786/32,436/22,960 of 49,471; top1/5/10%: 45/137/227% | OOS net gross/base/stress/2x: 52,060/49,471/47,231/43,871 | [-23, 353] | **MARGINAL** |
| 7 | D NQ ORB-retrace VP T25_poc | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 382/127/175 | 89.3 | -51.0 | 306.6 | 1.18/0.90/1.47 | 14,125/14,042/22,994 | 1.06/-0.69/2.41 | OOS excl top1/3/5: 40,355/28,655/18,999 of 47,180; top1/5/10%: 50/149/244% | OOS net gross/base/stress/2x: 49,755/47,180/44,930/41,555 | [-34, 354] | **MARGINAL** |
| 8 | D NQ ORB-retrace VP T30_poc | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 348/119/162 | 64.8 | -98.7 | 309.8 | 1.14/0.81/1.48 | 15,333/19,202/21,998 | 0.81/-1.35/2.44 | OOS excl top1/3/5: 31,611/19,911/10,255 of 38,436; top1/5/10%: 48/172/278% | OOS net gross/base/stress/2x: 40,845/38,436/36,316/33,136 | [-57, 342] | **MARGINAL** |
| 9 | D NQ ORB-retrace VP T25_vah | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 380/127/178 | 40.8 | 25.2 | 212.8 | 1.08/1.05/1.32 | 18,497/7,813/22,557 | 0.49/0.33/1.78 | OOS excl top1/3/5: 35,051/25,940/17,430 of 41,081; top1/5/10%: 48/149/251% | OOS net gross/base/stress/2x: 43,675/41,081/38,821/35,431 | [-45, 318] | **MARGINAL** |
| 10 | D NQ ORB-retrace VP T20_val | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 403/138/195 | 119.1 | -30.5 | 251.5 | 1.25/0.94/1.39 | 16,252/17,024/26,570 | 1.39/-0.38/2.02 | OOS excl top1/3/5: 38,136/26,246/16,171 of 44,822; top1/5/10%: 53/167/280% | OOS net gross/base/stress/2x: 47,650/44,822/42,362/38,672 | [-45, 320] | **MARGINAL** |
| 11 | D NQ ORB-retrace VP T30_val | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 348/121/167 | 116.3 | -58.4 | 272.4 | 1.27/0.89/1.45 | 11,939/21,070/26,662 | 1.46/-0.73/2.26 | OOS excl top1/3/5: 31,742/21,392/11,917 of 38,428; top1/5/10%: 44/165/271% | OOS net gross/base/stress/2x: 40,880/38,428/36,288/33,078 | [-54, 333] | **MARGINAL** |
| 12 | D NQ ORB-retrace VP T10_vah | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 467/160/217 | 20.1 | 51.1 | 189.1 | 1.04/1.11/1.27 | 31,552/8,629/22,046 | 0.23/0.64/1.54 | OOS excl top1/3/5: 43,170/33,915/24,954 of 49,200; top1/5/10%: 40/154/267% | OOS net gross/base/stress/2x: 52,390/49,200/46,440/42,300 | [-37, 295] | **MARGINAL** |
| 13 | D NQ ORB-retrace VP T30_vah | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 344/118/164 | -12.1 | -25.6 | 236.4 | 0.98/0.95/1.36 | 22,000/12,591/18,163 | -0.15/-0.35/1.98 | OOS excl top1/3/5: 29,721/20,761/12,755 of 35,751; top1/5/10%: 42/158/267% | OOS net gross/base/stress/2x: 38,155/35,751/33,651/30,501 | [-57, 318] | **FAIL** |
| 14 | D NQ ORB-retrace VP T20_poc | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 406/138/193 | 104.0 | -63.5 | 262.5 | 1.21/0.88/1.38 | 17,095/18,311/20,913 | 1.19/-0.84/2.03 | OOS excl top1/3/5: 35,071/22,346/12,380 of 41,896; top1/5/10%: 59/184/305% | OOS net gross/base/stress/2x: 44,735/41,896/39,396/35,646 | [-59, 314] | **MARGINAL** |
| 15 | A NQ Noise-Area long | Zarattini/Aziz/Barbon 2024 | NQ | yes | 336/91/146 | 256.2 | 102.1 | 134.4 | 1.64/1.20/1.19 | 10,433/16,847/29,589 | 3.44/1.24/0.85 | OOS excl top1/3/5: -7,338/-21,888/-31,569 of 28,907; top1/5/10%: 176/291/393% | OOS net gross/base/stress/2x: 32,415/28,907/24,167/17,057 | [-210, 551] | **MARGINAL** |
| 16 | D NQ ORB-retrace VP T20_vah | dws-data/nas-orb-backtester | NQ | mechanics yes; config/filter no | 408/140/193 | 73.8 | 30.2 | 149.1 | 1.15/1.06/1.21 | 18,285/8,572/21,542 | 0.86/0.38/1.23 | OOS excl top1/3/5: 26,966/17,711/8,751 of 32,997; top1/5/10%: 60/203/347% | OOS net gross/base/stress/2x: 35,845/32,997/30,497/26,747 | [-79, 276] | **MARGINAL** |
| 17 | G GC Crabel Stretch ORB | Crabel 1990 (oxfordstrat replication) | GC | yes | 1923/236/locked | -1.7 | 17.6 | n/a | 0.99/1.04 | 26,134/18,178 | -0.03/0.22 | val excl top1/3/5: -1,898/-10,168/-17,197 of 4,157; top1/5/10%: 345/953/1520% | val net gross/base/stress/2x: 10,060/4,157/-5,393/-19,433 | [-137, 174] | **FAIL** |
| 18 | F GC 5th-half-hour -> last-half-hour | Wen et al. 2020 / Gao et al. 2018 | GC | yes (ETF->futures mapping caveat) | 1910/240/locked | -26.2 | 1.1 | n/a | 0.63/1.01 | 50,616/2,142 | -2.32/0.07 | val excl top1/3/5: -1,388/-3,488/-5,078 of 266; top1/5/10%: 1409/3490/5059% | val net gross/base/stress/2x: 6,300/266/-9,334/-23,734 | [-30, 35] | **FAIL** |
| 19 | B Early-Bird intraday trend | Turc/Gava/McNeal 2021 | NQ | SPEC_NOT_RECOVERABLE |  | n/a | n/a | n/a |  |  |  |  |  |  | **NOT TESTED** |
| 20 | C S/R first-touch rejection | unidentified repository | NQ | SPEC_NOT_RECOVERABLE |  | n/a | n/a | n/a |  |  |  |  |  |  | **NOT TESTED** |
| 21 | E opening-gap reversal | Fung/Mok/Lam 2000; Grant/Wolf/Yu 2005 | NQ | SPEC_NOT_RECOVERABLE |  | n/a | n/a | n/a |  |  |  |  |  |  | **NOT TESTED** |
| 22 | H GC mean reversion | no exact public spec | GC | SPEC_NOT_RECOVERABLE |  | n/a | n/a | n/a |  |  |  |  |  |  | **NOT TESTED** |

## D — repository-faithful (touch fills, zero cost) vs corrected (through fills, base cost), expR / n
| cell | dev faithful | dev corrected | val1 faithful | val1 corrected | val2 faithful | val2 corrected |
|---|---|---|---|---|---|---|
| T10_vah | 0.059 / 468 | 0.047 / 467 | 0.093 / 160 | 0.064 / 160 | 0.224 / 218 | 0.189 / 217 |
| T10_poc | 0.112 / 472 | 0.106 / 472 | 0.024 / 160 | 0.009 / 160 | 0.286 / 221 | 0.260 / 219 |
| T10_val | 0.165 / 471 | 0.141 / 470 | -0.014 / 161 | -0.053 / 161 | 0.186 / 216 | 0.163 / 215 |
| T15_vah | 0.089 / 436 | 0.080 / 436 | 0.191 / 146 | 0.166 / 146 | 0.337 / 206 | 0.303 / 205 |
| T15_poc | 0.149 / 439 | 0.144 / 439 | 0.086 / 144 | 0.072 / 144 | 0.317 / 205 | 0.290 / 203 |
| T15_val | 0.217 / 436 | 0.192 / 435 | 0.051 / 144 | 0.010 / 144 | 0.216 / 200 | 0.193 / 199 |
| T20_vah | 0.116 / 408 | 0.109 / 408 | 0.084 / 140 | 0.060 / 140 | 0.286 / 194 | 0.249 / 193 |
| T20_poc | 0.131 / 406 | 0.126 / 406 | 0.004 / 138 | -0.010 / 138 | 0.286 / 194 | 0.268 / 193 |
| T20_val | 0.208 / 403 | 0.187 / 403 | -0.045 / 138 | -0.086 / 138 | 0.224 / 196 | 0.201 / 195 |
| T25_vah | 0.091 / 381 | 0.083 / 380 | 0.140 / 127 | 0.118 / 127 | 0.335 / 179 | 0.296 / 178 |
| T25_poc | 0.124 / 382 | 0.103 / 382 | 0.008 / 127 | -0.006 / 127 | 0.325 / 175 | 0.315 / 175 |
| T25_val | 0.141 / 376 | 0.126 / 376 | -0.004 / 128 | -0.046 / 128 | 0.255 / 179 | 0.231 / 178 |
| T30_vah | -0.026 / 345 | -0.033 / 344 | 0.083 / 118 | 0.060 / 118 | 0.319 / 165 | 0.280 / 164 |
| T30_poc | 0.042 / 348 | 0.038 / 348 | -0.016 / 119 | -0.030 / 119 | 0.340 / 162 | 0.329 / 162 |
| T30_val | 0.098 / 348 | 0.083 / 348 | -0.035 / 121 | -0.079 / 121 | 0.275 / 168 | 0.250 / 167 |

## Equal-risk bucket (strategies profitable after BASE cost; D enters as the equal-weight average of its 15 cells — no cell selected)

Members: ['A_noise_long', 'D_orb_retrace_family_avg']. Out-of-sample (2024 + 2025-2026H1) daily corr = [[1.0, -0.04], [-0.04, 1.0]], monthly corr = [[1.0, -0.18], [-0.18, 1.0]], pairwise both-lose share = {'A_noise_long|D_orb_retrace_family_avg': 0.05573770491803279}, all-lose share = 0.056, equal-risk weights = {'A_noise_long': 0.39623298656893974, 'D_orb_retrace_family_avg': 0.6037670134310603}, portfolio (weights sum to 1) max DD $11,404, Sharpe 1.25, total $41,391 over 610 days.
Full sample (dev+OOS): daily corr = [[1.0, 0.01], [0.01, 1.0]], monthly corr = [[1.0, -0.21], [-0.21, 1.0]], portfolio Sharpe 1.47, max DD $11,519.

D cells vs A, OOS daily P&L correlation: T10_vah -0.02, T10_poc -0.03, T10_val -0.01, T15_vah -0.02, T15_poc -0.03, T15_val -0.01, T20_vah -0.04, T20_poc -0.06, T20_val -0.01, T25_vah -0.04, T25_poc -0.08, T25_val -0.03, T30_vah -0.04, T30_poc -0.08, T30_val -0.03