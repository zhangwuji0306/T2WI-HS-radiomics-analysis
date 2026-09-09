# R5 P5/G3R technical release audit

## Release state

- Stage: `G3R`
- Status: `PASS`
- Technical execution code commit: `1964cee2df00be745ff2a297d56e3569c7f47a90`
- L6 evidence-generation source commit: `882901d0d28b6ee0978c2eb25867295249290f05`
- L7 audit base commit: `1964cee2df00be745ff2a297d56e3569c7f47a90`
- P5 coverage: `10` repeats × `5` frozen W07 outer folds = `50/50` fold units
- Aggregate coverage: `17` fixed technical runs × `50` folds = `850` rows
- Observed P5 execution duration: `1479.185` seconds
- Current output: `prognosis_analysis/output/p5_technical_preflight_A_L7_1964cee`
- Predecessor output: `prognosis_analysis/output/p5_technical_preflight_A_G3R`

The production entry used the existing protected A technical-ID authorization path, then the existing authorized A outcome reader only to materialize the frozen modeling population and event/censor feasibility. No outcome values are present in the submitted evidence. Each aggregate row is one fixed `run_id` × W07 outer repeat × W07 outer fold technical-feasibility unit.

## Frozen binding and technical contract

- W04 modeling protocol SHA-256: `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe`
- W03 candidate-freeze SHA-256: `ae3ed731308d4915675678258bc1c23d9a9e9e493fec4dd57745e7049a3b5cb2`
- W07 outer-split config SHA-256: `535f0aa7caef877727dc08bb70741b1c96ed4542230b5cfbf173eeff48677217`
- W07 frozen outer-split artifact SHA-256: `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`
- W07A protocol SHA-256: `adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70`
- W07A amendment JSON SHA-256: `0ca857a7b22c5b948c675f9970cc07b5a908c3f486be3f5656c86e20b5479f14`
- P4 integrity audit SHA-256: `6baae4a1bf97a6e85bce3d71a6235fba7b6945a3aec71fa51c184502c6cbbb83`
- P4R reconciliation SHA-256: `374ddc9f6ecd01c04ff957576f032fec18f0ebbb53f6651a725ad0b6aff7786d`
- Protected code/config tree SHA-256: `0d63f6c3aa594537d8d9b6ef38e1abd8b6cf303f4558027757592b965f6884dc`
- K-means: `K=2`, `k-means++`, `n_init=100`, `max_iter=300`, `tol=1e-4`
- Fold seeds: frozen W07 seed root `12345`, 50 outer-fold entries
- `minimumROISize=10`; support states are `0=structural_absence`, `1–9=technical_small_roi`, `>=10=extractable`
- Candidate pools: `R_low=49`, `R_high=10`
- Representation contract: representative low/high masks, `G=6`, `R_low=49`, `R_high=10`
- Inner 5-fold feasibility: `PASS`

The current L6 evidence at `prognosis_analysis/W08_local_L6_integration.json` records the fold seed schedule, representative mask checks, and feature dimensions. The current P5 aggregate records fold-specific centres/boundaries, support states, population hashes, eligibility, event/censor counts, inner-fold feasibility, paired comparators, and frozen candidate hashes.

## Technical result

- Required runs: `17`
- Rows per run: `50`
- Aggregate rows: `850`
- All folds complete: `true`
- All required runs estimable: `true`
- All paired populations equal: `true`
- Minimum training events/censors: `62` / `210`
- Minimum validation events/censors: `13` / `49`
- P5 release gate: `PASS`

## Locked environment and verification

- Conda environment: `t2_radiomics`
- Python: `3.7.12`
- NumPy: `1.21.6`
- pandas: `1.3.5`
- SciPy: `1.7.3`
- scikit-learn: `1.0.2`
- PyRadiomics: `3.0.1`
- SimpleITK: `2.2.1`
- Environment probe: locked specification matched
- Complete discovery: `309` tests; `308` passed, `1` pre-existing wording failure, `0` errors
- Targeted W05/W08/R6 suite: `142/142` passed, exit code `0`
- Locked-environment `compileall`: passed, exit code `0`
- `git diff --check`: passed

The complete-suite failure is the existing `test_provenance_reconciliation` assertion for historical `failure_reason_summary` wording. It does not involve the P5 entry or current P5 aggregate result.

## Access and release boundary

- `B_data_read=false`
- `B_reader_invoked=false`
- `B_source_opened=false`
- `B_statistics_generated=false`
- `performance_generated=false`
- `predictions_generated=false`
- `risk_scores_generated=false`
- `cox_fit_generated=false`
- `model_artifacts_generated=false`
- `patient_level_outputs_written=false`
- `model_freeze_lock.json` is absent
- No formal W08 production run was started
- No formal W08 output, risk score, prediction, performance metric, model artifact, or model-freeze output was generated

The historical W08 failed-attempt archives remain preserved and are not treated as complete output.

## Aggregate evidence hashes

- `P5_fold_feasibility.csv`: `6dcb57a85982653c72bf0b44d97cf03085d841a2f10f50a252ddf3ca6e52855f`
- `P5_release_gate.json`: `1d062ed06e5713d2b4fa0698b1c187e96b1f98a043edd78a496bd51e230b4676`
- `P5_sha256_manifest.json`: `b4a0a411aac2398f359ac28d1446b7f8505a138579773d11bd869f8e23113053`
- `P5_technical_preflight_summary.json`: `cdcaff83cb61a0dcf566fdafb14685cb7f8fcbebd9f66f847c84633ef9f6db16`

The final aggregate evidence and this audit are the only allowlisted R5 evidence paths. The aggregate release binding records the current technical execution commit and the evidence-only append-only successor relation. Independent downstream review remains read-only and does not authorize formal W08, model fitting, prediction, performance evaluation, or model freezing.
