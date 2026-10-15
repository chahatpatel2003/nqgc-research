# STRATEGY A — R4 tap-and-go (frozen nq-levels R4v10) — old vs new engine

```
{
 "name": "R4_tapandgo",
 "version": "1.0-frozen-nqlevels",
 "spec_id": "4d603c68e411",
 "cells": [
  [
   "P14_ck2_S12.5_T30",
   2,
   12.5,
   30.0
  ],
  [
   "H2_ck0_S15.0_T30",
   0,
   15.0,
   30.0
  ],
  [
   "H2_ck0_S15.0_T40",
   0,
   15.0,
   40.0
  ],
  [
   "H2_ck0_S17.5_T30",
   0,
   17.5,
   30.0
  ],
  [
   "H2_ck0_S17.5_T40",
   0,
   17.5,
   40.0
  ],
  [
   "H2_ck0_S20.0_T30",
   0,
   20.0,
   30.0
  ],
  [
   "H2_ck0_S20.0_T40",
   0,
   20.0,
   40.0
  ],
  [
   "H2_ck0_S25.0_T30",
   0,
   25.0,
   30.0
  ],
  [
   "H2_ck0_S25.0_T40",
   0,
   25.0,
   40.0
  ]
 ],
 "source_files": [
  "nq-levels/src/nqlevels/features/zones.py (zone universe, band, confirmation)",
  "nq-levels/src/nqlevels/features/interactions.py (tap engine, re-arm, tap_no, side)",
  "nq-levels/scripts/p14_common.py (R4v10 fire rule, checkpoints, entry convention, S/T grids)",
  "nq-levels/scripts/build_p14_fire.py (fire dataset: resistance role, n_fwd>=1800)",
  "nq-levels/scripts/run_p18_stageb.py (H2 cells, one-open-trade rule, 1.0 pt cost)",
  "nq-levels/scripts/run_p14_final.py (P14 baseline cell ck2 S12.5/T30)",
  "nq-levels/RESEARCH_PLAN.md \u00a718.2, \u00a720.2, \u00a721.1, \u00a729; EXPERIMENT_LOG.md P13-384, P14-392, P18-403/404, P24"
 ]
}
```

- OLD = frozen evaluator on 1-s bars (stop on 1-s high touch, target on 1-s low TOUCH, same-second tie = stop, flat 1.0 pt RT). NEW = tick engine (stop on first print at/through + slippage, target requires trade-THROUGH by 1 tick, exact print order).
- Legacy tier = NEW gross ledger minus a flat 1.0 pt ($20) per trade, to isolate execution differences from cost differences.
- Holdout 2026-06-18..08-14 NOT touched. NOTE: nq-levels Phase 17B already opened that window once for the model-gated Balanced variant (FAIL).

## P14_ck2_S12.5_T30
| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy(1pt) n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| development | 2585 | 0.210 | 1.31 | 0.38 | 6,776 | 2563 | 0.18 | 1.27 | 0.26 | 1.41 | 2562 | 0.21 | 1.33 | 0.37 | 136,927.40 | 0.15 | 1.22 |
| validation1 | 1050 | 0.102 | 1.15 | 0.35 | 1,336 | 1041 | 0.13 | 1.19 | 0.21 | 1.33 | 1043 | 0.15 | 1.22 | 0.35 | 39,678.60 | 0.08 | 1.11 |
| validation2 | 2703 | 0.223 | 1.34 | 0.38 | 7,539 | 2670 | 0.24 | 1.36 | 0.32 | 1.52 | 2671 | 0.26 | 1.40 | 0.38 | 175,444.20 | 0.18 | 1.25 |

## H2_ck0_S15.0_T30
| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy(1pt) n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| development | 2574 | 0.171 | 1.27 | 0.41 | 6,611 | 2552 | 0.16 | 1.26 | 0.23 | 1.39 | 2553 | 0.19 | 1.31 | 0.41 | 147,150.60 | 0.13 | 1.21 |
| validation1 | 1039 | 0.172 | 1.28 | 0.42 | 2,680 | 1036 | 0.20 | 1.32 | 0.26 | 1.46 | 1035 | 0.20 | 1.34 | 0.42 | 63,497.00 | 0.14 | 1.22 |
| validation2 | 2706 | 0.254 | 1.43 | 0.44 | 10,322 | 2666 | 0.25 | 1.41 | 0.32 | 1.56 | 2666 | 0.27 | 1.46 | 0.44 | 215,973.20 | 0.21 | 1.34 |

## H2_ck0_S15.0_T40
| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy(1pt) n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| development | 2516 | 0.197 | 1.28 | 0.35 | 7,424 | 2489 | 0.19 | 1.27 | 0.26 | 1.39 | 2491 | 0.21 | 1.31 | 0.34 | 159,273.20 | 0.15 | 1.21 |
| validation1 | 1020 | 0.170 | 1.24 | 0.34 | 2,594 | 1015 | 0.23 | 1.33 | 0.29 | 1.46 | 1017 | 0.24 | 1.35 | 0.35 | 72,433.40 | 0.17 | 1.24 |
| validation2 | 2658 | 0.301 | 1.45 | 0.37 | 12,015 | 2623 | 0.29 | 1.43 | 0.36 | 1.57 | 2622 | 0.32 | 1.48 | 0.37 | 250,949.40 | 0.27 | 1.39 |

## H2_ck0_S17.5_T30
| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy(1pt) n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| development | 2552 | 0.156 | 1.27 | 0.45 | 6,962 | 2531 | 0.17 | 1.29 | 0.22 | 1.41 | 2530 | 0.19 | 1.34 | 0.45 | 170,221.00 | 0.15 | 1.25 |
| validation1 | 1028 | 0.165 | 1.29 | 0.45 | 2,977 | 1027 | 0.18 | 1.31 | 0.23 | 1.43 | 1025 | 0.21 | 1.37 | 0.46 | 74,320.00 | 0.15 | 1.25 |
| validation2 | 2691 | 0.228 | 1.41 | 0.47 | 10,732 | 2657 | 0.25 | 1.46 | 0.31 | 1.59 | 2656 | 0.27 | 1.49 | 0.48 | 249,061.20 | 0.23 | 1.40 |

## H2_ck0_S17.5_T40
| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy(1pt) n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| development | 2485 | 0.189 | 1.29 | 0.38 | 8,216 | 2456 | 0.19 | 1.30 | 0.25 | 1.41 | 2456 | 0.21 | 1.34 | 0.38 | 183,751.20 | 0.16 | 1.25 |
| validation1 | 1005 | 0.161 | 1.25 | 0.38 | 2,823 | 1004 | 0.20 | 1.31 | 0.26 | 1.42 | 1004 | 0.23 | 1.37 | 0.39 | 81,335.80 | 0.16 | 1.25 |
| validation2 | 2636 | 0.271 | 1.43 | 0.41 | 12,517 | 2605 | 0.30 | 1.48 | 0.36 | 1.61 | 2606 | 0.31 | 1.51 | 0.41 | 286,701.20 | 0.27 | 1.42 |

## H2_ck0_S20.0_T30
| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy(1pt) n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| development | 2529 | 0.157 | 1.29 | 0.48 | 7,923 | 2508 | 0.15 | 1.27 | 0.20 | 1.38 | 2509 | 0.16 | 1.30 | 0.47 | 163,501.80 | 0.13 | 1.23 |
| validation1 | 1021 | 0.149 | 1.28 | 0.48 | 3,051 | 1020 | 0.14 | 1.25 | 0.19 | 1.36 | 1019 | 0.16 | 1.30 | 0.48 | 66,513.80 | 0.14 | 1.25 |
| validation2 | 2675 | 0.229 | 1.45 | 0.51 | 12,271 | 2643 | 0.24 | 1.46 | 0.29 | 1.59 | 2641 | 0.26 | 1.51 | 0.51 | 270,393.20 | 0.22 | 1.42 |

## H2_ck0_S20.0_T40
| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy(1pt) n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| development | 2456 | 0.187 | 1.31 | 0.42 | 9,188 | 2430 | 0.16 | 1.26 | 0.21 | 1.36 | 2432 | 0.18 | 1.30 | 0.40 | 175,261.40 | 0.14 | 1.22 |
| validation1 | 992 | 0.145 | 1.23 | 0.40 | 2,886 | 995 | 0.17 | 1.28 | 0.22 | 1.37 | 996 | 0.19 | 1.32 | 0.41 | 76,324.20 | 0.16 | 1.25 |
| validation2 | 2616 | 0.277 | 1.48 | 0.44 | 14,486 | 2585 | 0.29 | 1.50 | 0.34 | 1.61 | 2586 | 0.31 | 1.54 | 0.45 | 318,847.20 | 0.27 | 1.45 |

## H2_ck0_S25.0_T30
| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy(1pt) n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| development | 2483 | 0.125 | 1.26 | 0.53 | 7,764 | 2462 | 0.12 | 1.24 | 0.16 | 1.33 | 2465 | 0.13 | 1.27 | 0.52 | 163,608.00 | 0.11 | 1.21 |
| validation1 | 1006 | 0.127 | 1.26 | 0.53 | 3,191 | 1005 | 0.12 | 1.24 | 0.16 | 1.33 | 1004 | 0.13 | 1.27 | 0.52 | 65,510.80 | 0.11 | 1.22 |
| validation2 | 2648 | 0.197 | 1.43 | 0.56 | 13,029 | 2614 | 0.20 | 1.44 | 0.24 | 1.55 | 2614 | 0.21 | 1.48 | 0.56 | 280,297.80 | 0.19 | 1.40 |

## H2_ck0_S25.0_T40
| phase | OLD n | OLD expR | OLD PF | OLD WR | OLD pts | NEW-legacy(1pt) n | expR | PF | NEW-gross expR | PF | NEW-base n | expR | PF | WR | net $ | NEW-stress expR | PF |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| development | 2392 | 0.155 | 1.28 | 0.46 | 9,292 | 2369 | 0.13 | 1.24 | 0.17 | 1.32 | 2370 | 0.15 | 1.27 | 0.45 | 178,509.00 | 0.12 | 1.21 |
| validation1 | 972 | 0.129 | 1.23 | 0.45 | 3,135 | 971 | 0.14 | 1.26 | 0.18 | 1.34 | 974 | 0.16 | 1.29 | 0.46 | 78,554.80 | 0.13 | 1.24 |
| validation2 | 2580 | 0.225 | 1.43 | 0.49 | 14,530 | 2545 | 0.23 | 1.43 | 0.27 | 1.53 | 2547 | 0.25 | 1.47 | 0.49 | 314,069.40 | 0.22 | 1.40 |
