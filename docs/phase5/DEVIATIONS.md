# Phase 5 — deviations from the pre-registered design (append-only)

- 2026-09-02 **Holdout base-rate exposure (disclosure, not a design change).** During the design pass, before the
  holdout window was defined, a descriptive base-rate table was printed for 2021 → 2026-H1, including the 2026-01-02 →
  2026-06-17 rows (up-share 59.6%, MFE>MAE share 58.8%, n = 114). No feature, model or threshold was derived from it. The
  parquet that held those rows (`runs/phase4/_design_target_baserates.parquet`) was deleted. The holdout report will
  state this exposure again.
- 2026-09-02 **Leakage test 6 (time-shift) replaced.** As written ("D+1 features must collapse a model to baseline") the
  test was ill-posed: D+1's features legitimately contain D's RTH outcome. Replaced by (a) an alignment test — the prior
  session features stored for D must equal the RTH statistics computed on D−1's own prints, and D+1's `prev_am_ret`
  must equal D's raw T1 return — and (b) a label-correlation scan: any feature whose development |correlation| with a
  same-day label exceeds 0.30 is flagged for audit (there is no legitimate reason for a pre-open feature to correlate
  that strongly with the 09:30–12:00 move).
- 2026-09-02 **Validation feature rows are not built at E2.** Building them would load 2024–2025 prints without a
  frozen spec; they are built at E9 with the frozen recipes' spec ids by the same deterministic code (feature values for
  a day depend only on prints ≤ that day, which the truncation tests verify).
- 2026-09-02 **Feature bank v1 is ~130 base features** rather than the ~180 estimated; fold-internal transforms and
  interactions (design §4-E) are added in E3 as planned. Every base feature is listed in `docs/phase5/FEATURES.md`.
