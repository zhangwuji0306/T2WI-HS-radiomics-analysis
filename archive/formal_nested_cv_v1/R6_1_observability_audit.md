# R6-1 numerical-failure observability audit

## Scope

R6-1 adds auditable numerical-failure context to the W08 nested-CV solver and
formal failure archive. The implementation does not alter the solver's
mathematical path, frozen candidate grid, convergence rule, or fail-closed
exception semantics.

## Failure context

The outer model context records:

- `repeat`, `outer_fold`, `run_id`, `model_id`, `population`, and `inner_seed`;
- training/validation sample counts and event counts;
- post-preprocessing `p` and retained feature counts by frozen feature block.

Inner candidate failures additionally record alpha and lambda coordinates,
iterations, convergence status/reason, stability actions, line-search
backtracking count, linear-predictor clipping count, objective diagnostics,
and the de-identified inner train/validation hashes already used by W08.

Outer final-refit failures additionally record the selected alpha and lambda
ratio, outer `lambda_max`, final lambda, selected inner score, retained feature
number, and `non_zero_coefficient_number` (the value is explicitly `null` when
the failed fit did not produce coefficients), together with the last objective,
objective improvement, coefficient delta, and iteration count.

The formal runner serializes this context under `numerical_failure_audit` in
failed-attempt metadata. Serialization removes patient-level identifier keys;
only aggregate counts and existing de-identified hashes are retained.

## Mathematical-path preservation

The following frozen values remain unchanged in the solver and runner:

- `max_iter=250`;
- `tolerance=1e-7`;
- initial coefficient vector, line-search proposal rule and backtracking rule;
- alpha grid, lambda ratios, lambda reference scopes, objective, gradient,
  candidate handling, and convergence criteria;
- W03/W04/W07/W07A bindings, `minimumROISize=10`, populations, split handling,
  and the B lock.

`test_solver_instrumentation_does_not_change_baseline_outputs` compares
deterministic Cox PH and Elastic-Net solver outputs with the pre-R6-1 solver
at commit `899cf71e1895985f1f2eb5daf482d1c595dad154`; coefficients, baseline
arrays, risks, and survival predictions are identical.

## Verification

The locked `t2_radiomics` environment was not available on this host. The
required command was attempted:

```text
conda.exe run -n t2_radiomics --no-capture-output python -m compileall -q prognosis_analysis/scripts tests
```

Result: not executed; `conda.exe` was not found. No locked-environment test
result is claimed.

System-Python syntax check (not a substitute for the locked environment):

```text
python -m compileall -q prognosis_analysis/scripts tests
```

Result: passed.

System-Python R6-1/W08 targeted discovery (not a substitute for the locked
environment):

```text
python -m unittest tests.test_w08_nested_cv tests.test_w08_transactional_outputs tests.test_w08_formal_release_gate tests.test_w08_technical_preflight_a
```

Result: 18 tests discovered; 15 passed and 3 errored during import because
`SimpleITK` is unavailable in the system Python.

The complete repository discovery was also run with system Python:

```text
python -m unittest discover -s tests -p "test*.py"
```

Result: 148 tests discovered; 1 pre-existing
`test_provenance_reconciliation` assertion failed because the tracked
historical `execution_status.json` summary does not contain the legacy phrase
`minimum ROI`, and 17 tests errored during import because `SimpleITK` is
unavailable. No R6-1 file or execution-status file was changed for those
environment/unrelated results.

A dependency-independent focused probe passed 2 checks: forced outer-refit
failure context contains `non_zero_coefficient_number: null`, and serialized
failure context contains neither patient identifiers nor patient paths.

## Stage boundary

B access remains false, the formal W08 gate remains `HOLD`, final W08 outputs
and `model_freeze_lock.json` remain absent, and W09 was not executed. No
formal W08 run, diagnostic replay, performance run, or patient-level artifact
was started for R6-1.
