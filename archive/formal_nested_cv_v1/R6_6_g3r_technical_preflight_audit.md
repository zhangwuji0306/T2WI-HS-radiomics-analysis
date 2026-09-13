# R6-6/G3R technical preflight audit

## Result state

- Status: `READY_FOR_INDEPENDENT_REVIEW`
- Scope: final-code P5-equivalent technical-only preflight
- Technical preflight gate: `PASS`
- Independent G3R review: `PENDING`
- This evidence is not formal W08 authorization and does not establish an accepted G3R gate.

## Execution

- Entry point: `prognosis_analysis/scripts/w08_technical_preflight_a.py`
- Command: `tools\run_t2_radiomics.ps1 -PythonArguments @('prognosis_analysis/scripts/w08_technical_preflight_a.py','--output','prognosis_analysis/output/p5_technical_preflight_A_R6_6_G3R')`
- Exit code: `0`
- Code commit: `15fc59e36cc9b9337d32f77148ba6c0d3463fd00`
- Historical duration reference for the same full entry point: `168.186` seconds
- Locked environment: `t2_radiomics`; Python `3.7.12`; NumPy `1.21.6`; pandas `1.3.5`; SciPy `1.7.3`; scikit-learn `1.0.2`; PyRadiomics `3.0.1`; SimpleITK `2.2.1`
- Environment probe exit code: `0`
- Technical regression command exit code: `0`; `51` tests, `0` failures, `0` errors, `0` skips

## Completeness and feasibility

- Fixed design: `10` repeats × `5` frozen outer folds = `50/50` fold units.
- Fixed technical definitions: `17`.
- Aggregate records: `850/850`; each definition has exactly `50` records.
- Missing fold-definition records: `0`.
- Duplicate fold-definition records: `0`.
- All required technical runs estimable: `true`.
- All paired comparator populations valid: `true`.
- Inner 5-fold technical feasibility: `true` for all `850` records.
- Minimum event/censor counts across eligible populations: train `62/210`, validation `13/49`.

The 17 fixed definitions are: `M0`, `M1`, `M2`, `M0_W_available`, `M5`, `M2_R_low`, `M3L`, `M2_R_high`, `M3H`, `M2_dual_radiomics`, `M3L_dual_radiomics`, `M3H_dual_radiomics`, `M4`, `M0-R`, `M1-R`, `M2-R`, and `M3L_vs_M3H`.

## Technical correctness

- Frozen W07 split SHA-256: `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`.
- Frozen SLIC/supervoxel assets were used.
- Habitat centres were fitted by training-only, patient-balanced K=2; validation cases were not used for centre fitting or boundary assignment.
- P3B contract: `structural_absence = 0 voxels`; `technical_small_roi = 1–9 voxels`; `extractable >=10 voxels`.
- `minimumROISize=10`.
- Eligibility was applied after provider transform and before preprocessing.
- Fold-specific model populations and same-fold paired-population rules were preserved.
- Frozen candidate hashes: R_low `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0`; R_high `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`.

## Provenance and solver bindings

The machine-readable companion records SHA-256 bindings for the technical freeze, W04, W07, W07A, P4R, R6-4A, R6-5R, and R6-5 evidence. Current solver/config bindings are:

- `w08_nested_cv.py`: `87b919d82a199461882af280adfc34a0e5e2a59974a1c4def6e3f6f9b393f6ce`
- `w08_nested_cv.json`: `0d4cbec42fc0a26e59a31d189285e83eb134628ea949c92100325d04873637a0`
- `w08_technical_preflight_a.py`: `72f8f616f76303ba04f87e52ffe6c210638ee18ce09c3076a86bff3990bd55ad`
- Elastic-Net lock: `max_iter=3000`, `tolerance=1e-7`, alpha grid `[0.1, 0.5, 0.9, 1.0]`, 100 log-spaced lambda values per alpha, training-only lambda scope, inner-CV-only selection, joint penalty semantics, zero start, no warm start.
- Candidate pools, candidate order, W07 split, population rules, objective, gradient, and convergence criteria were unchanged.

## Safety boundary

- `B_data_read=false`
- `B_reader_invoked=false`
- `B_source_opened=false`
- `B_statistics_generated=false`
- No Cox fitting, risk score, prediction, performance metric, model comparison, calibration, or formal model output was generated.
- `R6-6.5` was not started.
- `model_freeze_lock.json` is absent.
- Preflight output is aggregate-only; privacy scan found zero patient-identifier or sensitive-field literals and no absolute local paths.

## Evidence paths

- Aggregate output: `prognosis_analysis/output/p5_technical_preflight_A_R6_6_G3R/`
- Machine-readable evidence: `prognosis_analysis/R6_6_g3r_technical_preflight.json`
- This audit: `prognosis_analysis/R6_6_g3r_technical_preflight_audit.md`

This is technical preflight evidence only. Independent review remains required before any R6-6.5 or formal W08 action.
