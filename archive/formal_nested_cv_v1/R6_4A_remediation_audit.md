# R6-4A convergence-efficiency remediation audit

## Disposition

`PASS`; disposition-ready for the next protocol stage. The authorized path was R6-4A, Class A: iteration budget insufficient. The W08 gate remains `HOLD`. The next required stage is `R6-5`; this audit does not authorize formal W08, W09, model freezing, or B access.

## Remediation

The registered uniform Elastic-Net budget is `max_iter=3000`. The convergence tolerance remains `1e-7`. The objective, gradient, proximal update, line-search logic, convergence criteria, alpha grid, lambda grid, candidate order, candidate pool, W07 split, W04/W07A populations, and `minimumROISize=10` are unchanged. Warm start was not implemented because the synthetic study showed that a uniform budget alone was sufficient.

Elastic-Net fit state is cleared before every attempt. A failed refit therefore cannot expose coefficients or a baseline from an earlier fit; failed candidates remain auditable and fail closed.

## Synthetic convergence study

The study used deterministic synthetic survival data with seeds `101` and `202`, full alpha grid `[0.1, 0.5, 0.9, 1.0]`, and the stress endpoint `lambda_ratio=1e-4`:

| Design | Fits | Converged | Failed | Maximum iterations |
|---|---:|---:|---:|---:|
| `n=282, p=25`, highly correlated blocks | 8 | 8 | 0 | 1814 |
| `n=240, p=60`, independent standardized predictors | 8 | 8 | 0 | 33 |

The event structure was generated from deterministic exponential event and censoring times with a bounded event-fraction gate. A separate budget ladder on a correlated `n=282, p=25` design (`seed=101`, `alpha=0.5`, `lambda_ratio=0.01`) gave: `250` iterations failed with `iteration_budget_exhausted`; `1000`, `2000`, and `4000` iterations all converged at iteration `705`. The final maximum observed iteration count was `1814`, so `3000` leaves a fixed 1186-iteration margin without changing solver mathematics.

No warm-start path was needed. Zero-start remains the production behavior.

## Regression and boundary validation

The deterministic Cox PH and Elastic-Net regression cases preserve selected alpha, selected lambda ratio, objective, coefficient vector, risk scores, and survival predictions within the registered numerical tolerance. The failure-state regression confirms fail-closed behavior.

The targeted locked-environment suite ran 76 tests with exit code `0`: R6-4A convergence tests, W08 nested-CV tests, transactional output tests, formal release-gate tests, and A-only technical-preflight tests. It covers the lower-ROI, altered-split, altered-alpha, altered-lambda, B-access, stale-G3-certificate, frozen-binding-mismatch, no-stale-state, and no-candidate-skipping failure paths. Compileall exited `0`.

No formal 50-fold W08 run was started. No risk score, held-out prediction, C-index, AUC, Brier, calibration, W09 artifact, model-freeze lock, B read, or patient-level diagnostic material was generated or added to Git.

## Binding record

| Binding | Value |
|---|---|
| W04 | `888a4bbc871548fbef9cacc767d00cc9f01ed68d4396e20ee2063a0c098c3dfe` |
| W07 | `24764ee31381621d6a71098a00277743b126a8f00c382afb89d819357ece6502` |
| W07A | `adc8665ed5bc639353744bc6f2aa22ab421cf0a88e457057123ee29fbf7bcc70` |
| R_low candidate pool | `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0` |
| R_high candidate pool | `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce` |
| R6-4A implementation SHA-256 | `87b919d82a199461882af280adfc34a0e5e2a59974a1c4def6e3f6f9b393f6ce` |
| R6-4A config SHA-256 | `0d4cbec42fc0a26e59a31d189285e83eb134628ea949c92100325d04873637a0` |

All four B-access flags remain `false`; `model_freeze_lock.json` is absent and W08 remains `HOLD`.
