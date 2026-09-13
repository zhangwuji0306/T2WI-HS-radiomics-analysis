# FT03 A Validation Report

## Status

`COMPLETE`

Analysis label: `exploratory_fullA_habitat_non_nested_validation`.
Performance label: `non_nested_exploratory_estimate`.
The analysis is A-only, uses the frozen W07 repeat-1 ordinary 5-fold split, and does not read B data or write formal W08/L9 outputs.

## Model validation

| Model | Eligible n | Events | Uno C | Harrell C | AUC 3 y | AUC 5 y | Brier 3 y | Brier 5 y |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M0 | 393 | 89 | 0.6640 | 0.6159 | 0.6561 | 0.6824 | 0.1411 | 0.1803 |
| M1 | 393 | 89 | 0.6619 | 0.6164 | 0.6547 | 0.6776 | 0.1413 | 0.1805 |
| M2 | 393 | 89 | 0.6398 | 0.6091 | 0.6479 | 0.6570 | 0.1457 | 0.1842 |
| M3L | 391 | 88 | 0.6485 | 0.6319 | 0.6489 | 0.6746 | 0.1379 | 0.1753 |
| M3H | 356 | 84 | 0.6567 | 0.6205 | 0.6601 | 0.6910 | 0.1424 | 0.1800 |
| M4 | 354 | 83 | 0.6395 | 0.6165 | 0.6523 | 0.6626 | 0.1457 | 0.1858 |
| M5 | 393 | 89 | 0.6597 | 0.6461 | 0.6610 | 0.6852 | 0.1363 | 0.1747 |

Bootstrap confidence intervals use 200 deterministic case resamples, matching the accepted FT02 bootstrap hook default. Harrell C is pooled over held-out predictions; Uno C, AUC and Brier are validation-fold-size-weighted means using training-fold censoring weights.
Calibration and DCA are recorded at 3 and 5 years; KM curves are stored in the local FT03 output namespace.

## Paired comparisons

| Comparison | Population | Common n | Harrell C left | Harrell C right | Δ right − left |
|---|---|---:|---:|---:|---:|
| M0_vs_M1 | main | 393 | 0.6159 | 0.6164 | 0.0005 |
| M0_vs_M2 | main | 393 | 0.6159 | 0.6091 | -0.0068 |
| M2_vs_M3L | R_low | 391 | 0.6083 | 0.6319 | 0.0236 |
| M2_vs_M3H | R_high | 356 | 0.6258 | 0.6205 | -0.0053 |
| M2_vs_M4 | dual_radiomics | 354 | 0.6296 | 0.6165 | -0.0131 |
| M3L_vs_M3H | dual_radiomics | 354 | 0.6320 | 0.6175 | -0.0145 |
| M4_vs_M5 | dual_radiomics_and_W_Original | 354 | 0.6165 | 0.6030 | -0.0135 |

All seven comparisons use one common eligible population and identical frozen fold assignments for both models. AUC and Brier paired values are included in `FT03_A_validation.json`.

## Provenance and validation evidence

- Frozen repeat-1 seed: `12345`; fold count: `5`; split regeneration: `false`.
- M0–M5 completed with Cox fitting; high-dimensional models use alpha=1 and training-only inner 5-fold lambda selection.
- R_low=49, R_high=10 and W_Original=107 are bound to their frozen candidate/order hashes.
- Cross-validated prediction coverage, held-out-fold checks, endpoint/horizon checks, calibration, KM, DCA, bootstrap and paired-population checks passed.
- B data read: `false`; formal output written: `false`; formal model freeze lock written: `false`.

## Runtime

The production run and all Python probes/tests were executed through `tools/run_t2_radiomics.ps1` in the locked `t2_radiomics` environment. Runtime and the pre-run small-sample estimate are recorded in `provenance.runtime` in the aggregate JSON.
