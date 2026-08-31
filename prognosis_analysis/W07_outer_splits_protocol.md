# W07 Outer CV Split Freeze

Status: frozen for A-only nested modeling.

W07 consumes the local W06 `A_modeling_population.csv` artifact only. The
input is the exact A393 modeling population after W06 endpoint QC: 393 cases,
89 DFS events and 304 censored observations. W07 does not open the clinical
workbook, radiomics tables, or any B artifact, and it does not perform model
fitting, nested CV, tuning, or performance-based eligibility selection.

## Frozen split design

- Outer design: stratified 5-fold CV × 10 repeats.
- Stratification variable: `DFS_event`.
- Outer validation folds: 50.
- Roles: `train` and `validation`.
- Seed root: 12345.
- Repeat seed: `12345 + (repeat - 1)` for repeat indices 1–10.
- Every train and validation fold must contain at least one DFS event.
- A patient occurs once in validation per repeat and in the four complementary
  training folds.

The resulting local sensitive artifact is
`prognosis_analysis/output/outer_splits_A.csv` with 19,650 rows and the
columns `patient_id`, `repeat`, `fold`, `role`, and `seed`. Its SHA-256 is
`24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`, recorded
as the `outer_split_hash` for downstream provenance.

All 50 train/validation fold pairs passed the event gate. Training-fold event
counts were 71–72 and validation-fold event counts were 17–18.

The same split plan is used for M0/M1/M2/M5, the R_low M2-versus-M3L
comparison, the R_high M2-versus-M3H comparison, the dual-radiomics
M2/M3L/M3H/M4 analysis, and the paired M3L-versus-M3H comparison. When a
comparison has a narrower fixed availability population, the corresponding
model and comparator are evaluated on the identical eligible patients and
the same repeat/fold assignments.

## Fixed population eligibility record

- Main population: exact W06 A393 modeling population; structural global
  habitat values are retained. Only W06-frozen technical exclusion, outcome
  unavailability, duplicated/invalid endpoint records, or explicit
  unrepairable source errors can exclude a case.
- Whole-tumor reference M5: main population intersected with W-available
  technical cases; M0 is refit on the same cases and folds.
- R_low: main population with structurally present and W03-technically
  available R_low; M2 uses the same cases and folds.
- R_high: main population with structurally present and W03-technically
  available R_high; M2 uses the same cases and folds.
- Dual-radiomics: cases with both R_low and R_high structurally and
  technically available; supports M2, M3L, M3H, M4 and the paired M3L versus
  M3H comparison.

These records define technical and availability populations only. They do not
use model performance, feature associations, or fold-level results.
