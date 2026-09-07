# R5 P5/G3R technical release audit

## Release state

- Stage: `G3R`
- Status: `PASS`
- Technical execution code commit: `b8c98e9ef2de4a1cc86811f7598f57b1627925c6`
- Evidence binding commit: `0000000000000000000000000000000000000000`
- P5 coverage: `10` repeats × `5` frozen W07 outer folds = `50/50` fold units
- Aggregate coverage: `17` fixed technical runs × `50` folds = `850` rows
- Observed P5 execution duration: `201.760` seconds
- Current output: `prognosis_analysis/output/p5_technical_preflight_A_G3R`
- Predecessor output: `prognosis_analysis/output/p5_technical_preflight_A`

Each aggregate row is one fixed `run_id` × W07 outer repeat × W07 outer fold technical-feasibility unit. The computation performs training-only patient-balanced K=2 centre fitting, fold-specific boundary assignment, support-state classification, model-specific eligibility, event/censor feasibility, inner 5-fold feasibility, and paired-population equality checks. No patient-level rows are written to the P5 aggregate output.

## Frozen binding

- W04 modeling protocol SHA-256: `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe`
- W03 candidate-freeze SHA-256: `ae3ed731308d4915675678258bc1c23d9a9e9e493fec4dd57745e7049a3b5cb2`
- W07 outer-split config SHA-256: `535f0aa7caef877727dc08bb70741b1c96ed4542230b5cfbf173eeff48677217`
- W07 frozen outer-split artifact SHA-256: `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`
- W07A protocol SHA-256: `adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70`
- W07A amendment JSON SHA-256: `0ca857a7b22c5b948c675f9970cc07b5a908c3f486be3f5656c86e20b5479f14`
- P4 integrity audit SHA-256: `6baae4a1bf97a6e85bce3d71a6235fba7b6945a3aec71fa51c184502c6cbbb83`
- P4R reconciliation SHA-256: `374ddc9f6ecd01c04ff957576f032fec18f0ebbb53f6651a725ad0b6aff7786d`
- Protected code/config tree SHA-256: `a1018d52365c64709ee777a6c4f9d938025b75cda13ff84d081fa4404f3f5f97`

The protected manifest covers 36 committed code/config files. The exact-10 compatibility binding is PyRadiomics `3.0.1`, scientific `minimumROISize=10`, effective backend minimum `null`, and precheck threshold `>=10`; compatibility code SHA-256 is `b211fd510499cf357bb510e14f5c6446e6df24d7759ffbdd19d58a6477cc891f`, and compatibility config SHA-256 is `4b74b8cabd90a8e7ae1d269abc13fd8f423e1b192f3fbb2effafab1c9cb5342f`.

## Technical result

- Required runs: `17`
- Rows per run: `50`
- All required runs estimable: `true`
- All paired populations equal: `true`
- Minimum training events/censors: `62` / `210`
- Minimum validation events/censors: `13` / `49`
- Inner 5-fold feasibility: `PASS`
- `R_low` candidates: `49`
- `R_high` candidates: `10`
- Support states: `0=structural_absence`, `1–9=technical_small_roi`, `>=10=extractable`

## Environment

- Conda environment: `t2_radiomics`
- Python: `3.7.12`
- NumPy: `1.21.6`
- pandas: `1.3.5`
- SciPy: `1.7.3`
- scikit-learn: `1.0.2`
- PyRadiomics: `3.0.1`
- SimpleITK: `2.2.1`
- Environment fingerprint SHA-256: `a6151d7a135ea19a3f529199996c4063f2fd7b3da4484aa920a73599939ab74b`

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
- No new formal W08 run was started

The historical `prognosis_analysis/output/w08_formal_A/attempts/attempt_001_failed` archive remains explicitly failed at `nested_cv_modeling_radiomics_extraction`, with final outputs absent and the archive preserved as a failed attempt.

## Aggregate evidence hashes

The current P5 output manifest records the hashes of `P5_fold_feasibility.csv`, `P5_release_gate.json`, and `P5_technical_preflight_summary.json`; the final aggregate evidence additionally records the manifest hash.

- `P5_fold_feasibility.csv`: `4d31eb6dcb6d2ffad987fbfec3e0e943c6a717f5872be5351259b33616a6fd89`
- `P5_release_gate.json`: `2477ca22b8242d6c389c90ce55be043d8f7264d4d0348461842b9d1f17aca948`
- `P5_sha256_manifest.json`: `a3d416e13fcd058f6c2177a4b7df941dc45fa05d9add162f5be3c8cee532e144`
- `P5_technical_preflight_summary.json`: `42ca097880802de79fcee38527203e3d2b2779b8402a7382f0f7a9a8624d20bc`

The final aggregate and this audit are the only allowlisted R5 evidence paths. The aggregate release binding records the current technical execution commit and the evidence-only append-only successor relation.

## Independent review

- Disposition: `ACCEPT_WITH_FINDINGS`
- Review scope: current-code `b8c98e9` P5 technical-only rerun.
- Review result: 50/50 folds, 17 runs, 850 aggregate rows, artifact hashes, frozen bindings, P4R validator, B/formal W08 boundaries, and preserved local archives were accepted with no blocker; the P5 targeted suite passed 15/15.
- Non-blocking findings: the allowlisted R5 evidence in this audit is being rebound from the prior execution commit; the complete provenance unittest suite retains one historical wording assertion that does not match the current legitimate Elastic-Net Cox failure summary, while the P5 targeted suite passed 15/15 and the P4R validator passed.
- The all-zero `evidence_binding_commit` is temporary append-only bookkeeping; it must be replaced by the actual direct successor commit during finalization before formal W08 release-gate validation.
