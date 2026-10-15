# E1 — naive baselines (development 2021–2023, eligible days, no fitting)

Every rule predicts on 100% of days (sign = 0 → NO BIAS on that day). Accuracy is judged against always-BUY on the same predicted days.

## Accuracy by rule × target (correct/decisive, lift vs always-BUY on the same days)

| Rule | T1 | T2a | T2b | T3 | T4a | T4b | T5 | T6 | T7 |
|---|---|---|---|---|---|---|---|---|---|
| always_BUY | 381/727 52.41% (+0.0) | 341/639 53.36% (+0.0) | 282/525 53.71% (+0.0) | 334/692 48.27% (+0.0) | 381/722 52.77% (+0.0) | 302/600 50.33% (+0.0) | 325/598 54.35% (+0.0) | 336/660 50.91% (+0.0) | 236/458 51.53% (+0.0) |
| always_SELL | 346/727 47.59% (-4.8) | 298/639 46.64% (-6.7) | 243/525 46.29% (-7.4) | 358/692 51.73% (+3.5) | 341/722 47.23% (-5.5) | 298/600 49.67% (-0.7) | 273/598 45.65% (-8.7) | 324/660 49.09% (-1.8) | 222/458 48.47% (-3.1) |
| prev_RTH_sign | 365/727 50.21% (-2.2) | 323/639 50.55% (-2.8) | 262/525 49.90% (-3.8) | 328/692 47.40% (-0.9) | 350/722 48.48% (-4.3) | 287/600 47.83% (-2.5) | 301/598 50.33% (-4.0) | 321/660 48.64% (-2.3) | 221/458 48.25% (-3.3) |
| anti_prev_RTH_sign | 362/727 49.79% (-2.6) | 316/639 49.45% (-3.9) | 263/525 50.10% (-3.6) | 364/692 52.60% (+4.3) | 372/722 51.52% (-1.2) | 313/600 52.17% (+1.8) | 297/598 49.67% (-4.7) | 339/660 51.36% (+0.5) | 237/458 51.75% (+0.2) |
| prev_AM_sign | 360/726 49.59% (-2.8) | 313/638 49.06% (-4.2) | 256/524 48.85% (-4.8) | 325/691 47.03% (-1.2) | 349/721 48.40% (-4.3) | 285/599 47.58% (-2.7) | 298/597 49.92% (-4.4) | 314/659 47.65% (-3.2) | 220/457 48.14% (-3.3) |
| anti_prev_AM_sign | 366/726 50.41% (-1.9) | 325/638 50.94% (-2.4) | 268/524 51.15% (-2.5) | 366/691 52.97% (+4.8) | 372/721 51.60% (-1.1) | 314/599 52.42% (+2.2) | 299/597 50.08% (-4.2) | 345/659 52.35% (+1.5) | 237/457 51.86% (+0.4) |
| overnight_sign | 377/727 51.86% (-0.6) | 322/639 50.39% (-3.0) | 262/525 49.90% (-3.8) | 340/692 49.13% (+0.9) | 354/722 49.03% (-3.7) | 293/600 48.83% (-1.5) | 318/598 53.18% (-1.2) | 331/660 50.15% (-0.8) | 237/458 51.75% (+0.2) |
| anti_overnight_sign | 350/727 48.14% (-4.3) | 317/639 49.61% (-3.8) | 263/525 50.10% (-3.6) | 352/692 50.87% (+2.6) | 368/722 50.97% (-1.8) | 307/600 51.17% (+0.8) | 280/598 46.82% (-7.5) | 329/660 49.85% (-1.1) | 221/458 48.25% (-3.3) |
| last30_sign | 376/724 51.93% (-0.4) | 328/637 51.49% (-1.9) | 271/523 51.82% (-1.9) | 349/689 50.65% (+2.5) | 339/719 47.15% (-5.7) | 297/597 49.75% (-0.5) | 317/596 53.19% (-1.0) | 337/657 51.29% (+0.5) | 241/456 52.85% (+1.5) |
| anti_last30_sign | 348/724 48.07% (-4.3) | 309/637 48.51% (-4.9) | 252/523 48.18% (-5.5) | 340/689 49.35% (+1.2) | 380/719 52.85% (+0.0) | 300/597 50.25% (+0.0) | 279/596 46.81% (-7.4) | 320/657 48.71% (-2.1) | 215/456 47.15% (-4.2) |
| gap_sign | 378/726 52.07% (-0.4) | 327/638 51.25% (-2.2) | 263/525 50.10% (-3.6) | 337/691 48.77% (+0.4) | 352/721 48.82% (-4.0) | 289/599 48.25% (-2.2) | 319/597 53.43% (-1.0) | 332/659 50.38% (-0.6) | 235/457 51.42% (-0.2) |
| anti_gap_sign(gap_fade) | 348/726 47.93% (-4.5) | 311/638 48.75% (-4.7) | 262/525 49.90% (-3.8) | 354/691 51.23% (+2.9) | 369/721 51.18% (-1.7) | 310/599 51.75% (+1.3) | 278/597 46.57% (-7.9) | 327/659 49.62% (-1.4) | 222/457 48.58% (-3.1) |
| shock0830_sign | 345/721 47.85% (-4.3) | 297/633 46.92% (-6.2) | 245/522 46.93% (-6.5) | 335/686 48.83% (+0.9) | 348/716 48.60% (-3.9) | 290/594 48.82% (-1.2) | 277/594 46.63% (-7.6) | 319/655 48.70% (-1.8) | 214/456 46.93% (-4.4) |
| anti_shock0830_sign | 376/721 52.15% (+0.0) | 336/633 53.08% (+0.0) | 277/522 53.07% (-0.4) | 351/686 51.17% (+3.2) | 368/716 51.40% (-1.1) | 304/594 51.18% (+1.2) | 317/594 53.37% (-0.8) | 336/655 51.30% (+0.8) | 242/456 53.07% (+1.8) |
| am_drift20_sign | 375/727 51.58% (-0.8) | 332/639 51.96% (-1.4) | 271/525 51.62% (-2.1) | 348/692 50.29% (+2.0) | 370/722 51.25% (-1.5) | 293/600 48.83% (-1.5) | 303/598 50.67% (-3.7) | 331/660 50.15% (-0.8) | 236/458 51.53% (+0.0) |
| ret5d_sign | 381/727 52.41% (+0.0) | 339/639 53.05% (-0.3) | 276/525 52.57% (-1.1) | 346/692 50.00% (+1.7) | 382/722 52.91% (+0.1) | 303/600 50.50% (+0.2) | 310/598 51.84% (-2.5) | 339/660 51.36% (+0.5) | 237/458 51.75% (+0.2) |
| anti_ret5d_sign | 346/727 47.59% (-4.8) | 300/639 46.95% (-6.4) | 249/525 47.43% (-6.3) | 346/692 50.00% (+1.7) | 340/722 47.09% (-5.7) | 297/600 49.50% (-0.8) | 288/598 48.16% (-6.2) | 321/660 48.64% (-2.3) | 221/458 48.25% (-3.3) |

## Full blocks on T1 (net sign), per year and per side

```
[E1 always_BUY — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     728   (BUY 728, SELL 0)
NO BIAS days:             0
Correct days:             381
Wrong days:               346   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 381/727 = 52.41%   [Wilson 95% 48.77% – 56.02%]
Coverage:                 728/728 = 100.00%
BUY accuracy:             381/727 = 52.41%
SELL accuracy:            0/0 = n/a   (SELL base rate on same days 47.59%)
Always-BUY on same days:  52.41%   lift = 0.00%   best constant 52.41%   balanced acc 50.00%
Net-sign (T1) accuracy on the same predictions: 381/727 = 52.41%   (always-BUY 52.41%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 117 | 112 | 0 | 51.09% | 100.00% | 229 | 51.09% | 0 | n/a | 51.09% | 0.00% | 51.09% |
| 2022 | 250 | 250 | 127 | 123 | 0 | 50.80% | 100.00% | 250 | 50.80% | 0 | n/a | 50.80% | 0.00% | 50.80% |
| 2023 | 248 | 248 | 137 | 111 | 0 | 55.24% | 100.00% | 248 | 55.24% | 0 | n/a | 55.24% | 0.00% | 55.24% |
```

```
[E1 always_SELL — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     728   (BUY 0, SELL 728)
NO BIAS days:             0
Correct days:             346
Wrong days:               381   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 346/727 = 47.59%   [Wilson 95% 43.98% – 51.23%]
Coverage:                 728/728 = 100.00%
BUY accuracy:             0/0 = n/a
SELL accuracy:            346/727 = 47.59%   (SELL base rate on same days 47.59%)
Always-BUY on same days:  52.41%   lift = -4.81%   best constant 52.41%   balanced acc 50.00%
Net-sign (T1) accuracy on the same predictions: 346/727 = 47.59%   (always-BUY 52.41%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 112 | 117 | 0 | 48.91% | 100.00% | 0 | n/a | 229 | 48.91% | 51.09% | -2.18% | 48.91% |
| 2022 | 250 | 250 | 123 | 127 | 0 | 49.20% | 100.00% | 0 | n/a | 250 | 49.20% | 50.80% | -1.60% | 49.20% |
| 2023 | 248 | 248 | 111 | 137 | 0 | 44.76% | 100.00% | 0 | n/a | 248 | 44.76% | 55.24% | -10.48% | 44.76% |
```

```
[E1 prev_RTH_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     728   (BUY 398, SELL 330)
NO BIAS days:             0
Correct days:             365
Wrong days:               362   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 365/727 = 50.21%   [Wilson 95% 46.58% – 53.83%]
Coverage:                 728/728 = 100.00%
BUY accuracy:             208/397 = 52.39%
SELL accuracy:            157/330 = 47.58%   (SELL base rate on same days 47.59%)
Always-BUY on same days:  52.41%   lift = -2.20%   best constant 52.41%   balanced acc 49.98%
Net-sign (T1) accuracy on the same predictions: 365/727 = 50.21%   (always-BUY 52.41%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 111 | 118 | 0 | 48.47% | 100.00% | 129 | 49.61% | 100 | 47.00% | 51.09% | -2.62% | 48.47% |
| 2022 | 250 | 250 | 134 | 116 | 0 | 53.60% | 100.00% | 119 | 54.62% | 131 | 52.67% | 50.80% | 2.80% | 53.60% |
| 2023 | 248 | 248 | 120 | 128 | 0 | 48.39% | 100.00% | 149 | 53.02% | 99 | 41.41% | 55.24% | -6.85% | 48.39% |
```

```
[E1 anti_prev_RTH_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     728   (BUY 330, SELL 398)
NO BIAS days:             0
Correct days:             362
Wrong days:               365   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 362/727 = 49.79%   [Wilson 95% 46.17% – 53.42%]
Coverage:                 728/728 = 100.00%
BUY accuracy:             173/330 = 52.42%
SELL accuracy:            189/397 = 47.61%   (SELL base rate on same days 47.59%)
Always-BUY on same days:  52.41%   lift = -2.61%   best constant 52.41%   balanced acc 50.02%
Net-sign (T1) accuracy on the same predictions: 362/727 = 49.79%   (always-BUY 52.41%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 118 | 111 | 0 | 51.53% | 100.00% | 100 | 53.00% | 129 | 50.39% | 51.09% | 0.44% | 51.53% |
| 2022 | 250 | 250 | 116 | 134 | 0 | 46.40% | 100.00% | 131 | 47.33% | 119 | 45.38% | 50.80% | -4.40% | 46.40% |
| 2023 | 248 | 248 | 128 | 120 | 0 | 51.61% | 100.00% | 99 | 58.59% | 149 | 46.98% | 55.24% | -3.63% | 51.61% |
```

```
[E1 prev_AM_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     727   (BUY 379, SELL 348)
NO BIAS days:             1
Correct days:             360
Wrong days:               366   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 360/726 = 49.59%   [Wilson 95% 45.96% – 53.22%]
Coverage:                 727/728 = 99.86%
BUY accuracy:             196/378 = 51.85%
SELL accuracy:            164/348 = 47.13%   (SELL base rate on same days 47.66%)
Always-BUY on same days:  52.34%   lift = -2.75%   best constant 52.34%   balanced acc 49.49%
Net-sign (T1) accuracy on the same predictions: 360/726 = 49.59%   (always-BUY 52.34%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 229 | 112 | 116 | 1 | 49.12% | 99.57% | 116 | 50.00% | 112 | 48.21% | 50.88% | -1.75% | 49.12% |
| 2022 | 250 | 250 | 131 | 119 | 0 | 52.40% | 100.00% | 126 | 53.17% | 124 | 51.61% | 50.80% | 1.60% | 52.40% |
| 2023 | 248 | 248 | 117 | 131 | 0 | 47.18% | 100.00% | 136 | 52.21% | 112 | 41.07% | 55.24% | -8.06% | 47.18% |
```

```
[E1 anti_prev_AM_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     727   (BUY 348, SELL 379)
NO BIAS days:             1
Correct days:             366
Wrong days:               360   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 366/726 = 50.41%   [Wilson 95% 46.78% – 54.04%]
Coverage:                 727/728 = 99.86%
BUY accuracy:             184/348 = 52.87%
SELL accuracy:            182/378 = 48.15%   (SELL base rate on same days 47.66%)
Always-BUY on same days:  52.34%   lift = -1.93%   best constant 52.34%   balanced acc 50.51%
Net-sign (T1) accuracy on the same predictions: 366/726 = 50.41%   (always-BUY 52.34%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 229 | 116 | 112 | 1 | 50.88% | 99.57% | 112 | 51.79% | 116 | 50.00% | 50.88% | 0.00% | 50.88% |
| 2022 | 250 | 250 | 119 | 131 | 0 | 47.60% | 100.00% | 124 | 48.39% | 126 | 46.83% | 50.80% | -3.20% | 47.60% |
| 2023 | 248 | 248 | 131 | 117 | 0 | 52.82% | 100.00% | 112 | 58.93% | 136 | 47.79% | 55.24% | -2.42% | 52.82% |
```

```
[E1 overnight_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     728   (BUY 376, SELL 352)
NO BIAS days:             0
Correct days:             377
Wrong days:               350   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 377/727 = 51.86%   [Wilson 95% 48.22% – 55.47%]
Coverage:                 728/728 = 100.00%
BUY accuracy:             203/375 = 54.13%
SELL accuracy:            174/352 = 49.43%   (SELL base rate on same days 47.59%)
Always-BUY on same days:  52.41%   lift = -0.55%   best constant 52.41%   balanced acc 51.78%
Net-sign (T1) accuracy on the same predictions: 377/727 = 51.86%   (always-BUY 52.41%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 124 | 105 | 0 | 54.15% | 100.00% | 132 | 54.55% | 97 | 53.61% | 51.09% | 3.06% | 54.15% |
| 2022 | 250 | 250 | 131 | 119 | 0 | 52.40% | 100.00% | 110 | 53.64% | 140 | 51.43% | 50.80% | 1.60% | 52.40% |
| 2023 | 248 | 248 | 122 | 126 | 0 | 49.19% | 100.00% | 133 | 54.14% | 115 | 43.48% | 55.24% | -6.05% | 49.19% |
```

```
[E1 anti_overnight_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     728   (BUY 352, SELL 376)
NO BIAS days:             0
Correct days:             350
Wrong days:               377   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 350/727 = 48.14%   [Wilson 95% 44.53% – 51.78%]
Coverage:                 728/728 = 100.00%
BUY accuracy:             178/352 = 50.57%
SELL accuracy:            172/375 = 45.87%   (SELL base rate on same days 47.59%)
Always-BUY on same days:  52.41%   lift = -4.26%   best constant 52.41%   balanced acc 48.22%
Net-sign (T1) accuracy on the same predictions: 350/727 = 48.14%   (always-BUY 52.41%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 105 | 124 | 0 | 45.85% | 100.00% | 97 | 46.39% | 132 | 45.45% | 51.09% | -5.24% | 45.85% |
| 2022 | 250 | 250 | 119 | 131 | 0 | 47.60% | 100.00% | 140 | 48.57% | 110 | 46.36% | 50.80% | -3.20% | 47.60% |
| 2023 | 248 | 248 | 126 | 122 | 0 | 50.81% | 100.00% | 115 | 56.52% | 133 | 45.86% | 55.24% | -4.44% | 50.81% |
```

```
[E1 last30_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     725   (BUY 350, SELL 375)
NO BIAS days:             3
Correct days:             376
Wrong days:               348   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 376/724 = 51.93%   [Wilson 95% 48.29% – 55.55%]
Coverage:                 725/728 = 99.59%
BUY accuracy:             190/349 = 54.44%
SELL accuracy:            186/375 = 49.60%   (SELL base rate on same days 47.65%)
Always-BUY on same days:  52.35%   lift = -0.41%   best constant 52.35%   balanced acc 52.02%
Net-sign (T1) accuracy on the same predictions: 376/724 = 51.93%   (always-BUY 52.35%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 118 | 111 | 0 | 51.53% | 100.00% | 118 | 52.54% | 111 | 50.45% | 51.09% | 0.44% | 51.53% |
| 2022 | 250 | 248 | 127 | 121 | 2 | 51.21% | 99.20% | 107 | 52.34% | 141 | 50.35% | 50.81% | 0.40% | 51.21% |
| 2023 | 248 | 247 | 131 | 116 | 1 | 53.04% | 99.60% | 124 | 58.06% | 123 | 47.97% | 55.06% | -2.02% | 53.04% |
```

```
[E1 anti_last30_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     725   (BUY 375, SELL 350)
NO BIAS days:             3
Correct days:             348
Wrong days:               376   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 348/724 = 48.07%   [Wilson 95% 44.45% – 51.71%]
Coverage:                 725/728 = 99.59%
BUY accuracy:             189/375 = 50.40%
SELL accuracy:            159/349 = 45.56%   (SELL base rate on same days 47.65%)
Always-BUY on same days:  52.35%   lift = -4.28%   best constant 52.35%   balanced acc 47.98%
Net-sign (T1) accuracy on the same predictions: 348/724 = 48.07%   (always-BUY 52.35%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 111 | 118 | 0 | 48.47% | 100.00% | 111 | 49.55% | 118 | 47.46% | 51.09% | -2.62% | 48.47% |
| 2022 | 250 | 248 | 121 | 127 | 2 | 48.79% | 99.20% | 141 | 49.65% | 107 | 47.66% | 50.81% | -2.02% | 48.79% |
| 2023 | 248 | 247 | 116 | 131 | 1 | 46.96% | 99.60% | 123 | 52.03% | 124 | 41.94% | 55.06% | -8.10% | 46.96% |
```

```
[E1 gap_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     727   (BUY 370, SELL 357)
NO BIAS days:             1
Correct days:             378
Wrong days:               348   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 378/726 = 52.07%   [Wilson 95% 48.43% – 55.68%]
Coverage:                 727/728 = 99.86%
BUY accuracy:             201/369 = 54.47%
SELL accuracy:            177/357 = 49.58%   (SELL base rate on same days 47.52%)
Always-BUY on same days:  52.48%   lift = -0.41%   best constant 52.48%   balanced acc 52.03%
Net-sign (T1) accuracy on the same predictions: 378/726 = 52.07%   (always-BUY 52.48%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 120 | 109 | 0 | 52.40% | 100.00% | 134 | 52.99% | 95 | 51.58% | 51.09% | 1.31% | 52.40% |
| 2022 | 250 | 249 | 133 | 116 | 1 | 53.41% | 99.60% | 109 | 55.05% | 140 | 52.14% | 51.00% | 2.41% | 53.41% |
| 2023 | 248 | 248 | 125 | 123 | 0 | 50.40% | 100.00% | 126 | 55.56% | 122 | 45.08% | 55.24% | -4.84% | 50.40% |
```

```
[E1 anti_gap_sign(gap_fade) — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     727   (BUY 357, SELL 370)
NO BIAS days:             1
Correct days:             348
Wrong days:               378   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 348/726 = 47.93%   [Wilson 95% 44.32% – 51.57%]
Coverage:                 727/728 = 99.86%
BUY accuracy:             180/357 = 50.42%
SELL accuracy:            168/369 = 45.53%   (SELL base rate on same days 47.52%)
Always-BUY on same days:  52.48%   lift = -4.55%   best constant 52.48%   balanced acc 47.97%
Net-sign (T1) accuracy on the same predictions: 348/726 = 47.93%   (always-BUY 52.48%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 109 | 120 | 0 | 47.60% | 100.00% | 95 | 48.42% | 134 | 47.01% | 51.09% | -3.49% | 47.60% |
| 2022 | 250 | 249 | 116 | 133 | 1 | 46.59% | 99.60% | 140 | 47.86% | 109 | 44.95% | 51.00% | -4.42% | 46.59% |
| 2023 | 248 | 248 | 123 | 125 | 0 | 49.60% | 100.00% | 122 | 54.92% | 126 | 44.44% | 55.24% | -5.65% | 49.60% |
```

```
[E1 shock0830_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     722   (BUY 343, SELL 379)
NO BIAS days:             6
Correct days:             345
Wrong days:               376   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 345/721 = 47.85%   [Wilson 95% 44.22% – 51.50%]
Coverage:                 722/728 = 99.18%
BUY accuracy:             171/342 = 50.00%
SELL accuracy:            174/379 = 45.91%   (SELL base rate on same days 47.85%)
Always-BUY on same days:  52.15%   lift = -4.30%   best constant 52.15%   balanced acc 47.96%
Net-sign (T1) accuracy on the same predictions: 345/721 = 47.85%   (always-BUY 52.15%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 227 | 108 | 118 | 3 | 47.79% | 98.70% | 115 | 48.70% | 111 | 46.85% | 50.88% | -3.10% | 47.79% |
| 2022 | 250 | 249 | 126 | 123 | 1 | 50.60% | 99.60% | 111 | 51.35% | 138 | 50.00% | 50.60% | 0.00% | 50.60% |
| 2023 | 248 | 246 | 111 | 135 | 2 | 45.12% | 99.19% | 116 | 50.00% | 130 | 40.77% | 54.88% | -9.76% | 45.12% |
```

```
[E1 anti_shock0830_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     722   (BUY 379, SELL 343)
NO BIAS days:             6
Correct days:             376
Wrong days:               345   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 376/721 = 52.15%   [Wilson 95% 48.50% – 55.78%]
Coverage:                 722/728 = 99.18%
BUY accuracy:             205/379 = 54.09%
SELL accuracy:            171/342 = 50.00%   (SELL base rate on same days 47.85%)
Always-BUY on same days:  52.15%   lift = 0.00%   best constant 52.15%   balanced acc 52.04%
Net-sign (T1) accuracy on the same predictions: 376/721 = 52.15%   (always-BUY 52.15%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 227 | 118 | 108 | 3 | 52.21% | 98.70% | 111 | 53.15% | 115 | 51.30% | 50.88% | 1.33% | 52.21% |
| 2022 | 250 | 249 | 123 | 126 | 1 | 49.40% | 99.60% | 138 | 50.00% | 111 | 48.65% | 50.60% | -1.20% | 49.40% |
| 2023 | 248 | 246 | 135 | 111 | 2 | 54.88% | 99.19% | 130 | 59.23% | 116 | 50.00% | 54.88% | 0.00% | 54.88% |
```

```
[E1 am_drift20_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     728   (BUY 430, SELL 298)
NO BIAS days:             0
Correct days:             375
Wrong days:               352   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 375/727 = 51.58%   [Wilson 95% 47.95% – 55.20%]
Coverage:                 728/728 = 100.00%
BUY accuracy:             229/429 = 53.38%
SELL accuracy:            146/298 = 48.99%   (SELL base rate on same days 47.59%)
Always-BUY on same days:  52.41%   lift = -0.83%   best constant 52.41%   balanced acc 51.15%
Net-sign (T1) accuracy on the same predictions: 375/727 = 51.58%   (always-BUY 52.41%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 126 | 103 | 0 | 55.02% | 100.00% | 130 | 55.38% | 99 | 54.55% | 51.09% | 3.93% | 55.02% |
| 2022 | 250 | 250 | 121 | 129 | 0 | 48.40% | 100.00% | 130 | 49.23% | 120 | 47.50% | 50.80% | -2.40% | 48.40% |
| 2023 | 248 | 248 | 128 | 120 | 0 | 51.61% | 100.00% | 169 | 55.03% | 79 | 44.30% | 55.24% | -3.63% | 51.61% |
```

```
[E1 ret5d_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     728   (BUY 412, SELL 316)
NO BIAS days:             0
Correct days:             381
Wrong days:               346   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 381/727 = 52.41%   [Wilson 95% 48.77% – 56.02%]
Coverage:                 728/728 = 100.00%
BUY accuracy:             223/411 = 54.26%
SELL accuracy:            158/316 = 50.00%   (SELL base rate on same days 47.59%)
Always-BUY on same days:  52.41%   lift = 0.00%   best constant 52.41%   balanced acc 52.10%
Net-sign (T1) accuracy on the same predictions: 381/727 = 52.41%   (always-BUY 52.41%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 118 | 111 | 0 | 51.53% | 100.00% | 142 | 52.11% | 87 | 50.57% | 51.09% | 0.44% | 51.53% |
| 2022 | 250 | 250 | 127 | 123 | 0 | 50.80% | 100.00% | 110 | 51.82% | 140 | 50.00% | 50.80% | 0.00% | 50.80% |
| 2023 | 248 | 248 | 136 | 112 | 0 | 54.84% | 100.00% | 159 | 57.86% | 89 | 49.44% | 55.24% | -0.40% | 54.84% |
```

```
[E1 anti_ret5d_sign — target T1 — development]
Total eligible days:      728
BUY/SELL predictions:     728   (BUY 316, SELL 412)
NO BIAS days:             0
Correct days:             346
Wrong days:               381   (+1 predictions on FLAT-labelled days, excluded from accuracy)
Accuracy:                 346/727 = 47.59%   [Wilson 95% 43.98% – 51.23%]
Coverage:                 728/728 = 100.00%
BUY accuracy:             158/316 = 50.00%
SELL accuracy:            188/411 = 45.74%   (SELL base rate on same days 47.59%)
Always-BUY on same days:  52.41%   lift = -4.81%   best constant 52.41%   balanced acc 47.90%
Net-sign (T1) accuracy on the same predictions: 346/727 = 47.59%   (always-BUY 52.41%)

Per calendar year:
| Year | Eligible | Predictions | Correct | Wrong | No Bias | Accuracy | Coverage | BUY n | BUY acc | SELL n | SELL acc | Always-BUY same days | Lift | T1 acc same preds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021 | 230 | 230 | 111 | 118 | 0 | 48.47% | 100.00% | 87 | 49.43% | 142 | 47.89% | 51.09% | -2.62% | 48.47% |
| 2022 | 250 | 250 | 123 | 127 | 0 | 49.20% | 100.00% | 140 | 50.00% | 110 | 48.18% | 50.80% | -1.60% | 49.20% |
| 2023 | 248 | 248 | 112 | 136 | 0 | 45.16% | 100.00% | 89 | 50.56% | 159 | 42.14% | 55.24% | -10.08% | 45.16% |
```
