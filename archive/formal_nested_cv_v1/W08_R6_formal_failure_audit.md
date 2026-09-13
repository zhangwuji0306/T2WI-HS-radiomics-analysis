# R6 formal W08 failure audit

- Stage: `W08 formal`
- Execution status: `FAIL`; release state: `HOLD`
- Command: `conda run -n t2_radiomics --no-capture-output python prognosis_analysis/scripts/w08_formal_run_a.py`
- Code commit: `fdd0ce0f779fb10555465a4d040f6e390969f541`
- Locked environment: Python 3.7.12, PyRadiomics 3.0.1, SimpleITK 2.2.1
- Release gate at launch: `PASS`; `formal_authorized=true`
- Start: `2026-09-06 06:27:15` (local time)
- End: `2026-09-06 11:07:02` (local time)
- Elapsed: `16786.5 s` (`4 h 39 min 47 s`)

## Outcome

The formal runner entered the frozen nested-CV modeling stage and terminated with:

`W08NumericalFailure: Elastic-Net Cox fit did not converge`

The failure was handled fail-closed. No alpha grid, lambda rule, penalty semantics, feature-selection rule, eligibility rule, split, or convergence handling was changed. The attempt was preserved in the local protected output archive as a failed attempt.

The required `50/50` formal completion certificate was not produced. No accepted per-fold/run estimability evidence is available, and no final W08 manifest was generated. The following final artifacts were not generated: `predictions.csv`, `fold_results.csv`, `selection_results.csv`, and `formal_output_manifest.json`.

## Access and stage boundary

- `B_data_read=false`
- `B_reader_invoked=false`
- `B_source_opened=false`
- `B_statistics_generated=false`
- `model_freeze_lock.json` absent
- W09 metrics, performance evaluation, model comparison, and W09-derived conclusions not executed
- Patient-level runtime material remains local under the ignored W08 output area; no patient-level file is included in this audit

The next permitted action is protocol-owner review under the frozen convergence-failure rule. No automatic remediation or formal rerun is authorized by this failure record.
