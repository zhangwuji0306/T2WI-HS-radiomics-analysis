# W08 preflight execution audit

## Scope and status

This audit records the local W08 A-only preflight. The formal repeated nested
cross-validation was not started, and no W08 held-out predictions or model
metrics were produced.

## Preflight findings

- A-only smoke: 393 A cases passed the provider smoke check.
- First outer-fold provider contract: passed. The provider fit boundary used
  outer-training cases only, and the held-out transformation path was
  validated without entering the fit.
- Dual-radiomics preflight population: 354 eligible cases.
- First outer fold: 15 cases had at least one fold-specific habitat mask below
  the frozen minimum ROI size of 10 voxels. The affected mask included a
  highest-habitat count of 0 in at least one case; other affected masks were in
  the 5–9 voxel range.
- Frozen rule: PyRadiomics `minimumROISize=10` applies to both habitat
  radiomics blocks. The preflight therefore blocks formal extraction for this
  population under the current frozen specification.

The minimum was not lowered, affected cases were not imputed, and the
population was not dynamically changed.

## Output and access controls

- Formal W08 run: not started.
- W08 held-out predictions: none.
- W08 metrics: none.
- `prognosis_analysis/model_freeze_lock.json`: not present.
- `B_data_read=false`.
- No B reader, B source, or B-derived statistics were used.
- No patient-level output is part of this audit. Local generated caches under
  `prognosis_analysis/output/w08_formal_A` remain excluded by repository
  rules and are not committed.

## Verification

- `python -m py_compile` for the W08 adapter, W07 split module, W08 nested-CV
  module, and W08 tests: passed.
- W08 JSON schema validation for `w08_audit_schema.json` and
  `w08_results_schema.json`: passed.
- `python -m unittest tests.test_w08_nested_cv -v`: 16 tests passed.
- The repository submission contains no patient identifiers, raw imaging
  paths, clinical/outcome tables, SLIC caches, predictions, or metrics.
