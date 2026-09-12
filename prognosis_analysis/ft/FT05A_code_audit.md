# FT05A Independent Pre-run Code Audit — Round 13

Independent review: true

Reviewed FT05A implementation commit: `db92fb4278572a8baa9133564031fbcccc36b941`

FT05A runner SHA-256: `edf47786083f0ed075e367847b54c31686aa6311697ea10ed7bc67f21546e096`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

FT05A post-generation change scope: canonical audit-namespace allowlist only

## Verdict

Verdict: PASS

## Scope and evidence

- The current FT05A runner and synthetic regression tests were independently reviewed at the implementation commit above.
- Existing `TECHNICAL_COMPLETE_PENDING_REVIEW` state is restored without processor calls. The original run identity, generation runner hash, generation code-audit hash, cohort binding, W_Original binding, row schema, case-completion evidence, and factual technical-audit binding remain unchanged. Manifest and technical table finalization is reached only after an accepted independent technical audit and uses staged, hash-validated atomic promotion.
- Pending-state migration is fail-closed on missing or altered technical-audit files, altered generation bindings, altered case artifacts, incomplete case evidence, conflicting manifests, missing or non-allowlisted post-generation scope, and any post-review Git path outside the two canonical audit reports.
- The code-audit parser binds the reviewed runner blob to the reviewed implementation commit, the current runner SHA-256, the preparation contract identity, and the canonical post-review audit namespace. The accepted canonical code audit and the canonical factual technical audit are the only post-review audit paths admitted.
- Static validation and source inspection preserve the A-full frozen boundary, W_Original reuse-only provenance, W03/PyRadiomics bindings, outcome-blind technical processing, explicit structural states, and the prohibition on B K-means fitting, outcome access, whole-tumour or repeat extraction, and formal-directory mixing.
- FT04 remains valid and retains the accepted lock identity and frozen W_Original/PyRadiomics provenance.

## Synthetic and regression validation

All Python execution used `tools/run_t2_radiomics.ps1` with the locked `t2_radiomics` environment from `environment.yml`.

```text
tests.test_ft05a_runner: 50 tests run; 49 passed; 0 failed; 1 skipped; exit code 0
tests.test_ft04_runner + tests.test_ft03_runner + tests.test_ft02_runner + tests.test_w07_outer_splits: 65 tests run; 65 passed; 0 failed; exit code 0
ft05a_runner.py static-validate: pass=true; B_kmeans_fit=false; outcome_accessed=false; whole_tumor_reextraction=false; formal_directory_mixing=false
ft04_runner.py validate: status=VALID; FT04 lock identity retained
locked environment check: matches_locked_spec=true; mismatches={}
```

No real B image, ROI, W_Original asset, technical feature, clinical/outcome source, patient-level FT05A output, FT05B artifact, or FT06 artifact was read, generated, or changed during this review.

## Downstream authorization

The next Worker is authorized to run or resume only the same one-time FT05A technical generation under the accepted FT04 lock and this accepted independent code audit. After technical completion it must leave the factual technical audit in `generated_pending_review` and stop for an independent technical review. This authorization does not unlock B outcomes, FT05B, or FT06.
