# R6-5R W08 source binding refresh audit

## Disposition

`PASS` — the R6-5R coordinate provenance register matches the W08 source
files at the current L4 implementation state. The source binding refresh is
limited to the two `provenance.file_sha256` entries in
`prognosis_analysis/R6_5R_coordinate_reconciliation.json`; no scientific,
population, solver, outcome, B-side, or formal-output binding was changed.

## Current source bindings

| Path | SHA-256 |
|---|---|
| `prognosis_analysis/scripts/w08_formal_run_a.py` | `7ec78f7d1c55bf4fe7f7f63097c77fb886b29dc3ce0292035561a0ae437595e5` |
| `prognosis_analysis/scripts/w08_nested_cv.py` | `aa47023edf83a5b3f4af9658ea761f10d8fb736b45fa2f91500c0f23d7ea74be` |

The recorded values were recomputed from the current files. The L4 source
implementation is the intended code change; no additional W08 configuration,
scientific parameter, outcome, B-side, formal-output, model-freeze, or W09
file was changed.

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
- Full test discovery before L4: 290 tests, 289 passed, 1 pre-existing
  failure, 0 errors. The failure is
  `test_execution_status_is_the_failed_w08_hold_state`, whose assertion still
  expects `minimum ROI` while the recorded summary is
  `External execution session interrupted before formal W08 result writing.`
  This is independent of the source-hash registration and remains outside
  this remediation scope.

No newly changed line contains an absolute local path, credential, or patient
identifier. The R6-5R stage remains B-blinded and the W08 gate remains `HOLD`.
