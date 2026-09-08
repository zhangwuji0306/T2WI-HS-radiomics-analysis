# R6-5R W08 source binding refresh audit

## Disposition

`PASS` — the R6-5R coordinate provenance register now matches the W08 source
files at the code state used for this refresh, `a35d858f5832e1e5c3d88eb9fe601b894a7d6916`.
The source binding refresh is limited to the two `provenance.file_sha256`
entries in `prognosis_analysis/R6_5R_coordinate_reconciliation.json`.

## Current source bindings

| Path | SHA-256 |
|---|---|
| `prognosis_analysis/scripts/w08_formal_run_a.py` | `261969f49d34a2dc3bf20800fb8df679a6dd6d3290636b0d71fc3157bea42b0b` |
| `prognosis_analysis/scripts/w08_nested_cv.py` | `c8fa83a420d02dcde9e99f1cfad7c74b675a5c3281d712be489f7f248fe77c66` |

The recorded values were recomputed from the current files. No W08 source,
configuration, scientific parameter, outcome, B-side, formal-output,
model-freeze, or W09 file was changed.

## Environment

All Python checks used `tools\\run_t2_radiomics.ps1` and `environment.yml`'s
`t2_radiomics` environment: Python 3.7.12, NumPy 1.21.6, pandas 1.3.5,
SciPy 1.7.3, scikit-learn 1.0.2, PyRadiomics 3.0.1, SimpleITK 2.2.1, and
PyWavelets 1.3.0.

## Verification

- R6-5 validation plus L3C regression: 10/10 passed.
- W08 nested-CV regression: 30/30 passed.
- W08 transactional outputs, formal release gate, and technical preflight:
  70/70 passed.
- Targeted `compileall`: passed.
- `git diff --check`: passed.
- Full test discovery: 290 tests, 289 passed, 1 pre-existing failure, 0
  errors. The failure is
  `test_execution_status_is_the_failed_w08_hold_state`, whose assertion still
  expects `minimum ROI` while the recorded summary is
  `External execution session interrupted before formal W08 result writing.`
  This is independent of the source-hash registration and remains outside
  this remediation scope.

No newly changed line contains an absolute local path, credential, or patient
identifier. The R6-5R stage remains B-blinded and the W08 gate remains `HOLD`.
