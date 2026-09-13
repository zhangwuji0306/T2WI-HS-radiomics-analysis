# R5 P5/G3R technical release audit

## Release state

- Stage: `G3R`
- Status: `PASS`
- P5: `50/50` frozen W07 outer fold units complete
- Aggregate coverage: `17` fixed runs × `50` folds = `850` technical rows
- Code commit at certificate generation: `77cddd970f176533fd44fe1fbaaac880651fc84f`
- Certificate time: `2026-09-05T20:21:51Z`
- Current successor output: `prognosis_analysis/output/p5_technical_preflight_A_G3R`
- Predecessor output remains preserved at `prognosis_analysis/output/p5_technical_preflight_A`

Each aggregate row represents one fixed `run_id` × W07 outer repeat × W07 outer fold technical feasibility unit. All runs have 50 rows. Training-only patient-balanced K=2 centre fitting, fold-specific boundary assignment, support-state classification, model-specific eligibility, event/censor gates, inner 5-fold feasibility, and paired-population checks passed.

## Frozen binding

- W04 protocol SHA-256: `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe`
- W07 outer split SHA-256: `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`
- W07A protocol SHA-256: `adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70`
- W03 `R_low` candidate hash: `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0`
- W03 `R_high` candidate hash: `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`
- P4R status: `approved_reconciliation`
- P4R manifest SHA-256: `374ddc9f6ecd01c04ff957576f032fec18f0ebbb53f6651a725ad0b6aff7786d`
- Candidate counts: `R_low=49`, `R_high=10`
- Small-ROI states: `0=structural_absence`, `1–9=technical_small_roi`, `>=10=extractable`
- `minimumROISize=10`

## Compatibility and environment

- PyRadiomics: `3.0.1`
- SimpleITK: `2.2.1`
- Python: `3.7.12` in conda environment `t2_radiomics`
- Exact-10 compatibility code SHA-256: `37bee9152aec365b8bbe0586d1169ab8870de45b99ad159b1c2642a14cdfa882`
- Compatibility config SHA-256: `4b74b8cabd90a8e7ae1d269abc13fd8f423e1b192f3fbb2effafab1c9cb5342f`
- Effective backend minimum size: `null`; precheck threshold: `>=10`
- Environment fingerprint SHA-256: `a6151d7a135ea19a3f529199996c4063f2fd7b3da4484aa920a73599939ab74b`

## Isolation and release boundary

- `B_data_read=false`
- `B_reader_invoked=false`
- `B_source_opened=false`
- `B_statistics_generated=false`
- `performance_generated=false`
- `predictions_generated=false`
- `patient_level_outputs_written=false`
- `model_artifacts_generated=false`
- `model_freeze_lock.json` is absent
- No new formal W08 run was started by R5

The historical `attempt_001_failed` archive remains explicitly failed at `prognosis_analysis/output/w08_formal_A/attempts/attempt_001_failed` and is not treated as complete.

## SHA-256 evidence

The current successor manifest is `prognosis_analysis/output/p5_technical_preflight_A_G3R/P5_sha256_manifest.json`. Its aggregate artifact hashes are recorded in `R5_P5_G3R_aggregate_evidence.json`.
