# FT05A Independent Pre-run Code Audit

Independent review: true

Reviewed implementation commit: `7ddc4458f11fd631173e3778bd2a1ac518f74143`

## Verdict

Verdict: FAIL

FT05A is not authorized to access real B technical assets. The implementation has correct frozen-boundary, no-refit, candidate-order, PyRadiomics-configuration, and W_Original-reuse checks, but the pre-run and one-time-extraction boundary is not yet fail-closed.

## Evidence

- Static inspection covered `prognosis_analysis/ft/ft05a_runner.py`, `tests/test_ft05a_runner.py`, the accepted FT00–FT04 records, the FT amendment, the FT05A preparation contract, and the frozen habitat/W03 implementation and configuration.
- The canonical FT04 lock validates through the required wrapper with status `VALID` and lock identity `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`.
- The focused FT05A synthetic suite passed: 11 tests run, 11 passed, 0 failed.
- The combined FT05A/FT04 suite ran 35 tests with one failure in `test_missing_or_forged_ft04_review_fails_closed`. The test assumes that no canonical FT04 review exists, whereas the accepted canonical review now exists and validates. This is a stale test-state expectation and does not invalidate the production FT04 prerequisite gate.
- The runner's static command reported no clustering fit, B outcome reader, whole-tumour re-extraction, or declared formal-directory mixing.
- A wrapper-only interface probe showed that the FT05A table omits all nine frozen clinical predictors required by the accepted FT04 canonical B table validator. The same probe showed that an output root named `w08_nested_cv` is not classified as formal and is accepted as its own namespace root.
- No real B image, ROI, feature asset, clinical source, outcome source, patient record, or real FT05 manifest was enumerated, opened, hashed, copied, or generated during this review.

## Mandatory checks

| Check | Result | Evidence |
|---|---|---|
| Exact frozen A-full boundary | PASS | Preflight validates the accepted FT04 lock, the frozen FT01 definition, K=2, `n_init=100`, SLIC parameters and hashes; the production processor applies the frozen numeric boundary directly. |
| No habitat fitting on B | PASS | The production path contains no K-means import or fit call and assigns B supervoxels by direct comparison with the frozen A boundary. |
| No B outcome read or availability | FAIL | Column/path denylisting exists, but the CLI loads the B technical cohort at `ft05a_runner.py:1172` before `run_ft05a` performs the FT04/code-audit preflight. Therefore the required prerequisite-before-any-B-read ordering is not guaranteed. |
| Frozen PyRadiomics configuration unchanged | PASS | The W03 configuration file hash and Original-only settings are validated, and extraction settings match the frozen W03 parameter set. |
| No whole-tumour extraction; exact W_Original reuse | PASS | W_Original is bound to the FT04 path, file hash, 107-feature order hash, reuse flag, and per-patient finite values; no whole-tumour extractor exists in FT05A. |
| Duplicate patients and extractions rejected | FAIL | Duplicate patient/source mappings and duplicate artifact filenames are checked, but run-state creation has no exclusive owner/lock. Concurrent invocations can both process the same not-yet-completed case before one artifact write is rejected, causing duplicate extraction. |
| Resume never recomputes completed or pilot cases | FAIL | Normal sequential resume skips recorded pilot/completed cases. However, completed artifacts are not bound by an artifact hash, and validation does not prove that the stored flattened row, patient ID, source record, and processor result agree. A modified row can be adopted without recomputation and frozen into the canonical table. Concurrent invocations also defeat the no-recomputation guarantee. |
| No formal-directory read or mixing | FAIL | Output-root validation compares the candidate root with itself, so any non-explicitly-denied root is accepted. Formal detection misses active names such as `w08_nested_cv`; the technical input allowlist also permits broad A/FT output roots rather than an exact FT05A technical-source contract. |

## Additional blocking findings

1. **The canonical FT05A output cannot pass the accepted FT04 consumer contract.** FT05A writes a technical-only table, while `ft04_runner._validate_ft05a_feature_table` requires the nine clinical predictors. Adding them in FT05A would violate outcome-blind technical isolation; leaving them out causes the frozen manifest to be rejected downstream. The current focused tests never submit the generated manifest/table to the accepted FT04 validator.
2. **The code-audit prerequisite is not bound to the reviewed runner.** `_validate_code_audit` accepts any file containing an independence marker and an accepted verdict. It does not require the reviewed commit, runner SHA-256, or contract identity, so a later code change could reuse this audit before B access.
3. **The production processor does not implement the frozen structural-support states.** It always invokes PyRadiomics for both habitat masks and always emits both blocks as structurally defined and technically available. Empty or small habitat masks are therefore treated as run failures instead of the frozen structural-absence/technical-small-ROI states, and the focused tests replace the production processor rather than exercising this path. This is especially material because the repository records the PyRadiomics 3.0.1 `minimumROISize=10` boundary behavior.
4. **Finalization is not atomic as a complete state transition.** The table and manifest are written before the run state is marked completed. A crash between those writes leaves a frozen manifest with a non-completed run state and no defined recovery path. The required technical audit is also validated only after the canonical table has been written.
5. **Pilot execution scans all target sources before processing the pilot.** `_source_records` hashes every cohort image and ROI before the selected pilot loop. This defeats a small-subset runtime measurement and broadens B technical reads beyond the pilot subset.

## Limited remediation plan

1. Move all cohort loading and every other B technical read behind a single preflight that validates the canonical FT04 lock/review/digest and a code-audit record bound to the exact FT05A runner SHA-256 and reviewed commit.
2. Replace self-relative output validation with fixed canonical FT05A roots and exact source-root contracts; reject formal, A, FT03, FT04, W08 and L9 namespaces by resolved-path containment rather than name fragments.
3. Reconcile the FT05A technical-only table schema with the accepted FT04 consumer contract. Keep clinical predictors out of FT05A, defer their join until the authorized outcome stage, and add an end-to-end synthetic test in which the actual FT05A manifest/table passes the canonical downstream manifest validator.
4. Add exclusive run ownership and atomic create semantics. Bind every case artifact to its exact input hashes, W_Original row, processor result, flattened row and schema; reject any mismatch. Test concurrent starts, interrupted writes, artifact tampering, pilot resume and completed-run refusal.
5. Implement and test the frozen structural-absence and technical-small-ROI states in the real production processor, including the PyRadiomics 3.0.1 size-boundary compatibility behavior, without imputing or silently substituting features.
6. Hash only selected pilot sources during the pilot, retain their completion artifacts in the canonical one-time run, and hash the remaining sources only when the same run is resumed.
7. Make finalization a recoverable, explicitly ordered transaction and update the stale FT04 review-absence test so the combined regression suite passes in the accepted repository state.

Real B technical access remains blocked pending an independent re-review of the remediated FT05A pre-run gate.
