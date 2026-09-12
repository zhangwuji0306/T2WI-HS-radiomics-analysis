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

- Frozen habitat: `K=2`, `n_init=100`, `R_low=49`, `R_high=10`, `W_Original=107`.
- Frozen split binding: W07 repeat 1, five folds, seed `12345`; split regeneration is `false`.
- Endpoint: DFS; prediction horizons: 36 and 60 months.
- B state: locked; FT05A, FT05B, and FT06: not executed.
- Formal lock: `prognosis_analysis/model_freeze_lock.json` unchanged.
- Runtime wrapper: `tools/run_t2_radiomics.ps1`; pre-run long-task estimate: `180` minutes based on accepted FT03 runtime evidence; no periodic worker polling.

## Validation

- FT04 serialization, replay, fail-closed prerequisite, tamper, boundary, and formal-lock tests: 6 passed.
- Direct FT04 plus accepted FT03/FT02/W07 regression suite through the wrapper: 47 passed.
- All seven serialized states reload in `t2_radiomics` and reproduce risk/survival outputs from their frozen preprocessing and baseline-survival state.

## Deliverables

- `prognosis_analysis/ft/FT_model_freeze_lock.json`
- ignored local FT04 model states under `prognosis_analysis/output/ft_20260910_01a08bf3/FT04/model_states/`
- `prognosis_analysis/ft/ft04_runner.py`
