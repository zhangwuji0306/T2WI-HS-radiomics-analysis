# R6-5R first-failure coordinate reconciliation audit

## Disposition

`III` on the runner-recovery axis — the historical exact replay runner is not recoverable. The current canonical production reconstruction is `282/67`, matching the recorded R6-2 nominal coordinate, but the supplied III branch's `288/68` numerical premise is not observed. Therefore no historical canonical equivalence or numerical release conclusion is claimed; protocol-owner/Reviewer disposition remains required.

## Scope and boundary

- Coordinate: `repeat=1`, `outer_fold=1`, `population=R_high` only.
- Path B used the frozen W07 split, full outer training/validation A393 sides, `provider.fit(full outer training)`, `provider.transform(train + validation)`, P3B validation, and the existing `derive_fold_populations(..., population_names=['R_high'], require_p3b=True)` implementation.
- No `run_w08`, Cox fit, prediction, risk score, performance metric, convergence validation, or model comparison was called.
- B flags remain false; formal W08 remains `HOLD`; `model_freeze_lock.json` is absent.

## Path A — historical diagnostic reconstruction

| Field | Result |
|---|---|
| Status | `not_exactly_recoverable` |
| Required literal | `historical_diagnostic_runner_not_exactly_recoverable` |
| Runner path | `prognosis_analysis/scripts/_r6_2_diagnostic_replay.py` (absent) |
| Historical code commit recorded by R6-2 | `ae92f7cbbaf2ab5bfb608ab029ab0566d7203c55` |
| Exact replay starting train/validation n | unavailable; not inferred |
| Exact replay boundary | unavailable; not inferred |
| Exact replay P3B counts | unavailable; not inferred |
| Exact replay resulting train/validation n | unavailable; not inferred |
| Exact replay train/validation ID hashes | unavailable; not inferred |

Recorded R6-2 evidence (not a new reconstruction): `M2_R_high` at the same nominal coordinate reported `n_train=282` and `n_validation=67`; the R6-2 artifact does not provide the requested boundary/P3B counts or ID hashes.

## Path B — canonical production reconstruction

| Field | Train | Validation |
|---|---:|---:|
| Full outer side before fold eligibility | 314 | 79 |
| R_high structural absence | 21 | 7 |
| R_high technical-small-ROI | 11 | 5 |
| R_high extractable | 282 | 67 |
| Resulting R_high eligible n | 282 | 67 |

### Provider and P3B

- Provider: `AOnlyFoldFeatureProvider`; `formal_capable=True`; `fold_specific_habitat=True`.
- State fit scope: full outer training only; validation IDs were not used for fitting.
- Centers: `2.13187012852, 3.59814209276`; boundary: `2.86500611064` (representation: `aggregate/explicit`).
- P3B source: `P3B`; fields validated: `R_low_voxel_count, R_high_voxel_count, R_low_state, R_high_state, R_low_structurally_defined, R_high_structurally_defined, R_low_technically_extractable, R_high_technically_extractable`; minimum ROI threshold: `10`; eligibility stage: `after_provider_transform_before_any_preprocessing`.
- P3B hashes (train / validation / combined): `4981f5b2785b8f223d42a69a41567b4175d819f47b9566f92def1ac0f22f4c05` / `84af0be99d65e12e5aedca20b688c9c00ca06ac4de6fa13bd1f7cb44447cc8b7` / `3073fab85237e3a637bbfdc34244e91014d761f1ba57f947f0060d005ce66d99`.

### Reconciliation hashes

- Frozen W07 split file/canonical hash: `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502` / `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`.
- Full outer train ID hash: `7eeb6103574fd96ee4b698a00c7a5205dce6092490f3fb149c704057cd03af4b`; full outer validation ID hash: `941f0b0bfac12b74ec6f4115878ae994027a81b11360b061d0e12eeb8e790674`.
- Provider state training ID hash: `7eeb6103574fd96ee4b698a00c7a5205dce6092490f3fb149c704057cd03af4b`.
- R_high eligible train ID hash: `90b08549c4bd7204a8437ce5fb984af608ba019a0cc10e6d1124b9fbddaf41b1`; validation ID hash: `148ac9faad72ba250b558246967b26adfe3c52f9ff09e07377e6c3bef374dd06`.

## Provenance and execution

- Current code commit: `fb9eced7ce120b0bb8fd573d9d63130df555b97c`.
- Script/config/input SHA-256 values are recorded in the machine-readable companion JSON under `provenance.file_sha256`.
- Command: `tools\run_t2_radiomics.ps1 -PythonArguments @('local_private/r6_5r_coordinate_reconciliation_tmp.py')` (exit code `0`).
- Environment probe: `3.7.12` Python; NumPy `1.21.6`; pandas `1.3.5`; SciPy `1.7.3`; scikit-learn `1.0.2`; PyRadiomics `v3.0.1`; SimpleITK `2.2.1`.
- Technical checks: provider state validation, full train/validation transform membership validation, P3B eight-field cross-check, and production eligibility derivation all passed.

## Verification

- Technical/binding regression: `tools\run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_w07_outer_splits','tests.test_w08_technical_preflight_a')`; `28 tests`, exit code `0`.
- Combined provenance regression: `60 tests`, exit code `1` with `7` existing provenance snapshot errors and `1` existing `execution_status` wording failure; no historical or project-state file was changed.
- Aggregate JSON and privacy scan: PASS; no patient ID literal or absolute local path was found in the audit JSON.

## Preserved stage state

- B data read / reader invoked / source opened / statistics generated: `false / false / false / false`.
- Formal W08: `HOLD`; R6-5R did not start formal W08 and generated no final outputs.
- Cox fits / risk scores / predictions / performance: `false / false / false / false`.
- `prognosis_analysis/model_freeze_lock.json`: absent / not generated.
- W07, W07A, R6-4A, scientific, technical, statistical, eligibility, or population definitions: unchanged.
