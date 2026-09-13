# Quick check: three-year DFS AUC

Generated: 2026-08-28 12:54:26

Full-A Model 1/2/3 were fitted after fold-local imputation, variance filtering, correlation filtering, scaling, and inner 5-fold lambda.1se selection. B outcomes were not used in these steps.

## Cohort counts

| Dataset | N | Total events | Events by 36 months | At risk at 36 months |
|---|---:|---:|---:|---:|
| A | 530 | 121 | 76 | 430 |
| B | 163 | 42 | 23 | 130 |

## Point estimates

| Dataset | Model | 3-year DFS AUC | N | Total events | Events by 36 months |
|---|---|---:|---:|---:|---:|
| A_apparent | model1 | 0.7241 | 530 | 121 | 76 |
| A_apparent | model2 | 0.6748 | 530 | 121 | 76 |
| A_apparent | model3 | 0.7242 | 530 | 121 | 76 |
| A_OOF | model1 | 0.6693 | 530 | 121 | 76 |
| A_OOF | model2 | 0.5584 | 530 | 121 | 76 |
| A_OOF | model3 | 0.6778 | 530 | 121 | 76 |
| B_external | model1 | 0.6823 | 163 | 42 | 23 |
| B_external | model2 | 0.5259 | 163 | 42 | 23 |
| B_external | model3 | 0.6823 | 163 | 42 | 23 |

## Model 3 minus Model 1

| A_OOF | 0.0085 |
| A_apparent | 0.0001 |
| B_external | 0.0000 |

## Predefined operational flags

- model1 apparent minus OOF AUC > 0.05
- model2 apparent minus OOF AUC > 0.05
- model2 apparent minus OOF AUC > 0.10
- B_external Model 3 minus Model 1 AUC <= 0

## Upstream QC status

- Upstream QC contains 1 ERROR record(s); resolve before formal analysis.
- The one-repeat nested-CV run emitted 13 R warnings; predictions were complete, but the warning details should be captured and reviewed before formal resampling.

These are point estimates for workflow triage only; no bootstrap confidence intervals, calibration curves, decision-curve analysis, or B-informed tuning were performed.
