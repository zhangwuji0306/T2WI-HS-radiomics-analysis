# W07A Pre-W08 Remediation Baseline

## Baseline identity

- Remediation start commit: `78b0e8f48becd64413859027e8809e155ecded5e`
- Verification time: `2026-09-02T13:46:57+08:00`
- Formal W08 status: `HOLD`

## Frozen provenance

| Item | Evidence artifact | SHA-256 / frozen value |
|---|---|---|
| W04 modeling protocol | `prognosis_analysis/modeling_protocol.json` | `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe` |
| Original technical freeze lock | `habitat_analysis/freeze_lock.json` | `0388b8372a737cfaca7f8e9989aad68d63d7176a3fb93477b83c96f377001262` |
| W03 R_low candidate pool | `prognosis_analysis/output/w03_habitat_radiomics_A/candidate_freeze.json` | `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0` (49 candidates) |
| W03 R_high candidate pool | `prognosis_analysis/output/w03_habitat_radiomics_A/candidate_freeze.json` | `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce` (10 candidates) |
| W07 outer split artifact | `prognosis_analysis/output/outer_splits_A.csv` | `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502` |

The W04, W03, and W07 values agree with the locked W08 configuration and
the W07/W08 audit records. The original `habitat_analysis/freeze_lock.json`
exists and has no unstaged or staged Git difference at this baseline.

## W08 status and blocking evidence

- Formal W08 repeated nested cross-validation: not started.
- Held-out predictions: absent.
- W08 performance metrics: absent.
- `prognosis_analysis/model_freeze_lock.json`: absent.
- The W08 output directory contains 382 local `.npz` files only under
  `prognosis_analysis/output/w08_formal_A/work/slic_cache`; no files matching
  formal predictions, metrics, fold results, or selection results are present.
  These caches are excluded by repository rules and are not repository
  artifacts.
- The confirmed HOLD reason is the frozen PyRadiomics `minimumROISize=10`
  rule for both habitat radiomics blocks. In the first outer-fold preflight,
  15 cases had at least one fold-specific habitat mask below 10 voxels,
  including a highest-habitat count of 0 in at least one case and other
  affected masks in the 5–9 voxel range. The minimum was not lowered, values
  were not imputed, and the population was not dynamically changed.

## B access status

| Control | Status |
|---|---|
| `B_data_read` | `false` |
| `B_reader_invoked` | `false` |
| `B_source_opened` | `false` |
| `B_statistics_generated` | `false` |

The W08 implementation and preflight audits record the same four isolation
flags. No B reader, B source, or B-derived statistics were used.

## Evidence register

The following repository or local non-patient-level artifacts were checked at
the verification time above:

| Evidence | SHA-256 |
|---|---|
| `PROJECT_STATUS.md` | `ff31afb0877209c4e6bba086a6c686d28d61334ed5e422bb86779f9e8ca7a474` |
| `prognosis_analysis/W07_outer_splits_protocol.md` | `058c3b8067d1e8429387e0a5bd999b41e9986e69220e07b5e7d3d0407fcff329` |
| `prognosis_analysis/configs/w07_outer_splits.json` | `535f0aa7caef877727dc08bb70741b1c96ed4542230b5cfbf173eeff48677217` |
| `prognosis_analysis/W07_source_binding_remediation_audit.md` | `769d6700b08f9f1ea34d8db97690e9008f043b569cfbdba65d699f91aa15b18c` |
| `prognosis_analysis/configs/w08_nested_cv.json` | `d4440fe3b30a23d25ba7f0937bc26c31ee3eac49721194c64a1a23362cd028cf` |
| `prognosis_analysis/configs/w08_audit_schema.json` | `5444287b46caea3ba314fdb3452899f256581e8427242e7984e04142f779ed2e` |
| `prognosis_analysis/configs/w08_results_schema.json` | `6ccf363ba1b9dd55c30c1b7ce04240b499273416e91247db0e6ec84073ad6e45` |
| `prognosis_analysis/W08_nested_cv_protocol.md` | `d3ab90d400edb9e6731443440e26f9c17322722af121994a64e8048f974c22f5` |
| `prognosis_analysis/W08_implementation_audit.md` | `ddaee0261ba083331d2a3e2d9cda3f337571c4582c63c0cc0d77f6aad3d038f1` |
| `prognosis_analysis/W08_preflight_execution_audit.md` | `28352163833f9ff1746dde5b73c22a39308113a8a3e92b40b6553dacf41cfa8b` |
| `prognosis_analysis/output/w03_habitat_radiomics_A/candidate_freeze.json` | `ae3ed731308d4915675678258bc1c23d9a9e9e493fec4dd57745e7049a3b5cb2` |
| `habitat_analysis/freeze_lock.json` | `0388b8372a737cfaca7f8e9989aad68d63d7176a3fb93477b83c96f377001262` |
