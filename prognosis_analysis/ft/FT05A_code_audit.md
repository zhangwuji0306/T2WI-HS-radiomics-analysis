# FT05A Independent Pre-run Code Audit — Round 8

Independent review: true

Reviewed FT05A implementation commit: `ab77eb3085b3eac4c899bfd116c360d8fb152ab5`

FT05A runner SHA-256: `32d133122f6c2714177705a0283374e2d38167ae4b45ace1dbae95a7d3ddbd54`

FT05A preparation contract identity: `FT05A_code_prep_contract_v1`

## Verdict

Verdict: FAIL

## Scope and evidence

- The reviewed commit is limited to `prognosis_analysis/ft/ft05a_runner.py` and `tests/test_ft05a_runner.py`. No real B image, ROI, W_Original value, outcome, clinical/prognostic data, patient-level output, or real FT05A run artifact was accessed or changed during this review.
- The pilot and full W_Original paths now call the same physical-record CSV parser and the same `_canonical_w_original_value` conversion. Accepted B/R1 rows are filtered identically, while malformed rows, nonfinite values, duplicate accepted rows, missing selected rows, duplicate headers, and incomplete row schemas fail closed. The canonical feature order is preserved through `W_ORIGINAL_FEATURE_NAMES` and the row hash uses the same ordered representation.
- The focused synthetic suite passed: `36` tests, `1` platform-permission skip, `0` failures, through `tools/run_t2_radiomics.ps1` in `t2_radiomics`.
- The accepted-state synthetic suite passed: `101` tests, `1` platform-permission skip, `0` failures, through `tools/run_t2_radiomics.ps1` in `t2_radiomics`.
- Static validation returned `pass: true` with no findings for B clustering fit, outcome access, whole-tumour re-extraction, or formal-directory mixing.
- FT04 lock validation returned `status: VALID` with lock identity `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`.
- The existing path, audit binding, frozen A boundary, PyRadiomics, W_Original trust, source uniqueness, ownership, finalization, technical-only schema, outcome blindness, and no-B-fitting controls remain present in the reviewed implementation. The new synthetic equivalence and unchanged-contract resume tests pass.

## Blocking finding

The production resume path cannot continue the existing pilot run after this reviewed code remediation. `_initial_run_state` includes `code_audit_sha256` in `identity_payload`, and `_load_or_create_state` requires both the stored `run_identity_sha256` and the complete stored `identity_payload` to equal newly computed values. The mandatory canonical audit report must be updated to bind commit `ab77eb3` and the new runner hash, which changes `code_audit_sha256`; therefore the pre-remediation pilot state fails the run-identity equality check and is rejected as a conflicting run before completed-case reconciliation. The added resume test keeps the mocked audit identity unchanged and does not cover this code-change transition.

Completed pilot cases must remain immutable and must not be recomputed or overwritten. Until the continuation path is remediated and independently reviewed, the existing run cannot be safely resumed under the current implementation.

## FT05A-only remediation plan

Add a fail-closed reviewed-remediation continuation path that accepts the existing logical run only when its run ID, cohort, frozen FT04 lock, accepted W_Original binding, canonical output namespace, and every completed case artifact/source/row hash match. Bind the current reviewed implementation and audit atomically for continuation without recomputing or overwriting completed cases. Add a synthetic regression for a pre-remediation pilot state resumed under the current parser, plus rejection tests for changed cohort/lock/W_Original bindings and tampered completed artifacts. No real B processing or later FT module is authorized while this finding remains open.

## Downstream decision

No downstream authorization. The same-run FT05A resume is not authorized, and this audit does not authorize FT05B or FT06.
