# FT02 contract

## Role and boundary

Execute only FT02 of the updated `T2WI-HS 生境预后快速验证（FT）方案书.md`: implement the A-only modeling runner and technical validation. FT00 and amended FT01 are accepted for downstream use. Do not execute FT03–FT06.

Worker session constraints:

- This is already the independent Worker session. Do not create, open, spawn, delegate to, or request any other conversation, session, thread, subagent, child agent, nested agent, or equivalent.
- Complete only FT02; if impossible without delegation, stop and return the blocker.
- Work locally in `<LOCAL_PATH>` on `codex/ft-validation`.
- All Python execution must use `tools/run_t2_radiomics.ps1 -PythonArguments ...` with the `t2_radiomics` environment from `environment.yml`; do not use arbitrary Python or direct conda commands.

## Accepted prerequisites

- `prognosis_analysis/ft/FT00_protocol.json`
- `prognosis_analysis/ft/FT_protocol_amendment_20260911.json`
- `prognosis_analysis/ft/FT01_asset_manifest.json`
- `prognosis_analysis/ft/FT01_asset_audit.md`
- Existing A-only access readers, W07 frozen repeat-1 split artifact, A technical/full_A/habitat/W02/W03 assets, and current project tests.

## Required implementation

Build a reusable FT-only A modeling runner with the fixed model definitions:

- M0: C
- M1: C + H_high_fraction
- M2: C + G
- M3L: C + G + R_low
- M3H: C + G + R_high
- M4: C + G + R_low + R_high
- M5: C + W_Original, where W_Original is the existing 107-feature whole-tumor Original-only block; Wavelet/LoG/other filtered features are excluded.

Use Cox for all models, alpha=1 for high-dimensional models, ordinary single-layer 5-fold CV for A, and the pre-frozen W07 repeat-1 fold set without regeneration from performance. All data-driven preprocessing must be training-only: imputation, NZV/variance filtering, correlation reduction, scaling, λ selection and coefficients. Preserve structural absence semantics for R_low/R_high and explicit feature availability. Keep paired eligibility and common-population comparisons explicit, including M4 vs M5 on dual-radiomics ∩ W_Original availability.

Implement the technical interfaces needed for FT03: risk prediction, Uno/Harrell C-index hooks, 3/5-year AUC/Brier hooks, calibration/KM/DCA data hooks, bootstrap seed/mode hooks, paired comparisons, artifact hashes/provenance and fail-closed validation. FT02 need not run patient-level A performance; that belongs to FT03.

## Required validation

- Synthetic tests for all seven model definitions, fixed split propagation, training-only preprocessing and λ selection, explicit availability/structural absence, paired eligibility, W_Original-only schema, and B-row/path rejection.
- Regression/static tests for FT isolation: no B reads, no B extraction, no formal `model_freeze_lock.json` writes, and no formal W08/L9 output mutations.
- Use the locked wrapper/environment for all test execution and record commands, versions, exit codes and pass counts.

## Authorized writes

- FT-only scripts/configs/tests and `prognosis_analysis/ft/FT02_technical_audit.md`.
- Minimal FT-only package/module code needed by FT03; no changes to formal W08/L9 modeling semantics or shared locked assets.
- No patient-level output, B data, raw IDs, absolute paths, credentials or large sensitive files in tracked deliverables.

## Acceptance criteria

- M0–M5 and all required preprocessing/modeling contracts are executable on synthetic A-like data.
- W_Original is the only whole-tumor feature block; filtered features are excluded.
- Tests pass in `t2_radiomics` through the wrapper, with evidence recorded.
- B remains unread and ungenerated; formal locks/output state remains unchanged.
- FT03 can consume the runner through observable, documented interfaces.
