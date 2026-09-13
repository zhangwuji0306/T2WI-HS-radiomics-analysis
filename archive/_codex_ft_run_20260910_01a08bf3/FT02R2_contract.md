# FT02 second remediation contract

## Role and boundary

Remediate only the two FT02 blockers from the subsequent Reviewer. Do not execute FT03–FT06.

Worker session constraints:

- This is a new independent Worker session. Do not create, open, spawn, delegate to, or request any other conversation, session, thread, subagent, child agent, nested agent, or equivalent.
- Complete only this FT02 remediation; if impossible without delegation, stop and return the blocker.
- Work locally in `<LOCAL_PATH>` on `codex/ft-validation`.
- All Python execution/tests must use `tools/run_t2_radiomics.ps1 -PythonArguments ...` with `environment.yml`'s `t2_radiomics`; do not use arbitrary Python or direct conda commands.

## Required corrections

1. Prevent the public low-level `fit_fold_a` interface from fitting without verified A provenance/membership. Either make it an internal-only implementation or require an explicit validated A context and reject missing/invalid `technical_cohort`, `modeling_eligible`, A393 membership and frozen W07 binding before any fit. Add a regression test proving the bypass fails closed.
2. Correct the calibration hook so survival probability and observed outcome quantity have consistent direction and horizon semantics. Define the numerical contract explicitly and add a known synthetic calibration regression test that would fail under the old direction mismatch. Keep 36/60-month survival probabilities usable by Brier, calibration, KM and DCA.

## Non-changes and validation

Keep M0–M5, W_Original 107-feature Original-only definition, alpha=1, training-only preprocessing/λ selection, paired common populations, frozen W07 repeat-1 binding, B lock, and formal W08/L9 outputs unchanged. Do not read or generate B data. Run the complete FT02 suite and W07 regression suite through the wrapper, update `prognosis_analysis/ft/FT02_technical_audit.md`, and commit/push only FT02 remediation files.

## Acceptance criteria

- Low-level and production paths cannot bypass A provenance before fitting.
- Calibration quantities are directionally and horizon-consistent with tested numeric semantics.
- Tests pass and no later FT module is executed.
