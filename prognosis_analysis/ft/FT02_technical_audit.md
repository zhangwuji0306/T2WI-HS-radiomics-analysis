# FT02 Technical Audit

## Status

`PASS`

FT02 is implemented as an A-only, in-memory modeling runner. It consumes a
caller-supplied A feature frame and the pre-frozen W07 repeat-1 five-fold
split frame. It does not read or generate B data and does not write formal or
FT patient-level outputs.

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
Wavelet, LoG, and other filtered whole-tumor features are rejected.

All preprocessing parameters are fitted on the current training partition:
imputation, near-zero-variance filtering, correlation reduction, scaling,
and feature retention. Penalized models select lambda with ordinary
training-only inner five-fold scoring at fixed alpha=1; outer validation is
never used for lambda or model selection. The outer A performance split is
the supplied W07 repeat-1 set and is never regenerated.

R_low and R_high require explicit structural and technical availability flags.
Structural absence is excluded before preprocessing and is not represented by
imputed radiomics values. The M4 versus M5 paired population is explicitly
dual-radiomics availability intersected with W_Original availability.

## FT03 interfaces

`run_ft02_a` returns fold-specific preprocessing and solver audits, cross-
validated risk predictions, split provenance, population counts, paired
eligibility, and de-identified artifact hashes. The reusable interfaces are:

- `predict_risk_hook`
- `uno_c_index_hook` and `harrell_c_index_hook`
- `auc_3_year_hook`, `auc_5_year_hook`
- `brier_3_year_hook`, `brier_5_year_hook`
- `calibration_data_hook`, `km_data_hook`, `dca_data_hook`
- `bootstrap_ci_hook` with explicit seed and mode
- `paired_comparison_hook`
- `build_provenance_record`

Invalid A/B boundaries, missing frozen schema, missing availability flags,
split mismatch, duplicate IDs, nonfinite outcomes, failed fits, and
non-estimable lambda paths fail closed with `FTValidationError` or the
underlying audited numerical failure.

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

FT02 synthetic/regression/static tests, executed through the locked wrapper:

```text
Command: tools/run_t2_radiomics.ps1 -PythonArguments @('.\tests\test_ft02_runner.py')
Exit code: 0
Tests: 8 run, 8 passed, 0 failed (66.128 s)
```

The test set covers all seven model definitions, frozen split propagation,
training-only preprocessing and lambda selection, structural/technical
availability, W_Original-only schema, paired eligibility, risk and metric
hooks, bootstrap seed/mode, B-row/path rejection, and FT isolation.

The existing frozen-split regression suite was also run through the wrapper:

```text
Command: tools/run_t2_radiomics.ps1 -PythonArguments @('.\tests\test_w07_outer_splits.py')
Exit code: 0
Tests: 13 run, 13 passed, 0 failed
```

The FT isolation regression checks that the formal habitat freeze, formal
modeling protocol, execution status, frozen W07 configuration, and frozen W07
split artifact remain byte-identical during the test run. The formal model
freeze lock remains absent. No B reader, B extraction path, formal lock writer,
or formal W08/L9 output writer is part of the FT02 runner.

## Deliverables

- `prognosis_analysis/ft/ft02_runner.py`
- `prognosis_analysis/ft/__init__.py`
- `tests/test_ft02_runner.py`
- `prognosis_analysis/ft/FT02_technical_audit.md`
