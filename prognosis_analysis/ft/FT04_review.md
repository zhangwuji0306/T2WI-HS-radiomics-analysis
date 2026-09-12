# FT04 Third-Round Independent Review

## Disposition

`not accepted for downstream use`

## Evidence

- The current FT04 lock validates through the locked wrapper. The lock identity is `2654ba560d2aac45241d8cbe6811fd7a31e78465a826551d058aee2aff9dcf37`; the exact serialized lock SHA-256 is `1ebf3b3a712bcd46b9e82c040ced0413a761f782991f489c1a30fd2ced160c03`; the canonical digest-file SHA-256 is `ba0e98587989bea14e08a182b0f9f6b6697dec1d395c9f7e08e260f136419c98`; and the current FT04 runner SHA-256 is `f83dcd2c6773fd69561d20b997ce1d74365b4c6e16da778d2c30830535a80f9a`.
- All seven FT04 model states exist, have distinct hashes matching the current lock and the original FT04 state summaries, reload under `t2_radiomics`, and preserve the checked model-input, population, predictor-block, cutoff, and scientific-fit bindings.
- The lock freezes the accepted R_low/R_high candidate hashes, W_Original count/order, the accepted existing W_Original path and asset SHA-256, reuse-only status, A-only full_A scope, and B/formal-lock separation. No FT05A/FT05B/FT06 artifact file was created; B source/outcome/data was not read; and the formal model lock remains absent.
- Git provenance is non-circular at the implementation/source and attestation-parent layers. The implementation/source commit is `8bc0bb0c3fee67b1c81c35cef1aec30ca22a812d`; the current lock records `624789feac69d002587d6e79b4ff0b7810d66055` as its attestation parent; and the reviewed second-remediation commit is `7e509690789d52df78573f8da89606ce1da43252`. These commits resolve, are ancestors of the current branch, and contain the declared FT04 paths.
- The accepted FT04 review gate is not yet strict enough for downstream authorization. A wrapper-run synthetic fixture accepted a review naming the valid ancestor `624789feac69d002587d6e79b4ff0b7810d66055` instead of the required reviewed remediation commit `7e509690789d52df78573f8da89606ce1da43252`. The same accepted fixture contains no canonical digest-file SHA-256 marker, yet prediction succeeded.

## Wrapper tests

```text
tools/run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_ft04_runner','tests.test_ft03_runner','tests.test_ft02_runner','tests.test_w07_outer_splits')
64 tests run; 64 passed; 0 failed; exit code 0; 212.069 s

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft04_runner.py','validate')
status: VALID; exit code 0
```

## Closure of prior blockers

| Prior blocker | Third-round status |
|---|---|
| Canonical `FT_B_unlock.json` path | Closed; the canonical path is frozen and alternate paths are rejected. |
| Incorrect/non-specific FT04 Git binding | Partially closed; the source/attestation role split is valid, but the downstream review gate does not require the exact reviewed remediation commit. |
| Missing accepted-review and complete FT05A prerequisite gate | Partially closed; the accepted-review, canonical-manifest, table, model-input, uniqueness, provenance, W_Original, generation, and FT05A-review checks are present, but the two residual review-gate defects below remain blocking. |
| Missing R_low/R_high candidate-list hashes | Closed; both canonical hashes are frozen and validated. |
| Caller-frame/table identity binding | Closed; the production path loads the canonical table and rejects mismatched caller frames, rows, columns, values, and hashes. |
| W_Original accepted-asset binding | Closed; path, exact asset SHA-256, 107-feature order hash, and reuse-only state are frozen and required. |
| Exact serialized FT04 lock-byte binding | Closed at lock validation; the canonical digest rejects mutated lock bytes and incorrect digest content. |

## Blocking findings

1. The downstream accepted-review validator does not require the exact canonical digest-file SHA-256. `_validate_ft04_review` verifies the lock identity, serialized lock SHA-256, and current runner SHA-256, but it does not verify a review marker for the SHA-256 of `FT04_lock_sha256.json`. The existing positive synthetic downstream fixture omits that marker and is accepted. This leaves the required review binding incomplete.
2. The downstream accepted-review validator does not pin the reviewed remediation commit to `7e509690789d52df78573f8da89606ce1da43252`. It accepts any resolving ancestor that contains the declared FT04 paths; the wrapper-run synthetic probe substituted the valid `624789feac69d002587d6e79b4ff0b7810d66055` and prediction still succeeded. The required reviewed-commit binding is therefore not fail-closed.

## Nonblocking findings

None.

## Downstream decision

FT05A and all later FT modules remain unauthorized. FT04 is not accepted for downstream use until the two blocking review-gate findings are corrected and independently reviewed.
