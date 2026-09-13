# FT06 B External Validation Report

## Status

`COMPLETE`

Analysis label: `exploratory_fullA_habitat_non_nested_validation`.
Performance label: `external_B_frozen_prediction_evaluation`.
The B analysis used 163 authorized cases and applied the seven serialized FT04 states without fitting or tuning.
Uno C-index, time-dependent AUC and Brier use the full-A censoring reference; Harrell C is computed directly on B.

## Model validation

| Model | Eligible n | Events | Uno C | Harrell C | AUC 3 y | AUC 5 y | Brier 3 y | Brier 5 y |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M0 | 163 | 42 | 0.6698 | 0.6523 | 0.6173 | 0.6673 | 0.1392 | 0.1862 |
| M1 | 163 | 42 | 0.6719 | 0.6537 | 0.6197 | 0.6676 | 0.1394 | 0.1858 |
| M2 | 163 | 42 | 0.6733 | 0.6513 | 0.6106 | 0.6643 | 0.1396 | 0.1882 |
| M3L | 162 | 42 | 0.6170 | 0.6044 | 0.5722 | 0.6359 | 0.1437 | 0.2025 |
| M3H | 131 | 35 | 0.6705 | 0.6807 | 0.6484 | 0.7081 | 0.1349 | 0.1788 |
| M4 | 130 | 35 | 0.6555 | 0.6446 | 0.6412 | 0.6631 | 0.1374 | 0.1929 |
| M5 | 163 | 42 | 0.6365 | 0.6233 | 0.6382 | 0.6435 | 0.1377 | 0.1936 |

Patient-level bootstrap confidence intervals use 200 deterministic case resamples. Calibration, KM and DCA are retained for both 36- and 60-month horizons.

## Paired comparisons

| Comparison | Population | Common n | Harrell C left | Harrell C right | Δ right − left |
|---|---|---:|---:|---:|---:|
| M0_vs_M1 | main | 163 | 0.6523 | 0.6537 | 0.0014 |
| M0_vs_M2 | main | 163 | 0.6523 | 0.6513 | -0.0010 |
| M2_vs_M3L | R_low | 162 | 0.6492 | 0.6044 | -0.0448 |
| M2_vs_M3H | R_high | 131 | 0.6636 | 0.6807 | 0.0171 |
| M2_vs_M4 | dual_radiomics | 130 | 0.6612 | 0.6446 | -0.0167 |
| M3L_vs_M3H | dual_radiomics | 130 | 0.6161 | 0.6796 | 0.0635 |
| M4_vs_M5 | dual_radiomics_and_W_Original | 130 | 0.6446 | 0.6279 | -0.0167 |

All seven comparisons use a common B eligible population and identical patient alignment. Paired AUC and Brier estimates and bootstrap intervals are included in the JSON artifact.

## Calibration, KM and DCA

Calibration and DCA are present at 3 and 5 years for every model; KM data are present for every model in the ignored FT06 output namespace.

## Gate and safety evidence

- FT_B_unlock, FT04 lock/review, FT05A manifest/table/audit hashes and FT05B receipt were validated before the B predictor/outcome read.
- The B read used only `影像号`, the nine frozen clinical predictor columns, `DFS_time` and `DFS_event`, with a 163-ID allow-list.
- No B fit, lambda tuning, feature selection, cutoff tuning, habitat refit, radiomics re-extraction, or B→A feedback occurred.
- B technical/clinical joining was one-to-one with 163 unique cases and no duplicate or mismatched IDs.

## Final disposition

The single FT label is assigned by the pre-specified rule in the FT scheme and is recorded in `FT06_final_summary.md`.
