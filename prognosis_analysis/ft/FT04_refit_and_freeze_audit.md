# FT04 Refit and Freeze Audit

## Status

`COMPLETE`

Stage: `FT04` — Full_A Final Refit & Freeze.
Analysis label: `exploratory_fullA_habitat_non_nested_validation`.
The run is A-only and leaves B technical assets, B outcomes, and formal W08/L9 locks unchanged.

## Frozen models

| Model | Population | Eligible n | Events | State SHA-256 | Cutoff rule |
|---|---|---:|---:|---|---|
| M0 | main | 393 | 89 | `6a4284bec1388bab893076eb54096ec9aaad59126ad419c1ec107985b9a413da` | `median_full_A_fitted_linear_predictor` |
| M1 | main | 393 | 89 | `2d4eb86a95f2c5f768012d48db52fd1eb584ecfec3b4eca214d19cdd64c55710` | `median_full_A_fitted_linear_predictor` |
| M2 | main | 393 | 89 | `fa98601cb14d51d7fd5ebc648e185c24f1aac5751dae7818768ce1699ee02e7c` | `median_full_A_fitted_linear_predictor` |
| M3L | R_low | 391 | 88 | `ae2112008a9e5cd2715fd4da12de26ee0f3422f5f01284423355fea29e138b21` | `median_full_A_fitted_linear_predictor` |
| M3H | R_high | 356 | 84 | `add312861f2fc61c581cd836e99c489961e7def9324fe098c94f019ae46a544f` | `median_full_A_fitted_linear_predictor` |
| M4 | dual_radiomics | 354 | 83 | `5ba85f247cf97d4b94ddd796e5134cd55afb0b902335674ee98516b78768a649` | `median_full_A_fitted_linear_predictor` |
| M5 | W_Original | 393 | 89 | `d58e97f55d1dfb9e7cec08ab4d45f1b1cb1bb845f010dbb95587ed79b09f3ea3` | `median_full_A_fitted_linear_predictor` |

Penalized models use `alpha=1`, 20 candidates, and ordinary training-only inner five-fold selection on the complete eligible full-A fitting population. Unpenalized models retain the accepted Cox specification.
All final states include ordered raw predictors, transformed feature names, preprocessing parameters, coefficients, baseline survival, exact prediction formulas, and deterministic non-optimized cutoffs.

## Provenance and boundaries

- Frozen habitat: `K=2`, `n_init=100`, `R_low=49` (candidate hash `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0`), `R_high=10` (candidate hash `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`), `W_Original=107` (order hash `1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f`).
- W_Original binding: reuse-only accepted existing asset `feature_extract/output/features_v2/muscle_f0.25/features_original.csv` with asset SHA-256 `462201e66d8e8989063f02f1d7f63865a23335883c582707dc7713f40d3e9649`; feature count `107`, order SHA-256 `1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f`, and re-extraction `false`.
- Frozen split binding: W07 repeat 1, five folds, seed `12345`; split regeneration is `false`.
- Endpoint: DFS; prediction horizons: 36 and 60 months.
- B state: locked; FT05A, FT05B, and FT06: not executed.
- Formal lock: `prognosis_analysis/model_freeze_lock.json` unchanged.
- Immutable implementation/source commit: `8bc0bb0c3fee67b1c81c35cef1aec30ca22a812d`; it contains the first-round reviewed FT04 runner and lock version. It is distinct from the remediation attestation.
- Attestation parent commit: `31e15f4b1aa22677c894184e44b7d50dba3d5ccd`; it contains the pre-remediation FT04 files and is not claimed to contain the remediation.
- The final local attestation commit is the child that records the remediation lock and this audit. Its hash is intentionally not embedded in the lock, avoiding a self-referential commit claim.
- Current FT04 runner SHA-256: `27fa5aeae623ebce764b0ef511bc8a608cf97abc19a2c356e7d5a59027793b18`; serialized FT04 lock file SHA-256: `23056cd5c22acca3800c7ea4df00eead18d2b4c90cdcba6e05ca0ce67e70cc90` (canonical attestation: `prognosis_analysis/ft/FT04_lock_sha256.json`); lock payload identity SHA-256: `9ae1735aa0bbbbff56d4e309e810be7c0f120a497dd401c9ec851b247e45f5c8`.
- PyRadiomics configuration/provenance is bound to the accepted A/W03 files by SHA-256 in `provenance.pyradiomics`.
- B prediction is fail-closed on the canonical `FT05_B_feature_manifest.json`, an accepted independent FT04 review bound to the current lock/code, and the complete FT05A table/block/provenance/review contract.
- B outcome evaluation additionally requires the canonical `FT_B_unlock.json`; prediction-only loading does not read or require B outcomes.
- Runtime wrapper: `tools/run_t2_radiomics.ps1`; pre-run long-task estimate: `180` minutes based on accepted FT03 runtime evidence; no periodic worker polling.

## Validation

- The seven existing FT04 model states reload in `t2_radiomics` and reproduce their frozen risk/survival outputs; their hashes are preserved.
- `tests/test_ft04_runner.py`: 22 synthetic/contract tests passed, including canonical-path, Git-binding, review-gate, complete-manifest, hash/provenance, W_Original binding, outcome-unlock, tamper, and formal-lock negative coverage.
- FT04 plus accepted FT03/FT02/W07 wrapper regression suite: 63 tests passed.

## Deliverables

- `prognosis_analysis/ft/FT_model_freeze_lock.json`
- `prognosis_analysis/ft/FT04_lock_sha256.json`
- ignored local FT04 model states under `prognosis_analysis/output/ft_20260910_01a08bf3/FT04/model_states/`
- `prognosis_analysis/ft/ft04_runner.py`
