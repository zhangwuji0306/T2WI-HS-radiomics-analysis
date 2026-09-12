# FT05A Independent Pre-run Code Audit — Round 2

Independent review: true

Reviewed implementation commit: `35f873ac8333f4f8c0e8e770b87a79e36635d4da`

FT05A runner SHA-256: `0f50cadef8ac72d773b12305bbeb7846b793010ffa1b35e8d7837d903dd42b05`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: FAIL

FT05A remains unauthorized to access real B technical assets. The remediation closes the ordinary preflight, fixed-source-root, technical-only schema, ownership, artifact-binding, pilot-resume, structural-state, and normal finalization paths. Independent synthetic review found residual fail-open paths in finalization recovery and downstream provenance validation, plus a code-audit commit binding that cannot remain valid after the required report-only commit.

## Evidence

- Reviewed the repository instructions, FT scheme and amendment, accepted FT00–FT04 records, both prior FT05A contracts, the FT05A preparation contract, remediation commit `35f873ac8333f4f8c0e8e770b87a79e36635d4da`, current FT05A/FT04 code, and current tests.
- The locked wrapper environment probe and FT04 validation completed successfully. FT04 reported `status: VALID` with lock identity `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`.
- `tools/run_t2_radiomics.ps1 -PythonArguments @('.\\prognosis_analysis\\ft\\ft05a_runner.py','static-validate')` returned `pass: true`, with no B K-means fit, outcome reader, whole-tumour re-extraction, or formal-directory mixing finding.
- The focused FT05A synthetic suite passed: 20 tests, 20 passed.
- The accepted-state combined regression passed: 85 tests, 85 passed, including the corrected FT04 review-absence test.
- A synthetic `FINALIZING` state containing an arbitrary table and only `{artifact_id: FT05_B_feature_manifest, status: frozen}` manifest was accepted by `_recover_finalization`; the arbitrary table was installed and the state was marked complete. Recovery does not revalidate the technical table, manifest contract, transaction paths, or W_Original binding.
- A generated synthetic technical manifest was mutated so one source record contained a formal relative path, a forged source hash, and a forged case-identity hash. `validate_ft05a_technical_manifest` accepted the mutated manifest because it checks only field presence and hash shape for source records, not path allowlist, file binding, case identity, table correspondence, or source-record integrity.
- During pilot execution, `_load_w_original_asset` still hashes and reads the complete accepted W_Original CSV before the selected pilot loop. Thus the pilot does not restrict all B technical-source reads to the selected pilot cases.
- No real B image, ROI, feature asset, clinical source, outcome source, patient record, or real FT05 manifest was enumerated, opened, hashed, copied, or generated during this review.

## Mandatory checks

| Check | Result | Evidence |
|---|---|---|
| Exact frozen A-full boundary | PASS | FT04 lock, FT01 definition, K=2, `n_init=100`, SLIC settings, boundary and source hashes are validated before the technical cohort is loaded; production projection uses the frozen boundary directly. |
| No habitat fitting on B | PASS | Static validation found no clustering import, K-means symbol, or fitting call; production projection assigns labels directly from the frozen boundary. |
| No B outcome read or availability | PASS_WITH_FINDINGS | Technical columns and ordinary source paths are denylisted and cohort file loading is preflight-gated. The pilot still reads the complete W_Original asset before selected-case processing, and the downstream provenance validator accepts forged source paths. |
| Frozen PyRadiomics configuration unchanged | PASS | The accepted A/W03 configuration and hash are checked; Original-only settings, bin width, normalization, resampling, feature classes and minimum ROI boundary are enforced in the production path. |
| No whole-tumour extraction; exact W_Original reuse | PASS_WITH_FINDINGS | The normal run binds W_Original to the accepted FT04 asset, hash, order and reuse-only flags. Finalization recovery can complete without rechecking the current W_Original asset. |
| Duplicate patients and extractions rejected | PASS_WITH_FINDINGS | Loader, case identity, ownership, state and artifact checks reject ordinary duplicates and concurrent starts. A tampered finalization state can bypass the normal artifact/table validation. |
| Resume never recomputes completed or pilot cases | PASS_WITH_FINDINGS | Normal pilot and resume tests pass and completed artifacts are hash-bound. Recovery of a tampered `FINALIZING` state is not bound to the canonical table/manifest contract. |
| No formal-directory read or mixing | FAIL | Normal input/output paths are constrained, but `_recover_finalization` validates transaction paths only as project-relative paths and can install state-supplied files outside the FT05A namespace; the downstream source-record validator also accepts a forged formal path. |

## Residual blocking findings

1. **Finalization recovery trusts mutable state.** `_recover_finalization` verifies only the hashes supplied by the `FINALIZING` state and the manifest's two identity fields. It does not validate the installed table with `_validate_technical_table_frame`, validate the manifest with `validate_ft05a_technical_manifest`, compare manifest/table bindings, verify case-completion evidence, or constrain transaction targets to the canonical FT05A namespace. A modified or partially corrupted ignored run-state file can therefore finalize an arbitrary table/manifest and mark the run `COMPLETED`.

2. **The canonical technical manifest validator does not bind source provenance.** `validate_ft05a_technical_manifest` requires source-record keys and 64-hex strings but does not validate source paths against the exact technical root, hash the referenced files, recompute case identities, match source records to table rows, or verify W_Original row/asset bindings. The synthetic tamper probe accepted a forged formal path and source identity. This leaves a canonical downstream technical validator that is not fail-closed on provenance or formal mixing.

3. **The code-audit commit binding is self-invalidating after the mandated report commit.** `_validate_code_audit` requires `Reviewed implementation commit` to equal the current `HEAD`. The report is required to be committed as the only tracked change after reviewing implementation commit `35f873a...`; that report-only commit necessarily changes `HEAD`, so the audit no longer validates before the later execution Worker. The binding also accepts any text containing `independent` rather than requiring an explicit independent-review marker.

4. **Pilot source restriction is incomplete.** The pilot loop limits image/ROI hashing to selected cases, but `_load_w_original_asset` reads and hashes the entire accepted B W_Original asset before the pilot selection is applied. This does not meet the round-2 requirement that pilot mode read/hash only selected sources.

## Disposition

The FT04 prerequisite and combined regression are valid, and the ordinary FT05A paths are substantially improved. The four residual findings are blocking because they permit a tampered recovery state or manifest to escape the technical-only and FT05A namespace contracts, and because the accepted code-audit record cannot survive the required report-only commit. Real B technical execution must not start.
