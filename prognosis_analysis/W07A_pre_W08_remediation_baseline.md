# W07A Pre-W08 remediation baseline

## Baseline

- Remediation start commit: `78b0e8f48becd64413859027e8809e155ecded5e`
- W04 modeling protocol SHA-256: `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe`
- Original `habitat_analysis/freeze_lock.json` SHA-256: `0388b8372a737cfaca7f8e9989aad68d63d7176a3fb93477b83c96f377001262`
- W03 `R_low` candidate hash (49 candidates): `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0`
- W03 `R_high` candidate hash (10 candidates): `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`
- W07 outer split SHA-256: `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`

## W08 status

- Formal W08: `HOLD`; the formal repeated nested cross-validation has not started.
- Held-out predictions: none.
- W08 performance metrics: none.
- Confirmed blocker: the technical preflight found 15 dual-radiomics cases in the first outer fold with at least one fold-specific habitat mask below the frozen `minimumROISize=10` voxel rule. At least one affected mask had a highest-habitat count of 0; other affected masks were in the 5–9 voxel range. Formal extraction is blocked under the current frozen specification. The minimum was not lowered, affected cases were not imputed, and the population was not dynamically changed.

## B access and patient-level artifacts

- `model_freeze_lock.json`: absent.
- `B_data_read=false`.
- `B_reader_invoked=false`.
- `B_source_opened=false`.
- `B_statistics_generated=false`.
- Patient-level W08 predictions, metrics, and other formal W08 artifacts: none.

## First-stage lock integrity

- `habitat_analysis/freeze_lock.json`: present.
- SHA-256: `0388b8372a737cfaca7f8e9989aad68d63d7176a3fb93477b83c96f377001262`.
- Git worktree and diff checks for the first-stage lock: clean.

## Evidence files and verification time

Verification time: `2026-09-02T13:45:22+08:00`.

- `PROJECT_STATUS.md`
- `T2WI-HS-radiomics-analysis Pre-W08 整改、协议补丁与后续 A-only 建模分包工作流.md`
- `prognosis_analysis/modeling_protocol.md`
- `prognosis_analysis/modeling_protocol.json`
- `prognosis_analysis/W07_outer_splits_protocol.md`
- `prognosis_analysis/W08_nested_cv_protocol.md`
- `prognosis_analysis/W08_implementation_audit.md`
- `prognosis_analysis/W08_preflight_execution_audit.md`
- `prognosis_analysis/configs/w08_nested_cv.json`
- `prognosis_analysis/configs/w08_audit_schema.json`
- `prognosis_analysis/configs/w08_results_schema.json`
- `prognosis_analysis/scripts/w07_outer_splits.py`
- `prognosis_analysis/scripts/w08_nested_cv.py`
- `prognosis_analysis/scripts/w08_formal_run_a.py`
- `habitat_analysis/freeze_lock.json`
