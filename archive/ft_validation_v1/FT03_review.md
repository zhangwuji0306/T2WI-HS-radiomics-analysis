# FT03 First-Round Review

## Disposition

`accepted for downstream use`

## Evidence

- Commit under review: `6d30aeccdd2c606098a0e3a7abe9effbd670d285`; its scoped diff contains only the aggregate FT03 JSON and Markdown report. The production runner is bound in the JSON to code commit `c3de2b2405efa0841c6124a6c2e768c70977188b` and the recorded runner hash matches the reviewed file.
- All seven frozen models (`M0`, `M1`, `M2`, `M3L`, `M3H`, `M4`, `M5`) completed on the frozen W07 repeat-1 five-fold split. All seven prespecified paired comparisons use their required common eligible populations.
- The 14 local model and paired-prediction tables all exist under the ignored FT03 output namespace; recorded hashes and row counts match. Each table has unique coverage, and every row's fold matches its single frozen held-out validation fold.
- Model records confirm five folds per model, converged fits, training-only preprocessing, and—where applicable—training-only inner five-fold lambda selection with `alpha=1`, 20 frozen lambda candidates, and no outer-validation use. Frozen `R_low=49`, `R_high=10`, and `W_Original=107` bindings match their prescribed hashes.
- Uno and Harrell C-index, 3/5-year AUC and Brier score, 3/5-year calibration and DCA, KM output, 200-replicate bootstrap confidence intervals, and paired-comparison results are complete and consistent with the accepted FT02 hooks. Aggregate JSON and report labels are `exploratory_fullA_habitat_non_nested_validation` and `non_nested_exploratory_estimate`.
- All recorded source, split, environment, and local-output hashes match the reviewed files. Tracked FT03 deliverables contain no patient identifiers, patient-level values, B data, credentials, private source paths, or formal W08/L9 outputs. B-access flags remain false, the formal model-freeze lock remains absent, and no FT04-or-later artifact is present.

## Wrapper tests

```text
tools/run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_ft03_runner','tests.test_ft02_runner','tests.test_w07_outer_splits')
41 tests run; 41 passed; 0 failed; exit code 0; 184.745 s
```

## Findings and downstream decision

Blocking findings: none.

Nonblocking findings: none.

FT03 is accepted for downstream use. This decision authorizes only the next contract-defined gate and does not execute or review any later FT module.
