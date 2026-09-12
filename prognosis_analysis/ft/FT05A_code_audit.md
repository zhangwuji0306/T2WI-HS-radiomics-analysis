# FT05A Independent Pre-run Code Audit — Round 10

Independent review: true

Reviewed FT05A implementation commit: `b831845d57277f20f115329fd6ea4f0796d1dcd0`

FT05A runner SHA-256: `0f37da4c964beffafa1286f54199c267f186d2a9a4c620dcddb27dc270d95498`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: PASS_WITH_FINDINGS

## Scope and evidence

- Reviewed the repository instructions, FT scheme and approved amendment, accepted FT00–FT04 records and lock, all FT05A contracts and prior audit state, the actual current Git history/diff, `prognosis_analysis/ft/ft05a_runner.py`, and `tests/test_ft05a_runner.py`.
- The current implementation includes the full W_Original binding check before audit-identity migration: the migration path performs an unselected full-asset load at the exact FT04-bound path, verifies the expected full SHA-256, frozen feature count/order and reuse flags, verifies cohort coverage, and reconciles every completed artifact and source record before any migration state write.
- The persisted non-completed state is validated before migration. The checks cover the exact state schema, identity digest, unchanged identity fields except `code_audit_sha256`, run/cohort/count/hash consistency, unique completed case keys and artifact hashes, pilot-key containment, status-specific `PILOT_COMPLETE` evidence, and rejection of zero-completion migration states. Completed artifacts are revalidated against the current source hashes, W_Original rows, processor evidence, flattened rows, schema and stored artifact hashes.
- Migration writes only a copied state after all preconditions and post-migration structure checks pass, using the atomic state writer. The migration records the old/new audit hashes while preserving the run ID, completed artifacts, pilot set and one-time resume behavior. Completed, frozen, finalizing, non-resume, manifest-existing and other-identity-change cases remain fail-closed.
- The current audit binding requires an independent accepted report, exact current runner SHA-256, exact reviewed implementation commit/ancestor with matching runner blob, report-only post-review Git changes, and the fixed preparation-contract identity. The FT05A entry point applies the exact canonical output/artifact namespace checks before preflight, source loading, W_Original loading, ownership or output writes.
- Existing FT05A controls remain intact: technical-only columns and allowlisted roots, outcome/clinical path and column denylist, frozen A boundary and no B K-means fit, unchanged A/W03 PyRadiomics settings, exact candidate/order hashes, accepted W_Original path/hash/order/reuse binding, source uniqueness, structural absence and small-ROI states, exclusive ownership, pilot streaming/resume, atomic finalization/recovery, provenance and formal-directory isolation.

## Blocking findings

None.

## Nonblocking finding

One synthetic directory-symlink test was skipped because the Windows account lacks symbolic-link privilege. The exact lexical namespace gate, resolved-path/reparse checks, non-privileged alias coverage, and junction/reparse coverage remain passing; this limitation does not weaken the production fail-closed path.

## Synthetic and regression validation

All Python execution used `tools/run_t2_radiomics.ps1` with the locked `t2_radiomics` environment.

```text
tools/run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_ft05a_runner','tests.test_ft04_runner','tests.test_ft03_runner','tests.test_ft02_runner','tests.test_w07_outer_splits')
107 tests run; 107 passed; 0 failed; 1 skipped; exit code 0

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft05a_runner.py','static-validate')
pass: true; B_kmeans_fit: false; outcome_accessed: false; whole_tumor_reextraction: false; formal_directory_mixing: false

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft04_runner.py','validate')
status: VALID; FT04 lock identity: 10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e
```

The FT05A synthetic suite includes adversarial unselected W_Original tampering, malformed pilot completion, atomic migration failure, identity-field mutation, completed/frozen/non-resume rejection, migration artifact reconciliation, pilot resume without recomputation, exact output-root and canonical artifact alias rejection, source/manifest tampering, duplicate mappings, structural absence and small-ROI handling, ownership contention, finalization recovery/tampering, outcome isolation, formal-directory rejection and technical-manifest validation.

No real B image, ROI, W_Original value, technical feature, clinical/outcome source, patient-level FT05A output or later FT05 module was read, generated or changed during this review.

## Downstream authorization

The next Worker is authorized to resume only the same existing one-time FT05A run identity after the normal runtime preconditions are satisfied. This audit authorizes no FT05B outcome unlock and no FT06 execution.
