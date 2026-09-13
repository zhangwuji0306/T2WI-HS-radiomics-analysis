# FT00–FT06 Final Uniform Audit

## Final decision

`accepted with non-blocking findings`

The FT rapid-validation branch is complete. Its scientific disposition is
`FT-INCONCLUSIVE` because the scheme does not pre-specify a single numerical
superiority threshold for assigning a positive or promising label.

## Module status

| Module | Status |
|---|---|
| FT00 | PASS |
| FT01 | PARTIAL_PASS: A assets PASS; B habitat assets intentionally deferred to FT05A |
| FT02 | PASS |
| FT03 | ACCEPTED |
| FT04 | ACCEPTED / FROZEN |
| FT05A | SCIENTIFICALLY_FROZEN_WITH_ENGINEERING_FINALIZATION_EXCEPTION |
| FT05B | AUTHORIZED / ACCEPTED |
| FT06 | COMPLETE / ACCEPTED WITH NON-BLOCKING FINDINGS |

## Scientific conclusion

- FT04 model states, predictor definitions, preprocessing, lambda values and
  cutoffs remain frozen.
- FT05A contains 163/163 B technical cases with the accepted technical audit,
  completion evidence, row schema, candidate bindings and W_Original binding.
  B outcome remained unread during technical generation; no B K-means fit or
  radiomics re-extraction occurred.
- FT05B outcome access was authorized only after the FT-specific unlock and
  receipt checks. The access scope is limited to FT06 prediction/evaluation.
- FT06 evaluated M0, M1, M2, M3L, M3H, M4 and M5 by frozen prediction only on
  163 B cases (42 DFS events and 121 censored cases). Predefined C-index,
  36/60-month AUC and Brier, calibration, KM, DCA, bootstrap intervals,
  paired comparisons and A/B ranking are present.
- No B fitting, tuning, feature selection, cutoff optimization, K-means or
  habitat refit, radiomics re-extraction, or B-to-A feedback occurred.

## Engineering findings

No scientificity-blocking or severe engineering-blocking finding remains.
FT05A remains in `FINALIZING` as an engineering promotion state, while its
scientific freeze evidence is complete and accepted. The regression-suite
count is 75/75 for the existing suite plus 7/7 FT06 tests, totaling 82/82;
the earlier 81/81 wording is a non-blocking count-label discrepancy.

## Evidence

- `prognosis_analysis/ft/FT05A_scientific_freeze_amendment.md`
- `prognosis_analysis/ft/FT05A_B_technical_generation_audit.md`
- `prognosis_analysis/ft/FT05B_outcome_unlock_audit.md`
- `prognosis_analysis/ft/FT_B_unlock.json`
- `prognosis_analysis/ft/FT06_B_validation.json`
- `prognosis_analysis/ft/FT06_B_validation_report.md`
- `prognosis_analysis/ft/FT06_final_summary.md`

Patient-level source data and derived outputs remain in the local ignored
output namespace and are not part of the repository deliverable.
