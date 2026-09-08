# W08 local L4 representation and cache audit

## Scope

This audit records the L4 implementation boundary for fold-specific A-only
representations. It contains no patient identifier, patient-level feature
value, clinical outcome, prediction, performance result, or local machine
path. No formal W08, W09, B validation, or model-freeze step was started.

## Locked environment

The project-root `environment.yml` is the sole environment contract:

- environment: `t2_radiomics`
- Python: `3.7.12`
- NumPy: `1.21.6`
- pandas: `1.3.5`
- SciPy: `1.7.3`
- scikit-learn: `1.0.2`
- PyRadiomics: `3.0.1`
- SimpleITK: `2.2.1`
- PyWavelets: `1.3.0`

The version probe reported `matches_locked_spec=true`. All tests and
compile checks in this audit were invoked through
`tools/run_t2_radiomics.ps1 -PythonArguments ...`.

## L4 implementation contract

1. `FoldRepresentationCache` binds every fitted state to the cache schema,
   sorted outer-training ID hash, K-means seed, required fold-feature schema,
   and provider identity. An identity or schema change invalidates the prior
   entry and refits it; a matching entry is reused only within the current
   process.
2. The formal A-only provider binds its representation identity to the L4
   contract, `environment.yml`, habitat configuration, exact extractor
   configuration, and frozen candidate identities.
3. SLIC cache entries carry a schema, contract hash, image/ROI input hashes,
   and image/ROI geometry hash. Missing metadata, changed inputs, changed
   geometry, malformed entries, and voxel mismatches are recorded as cache
   mismatches. Only the affected case is recomputed and atomically replaced;
   a cache write failure is fail-closed.
4. Fold representation entries are keyed by training-state provenance,
   exact habitat mask signature, boundary, case input binding, and geometry.
   R-low/R-high feature entries additionally require the exact block and
   voxel-level mask signature. Equal voxel counts or nearby boundaries never
   authorize reuse.
5. Training and validation transformations use the same immutable
   outer-training state. Validation IDs are not consumed by `fit`, and cache
   audit events expose hashes only.
6. Provider cache audit counters and mismatch events are returned in the
   in-memory W08 audit. No patient-level representation is promoted to a
   formal output by L4; local staging/output remains ignored by repository
   rules.

## Verification

- Locked environment probe: passed.
- `tests.test_w08_l4_representation_cache`: 4/4 passed.
- `tests.test_w08_nested_cv`: 30/30 passed.
- `tests.test_w08_formal_release_gate`: 40/40 passed.
- Locked-environment `compileall` for the modified scripts and test suite:
  passed.
- `git diff --check`: passed.
- Full test discovery: 294 tests, 293 passed, 1 pre-existing unrelated
  failure in `test_execution_status_is_the_failed_w08_hold_state`; the test
  still expects `minimum ROI` while the recorded historical summary is
  `External execution session interrupted before formal W08 result writing.`
- Real A processing, formal W08, predictions, performance, W09, B access,
  and model freeze: not invoked.

## Boundary

`B_data_read=false`; `B_reader_invoked=false`; `B_source_opened=false`;
`B_statistics_generated=false`; `formal_writer_invoked=false`;
`patient_level_outputs_written=false`.
