# FT02 Technical Audit

## Status

`PASS`

FT02 is an A-only, in-memory modeling runner. The production entry point is
bound to the project-frozen W07 split artifact and does not accept a
caller-supplied split table. Synthetic fixtures use a separately named
test-only helper. No B data is read or generated, and no formal W08/L9 or
model-freeze output is written. The low-level fold fitter is internal-only:
the former public `fit_fold_a` name fails closed, while `_fit_fold_a` accepts
only a context registered inside a private weak-reference issuance registry
after verified A393 provenance and W07 binding. The production issuer is not
exported. Directly constructed contexts, copied issued contexts and contexts
whose bound frame or split is mutated are absent from or no longer match that
registry and fail closed. Synthetic fixtures use a separate
`_fit_fold_a_for_testing` path available only through the explicitly test-only
runner.

## Frozen A boundary

`load_frozen_w07_repeat1()` validates:

- W07 artifact SHA-256:
  `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502`
- repeat-1 canonical SHA-256:
  `774436340ce68cd70a2c6acd17acbb7fa484fd7f29989f12670dde519c9f376d`
- 393 unique A393 members, 1,965 repeat-1 rows and five folds;
- frozen seed `12345` and complete `train`/`validation` roles.

`run_ft02_a` additionally requires `split=A`, `technical_cohort=A393`,
`modeling_eligible=1`, exact frozen A393 membership, and DFS endpoint equality
with the W07-bound A population. Missing or ambiguous provenance fails closed
before model fitting.

## Fixed modeling contract

| Model | Predictor blocks | Fit |
|---|---|---|
| M0 | C | Cox |
| M1 | C + H_high_fraction | Cox |
| M2 | C + G | Cox |
| M3L | C + G + R_low | Cox, alpha=1 |
| M3H | C + G + R_high | Cox, alpha=1 |
| M4 | C + G + R_low + R_high | Cox, alpha=1 |
| M5 | C + W_Original | Cox, alpha=1 |

M5 accepts exactly the frozen 107-feature whole-tumor Original-only schema.
The canonical order hash is
`1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f`.
Wavelet, LoG and other filtered whole-tumor features are rejected.

All preprocessing parameters are fitted on the current training partition:
imputation, near-zero-variance filtering, correlation reduction, scaling and
feature retention. Penalized models select lambda with ordinary training-only
inner five-fold scoring at fixed alpha=1. The outer validation fold is never
used for lambda or model selection, and the W07 fold plan is never regenerated.

R_low and R_high accept the frozen P3B structural-state fields and legacy
explicit availability fields. Structural absence is excluded before
preprocessing. `technically_available=1` with
`structurally_defined=0` is rejected.

## Paired comparisons

Each comparison is fitted on one common eligible population for both models.
The common training IDs, validation IDs and fold assignments are identical by
construction and are recorded as de-identified per-fold hashes. The required
populations are:

- M2 vs M3L: R_low;
- M2 vs M3H: R_high;
- M2 vs M4 and M3L vs M3H: dual radiomics;
- M4 vs M5: dual radiomics intersected with W_Original availability.

## FT03 interfaces

`run_ft02_a` returns fold-specific fitted states containing the fitted
preprocessor and Cox model, cross-validated risk predictions, and
`survival_probability_36`/`survival_probability_60` columns. The reusable
interfaces are:

- `predict_risk_hook`;
- `predict_risk_survival_hook` and `predict_survival_hook`;
- `uno_c_index_hook` and `harrell_c_index_hook`;
- `auc_3_year_hook`, `auc_5_year_hook`;
- `brier_3_year_hook`, `brier_5_year_hook`;
- `calibration_data_hook`, `km_data_hook`, `dca_data_hook`;
- `bootstrap_ci_hook` with explicit seed and mode;
- `paired_comparison_hook` and `build_provenance_record`.

The survival outputs are finite probabilities in `[0, 1]` derived from the
fitted Cox baseline survival. The numerical hook contract is explicit:
`S(t)` is the survival probability at 36 or 60 months; Brier compares `S(t)`
with a target of 1 for survival beyond the horizon and 0 for an event by the
horizon; calibration bins `S(t)` against the same observed survival quantity;
and DCA receives the corresponding event probability `1 - S(t)`. KM uses the
fold risk score for its fixed risk-rank groups.

## Validation evidence

Environment probe, executed through the locked wrapper:

```text
Command: tools/run_t2_radiomics.ps1
Exit code: 0
Environment: t2_radiomics
Python: 3.7.12
NumPy: 1.21.6
Pandas: 1.3.5
SciPy: 1.7.3
scikit-learn: 1.0.2
PyRadiomics: 3.0.1
SimpleITK: 2.2.1
PyWavelets: 1.3.0
matches_locked_spec: true
```

FT02 synthetic/regression/static tests:

```text
Command: tools/run_t2_radiomics.ps1 -PythonArguments @('.\tests\test_ft02_runner.py')
Exit code: 0
Tests: 18 run, 18 passed, 0 failed (189.510 s)
```

The test set covers all seven model definitions, frozen split seed/role
validation, production W07 binding and fail-closed A provenance, common paired
training/validation IDs and per-fold hashes, training-only preprocessing and
lambda selection, P3B and legacy structural availability, W_Original-only
schema, risk and survival interfaces, metric hooks, bootstrap seed/mode,
B-row/path rejection and FT isolation. It also verifies that direct public
fold-fitting bypasses and caller-constructed or unissued fit contexts fail
closed, that copying an issued production context does not copy its private
registry membership, that mutation invalidates an issued context, that an
issued verified context reaches the production fitter, and that a known
two-case calibration fixture returns survival-direction targets at the
requested horizon. Synthetic fitting uses a separate test-only fitter.

Existing W07 regression suite:

```text
Command: tools/run_t2_radiomics.ps1 -PythonArguments @('.\tests\test_w07_outer_splits.py')
Exit code: 0
Tests: 13 run, 13 passed, 0 failed (1.617 s)
```

The FT isolation checks preserve the formal habitat freeze, formal modeling
protocol, execution status, frozen W07 configuration and frozen W07 split
artifact. The formal model-freeze lock remains absent. No later FT module was
executed.

## Deliverables

- `prognosis_analysis/ft/ft02_runner.py`
- `prognosis_analysis/ft/FT02_technical_audit.md`
- `tests/test_ft02_runner.py`
