# W08 L7 current-code technical preflight audit

## Result state

- Status: `HOLD`
- Scope: final-code P5/G3R technical-only preflight
- Source code commit: `1964cee2df00be745ff2a297d56e3569c7f47a90`
- `origin/main`: `1964cee2df00be745ff2a297d56e3569c7f47a90`
- Current branch: `codex/l7-current-code-technical-preflight`, tracking `origin/codex/l7-current-code-technical-preflight`
- Worktree: clean
- L8 readiness: `NOT_READY`

## Locked environment

The wrapper resolved the `t2_radiomics` environment and matched `environment.yml`: Python `3.7.12`, NumPy `1.21.6`, pandas `1.3.5`, SciPy `1.7.3`, scikit-learn `1.0.2`, PyRadiomics `3.0.1`, SimpleITK `2.2.1`, PyYAML `6.0`, openpyxl `3.0.10`, matplotlib `3.5.3`, and PyWavelets `1.3.0`.

## Verification

- Full discovery: `302` tests; `289` passed, `5` failures, `8` errors; exit code `1`. The non-passing cases are the existing provenance/W03 local-freeze and registered-binding state checks.
- W05/W08/R6 targeted suite: `175` tests; `171` passed, `4` failures, `0` errors; exit code `1`. The four failures are existing R6-5/R6-5R/W08 registered binding hash mismatches.
- Compile check: exit code `0`.

## Synthetic current-code core

The current code completed the in-memory technical core for `50/50` frozen fold units and `850/850` aggregate rows (`17` fixed runs × `50` folds). All runs were estimable; paired populations were equal; inner 5-fold feasibility passed; centres and boundaries were finite; representative low/high support states were exercised; `minimumROISize=10`; and `n_init=100`. The frozen block counts were G=`6`, R-low=`49`, and R-high=`10`.

All four B-access flags were `false`. No performance, Cox, risk, prediction, patient-level, or model-freeze output was produced. This execution is explicitly `TEST_ONLY`; it is not a production P5/G3R certificate.

## Production boundary

The worker was prohibited from reading real outcomes or patient-level material. The worker worktree did not contain the local A freeze inputs, and no other checkout was mounted. Consequently, the production current-code 50-fold preflight was not run and no production certificate or formal W08 output was generated. The synthetic result must not be promoted to `PASS` or used as L8 binding evidence.
