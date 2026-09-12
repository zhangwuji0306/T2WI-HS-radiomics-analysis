# FT04 Fourth-Round Independent Review

## Disposition

`accepted for downstream use`

Independent review: true

FT04 lock identity SHA-256: `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e`

FT04 lock file SHA-256: `bb0c00b49b68cc31eb3899a9099ca8330551a7c2afd0ff3f849abc091a80c2d2`

FT04 lock digest file SHA-256: `877800e482b531b3073e290c4bcbf7270d19904d9ff939726b95fca3b69ff30a`

FT04 runner SHA-256: `f4ca2c3fe2cfc7128a9894888ff5e7a2fd1bb2a6d6794af26d0a222aba4856b3`

FT04 reviewed remediation commit: `7e509690789d52df78573f8da89606ce1da43252`

## Evidence

- The remediation through commit `f838ff87bd2d0acf0d77cbf02e1f496acc680118` is scoped to the FT04 lock, digest, audit, runner, and tests. The current runner requires the exact canonical digest-file SHA-256 marker and pins the reviewed-remediation marker to `7e509690789d52df78573f8da89606ce1da43252`; the production validator also verifies commit resolution, ancestry, and declared FT04 paths. Regression coverage rejects `624789feac69d002587d6e79b4ff0b7810d66055`, another valid ancestor, missing or malformed markers, and incorrect hashes.
- The lock identity, exact serialized lock bytes, canonical digest bytes, and current runner bytes independently match the markers above. The lock, digest, source records, Git bindings, environment binding, accepted W_Original asset, R_low/R_high candidate hashes, model-input hashes, and canonical FT05 paths validate together.
- All seven model-state files retain the hashes and scientific contents of the original FT04 freeze, match the lock, remain distinct, and reload under `t2_radiomics`. Their frozen populations, model blocks, preprocessing, Cox specifications, lambda records, coefficients, baseline survival, 36/60-month prediction formulas, and deterministic non-optimized cutoffs remain consistent.
- The downstream boundary loads the canonical FT05A feature table and rejects a distinct caller frame, altered rows, columns, order, values, hashes, duplicates, alternate paths, incomplete model inputs, nonfinite values, inconsistent provenance, noncanonical W_Original assets, repeat extraction, B K-means fitting, outcome access, and formal-directory mixing. Outcome evaluation additionally requires the canonical `FT_B_unlock.json`.
- No real FT05A, FT05B, or FT06 artifact exists. B remains locked, no B source/data/outcome was read, and the formal model lock remains absent. The reviewed tracked changes contain no patient identifiers, patient-level values, private paths, credentials, unexpected large files, unrelated changes, or formal-output contamination.

## Wrapper results

```text
tools/run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_ft04_runner','tests.test_ft03_runner','tests.test_ft02_runner','tests.test_w07_outer_splits')
65 tests run; 65 passed; 0 failed; exit code 0; 216.159 s

tools/run_t2_radiomics.ps1 -PythonArguments @('.\prognosis_analysis\ft\ft04_runner.py','validate')
status: VALID; exit code 0
```

The canonical review passed the production accepted-review validator through the locked wrapper without requiring or reading any B artifact.

## Closure of prior blockers

| Prior blocker | Fourth-round status |
|---|---|
| Canonical `FT_B_unlock.json` path | Closed. |
| Truthful, specific FT04 Git binding | Closed. |
| Accepted-review and complete FT05A prerequisite gate | Closed. |
| R_low/R_high candidate-list hashes | Closed. |
| Canonical feature-table and caller-frame identity | Closed. |
| Accepted W_Original asset binding | Closed. |
| Exact serialized lock-byte and canonical digest binding | Closed. |
| Exact canonical digest-file SHA-256 review marker | Closed. |
| Exact reviewed-remediation commit marker | Closed. |

## Findings and downstream decision

Blocking findings: none.

Nonblocking findings: none.

FT04 is accepted for downstream use. This decision authorizes only the next contract-defined gate and does not execute or review FT05A or any later module.
