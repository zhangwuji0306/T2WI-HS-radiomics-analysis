# FT04 Remediation Review — Second Round

## Disposition

`not accepted for downstream use`

## Evidence

- The FT04 lock validates successfully through `tools/run_t2_radiomics.ps1`; all seven ignored local FT04 model states exist, have distinct hashes matching the pre-remediation states, reload successfully in `t2_radiomics`, and reproduce finite risk and 36/60-month survival outputs.
- The canonical candidate-list hashes are present and enforced: R_low `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0`; R_high `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`.
- The implementation-source and attestation-parent commits resolve, are ancestors of the current branch, and contain their declared FT04 paths. The current runner hash and lock identity validate. No FT05A/FT05B artifact, B outcome access, or formal model lock was created; the pre-existing FT01 working-tree indication and orchestration control directory remain untouched.

## Wrapper tests

```text
tools/run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_ft04_runner','tests.test_ft03_runner','tests.test_ft02_runner','tests.test_w07_outer_splits')
56 tests run; 56 passed; 0 failed; exit code 0; 168.068 s

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft04_runner.py','validate')
status: VALID; exit code 0
```

## Closure of original blockers

| Original blocker | Closure status |
|---|---|
| Canonical `FT_B_unlock.json` path | Closed; canonical path is enforced and the prior filename is rejected. |
| Incorrect FT04 Git commit binding | Closed for the original incorrect binding; the role split is non-circular and the referenced commits resolve with declared paths. |
| Missing accepted-review and complete FT05A prerequisite gate | Partially closed; accepted-review, canonical-manifest, completeness, hash, uniqueness, provenance, and negative-path checks are present, but the residual blocking findings below prevent downstream use. |
| Missing R_low/R_high candidate-list hashes | Closed; both hashes are frozen and checked in the FT04 lock and manifest validation. |

## Blocking findings

1. `predict_b_from_frozen` validates the manifest table but does not bind the caller-supplied `feature_frame` to that table's canonical path, hash, columns, rows, or values. With a valid synthetic manifest and accepted synthetic review gate, a separate forged eight-row predictor frame was accepted and predictions were returned.
2. The FT05A `W_Original` asset is only checked against a self-reported manifest hash. Its path and hash are not bound to the accepted existing W_Original asset recorded by FT01/FT04. With the valid synthetic contract fixture, an arbitrary synthetic W_Original asset was accepted for M5 prediction.
3. The Git binding does not record or validate an exact SHA-256 for the current serialized FT04 lock file. A lock copy with an injected incorrect lock-file SHA-256 remained `VALID`, demonstrating that the declared current lock content hash is not enforced; only the payload identity is checked.

## Nonblocking findings

None.

## Downstream decision

FT05A and all later FT modules remain unauthorized. The current FT04 remediation is not accepted for downstream use until the three blocking findings are resolved and independently reviewed.
