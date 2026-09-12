# FT05A Independent Pre-run Code Audit — Round 11

Independent review: true

Reviewed FT05A implementation commit: `7777498aa6135fb635814e2f86719bcdccae9384`

FT05A runner SHA-256: `a3c6e6b9f3b2598b36b99d944efce97b838191a922e15c3560904709425f9aa3`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: PASS

## Scope and evidence

- Reviewed the FT scheme, the current FT05A runner and tests, the accepted FT04 lock/review bindings, the current Git diff, and the canonical FT05A audit contract.
- The runner treats `FT05A_code_audit.md` as the accepted independent pre-run code audit. It emits `FT05A_B_technical_generation_audit.md` only after all technical case artifacts and completion hashes are present, with `Status: generated_pending_review`, `Independent review: false`, and `Verdict: PENDING_REVIEW`.
- The generated factual audit is bound to the run identity, cohort, completed-case evidence, FT04 lock, current code-audit hash, exact runner hash, accepted W_Original asset, frozen W_Original order, and canonical row schema. The same canonical report must be independently changed to an accepted PASS/PASS_WITH_FINDINGS review before manifest finalization.
- `TECHNICAL_COMPLETE_PENDING_REVIEW` is a complete-case terminal hold for the technical generation stage. The manifest is not created in this state; resumption requires the same run identity and canonical audit path, validates completed case artifacts, and skips their processors. Code-identity migration is rejected after this hold.
- Accepted technical-audit finalization rechecks identity/provenance/safety fields and the exact current runner hash, then validates the staged table and manifest before atomic installation. Interrupted finalization and corrupted staged/installed bytes fail closed; case failures persist `FAILED` without a frozen manifest.
- Existing FT05A constraints remain enforced: the frozen full-A habitat boundary, direct projection without B K-means, exact A/W03 PyRadiomics settings, reuse-only W_Original, no B outcome access, no whole-tumor re-extraction, no duplicate extraction, formal-output isolation, technical namespace allowlisting, canonical artifacts, exclusive ownership, and one-time resume semantics.
- FT04's downstream validator requires the canonical frozen manifest, complete technical table, accepted independent technical/code audits, frozen provenance, and all outcome-blind generation flags. No FT05B/FT06 implementation or outcome-unlock artifact was accessed in this review.

## Findings

None blocking or nonblocking.

## Synthetic and regression validation

All Python execution used `tools/run_t2_radiomics.ps1` with the locked `t2_radiomics` environment.

```text
tools/run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_ft05a_runner','tests.test_ft04_runner','tests.test_ft03_runner','tests.test_ft02_runner','tests.test_w07_outer_splits')
109 tests run; 109 passed; 0 failed; 1 skipped; exit code 0

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft05a_runner.py','static-validate')
pass: true; B_kmeans_fit: false; outcome_accessed: false; whole_tumor_reextraction: false; formal_directory_mixing: false

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft04_runner.py','validate')
status: VALID; FT04 lock identity: 10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e
```

The FT05A synthetic suite covers factual pending-audit emission, absence of a premature manifest, accepted-review resume without case recomputation, audit-field binding, run-state transitions, identity migration, atomic state writes, finalization recovery/tamper rejection, W_Original reuse, namespace isolation, outcome/path denial, and failure closure. The single skipped check is the Windows symbolic-link privilege-dependent case; non-privileged alias and junction coverage passed.

No real B image, ROI, W_Original value, technical feature, clinical/outcome source, patient-level FT05A output, FT05B artifact, or FT06 artifact was read, generated, or changed during this review.

## Downstream authorization

The next Worker is authorized to run or resume only the same one-time FT05A technical run under the accepted FT04 lock and this accepted pre-run code audit. After technical completion it must leave the factual audit in `generated_pending_review` and stop for an independent technical review. This authorization does not unlock B outcome access, FT05B, or FT06.
