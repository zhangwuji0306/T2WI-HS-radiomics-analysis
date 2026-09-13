# FT02 remediation contract

## Role and boundary

Remediate exactly the FT02 defects identified by the first Reviewer. Do not execute FT03–FT06.

Worker session constraints:

- This is a new independent Worker session. Do not create, open, spawn, delegate to, or request any other conversation, session, thread, subagent, child agent, nested agent, or equivalent.
- Complete only this FT02 remediation; if impossible without delegation, stop and return the blocker.
- Work locally in `<LOCAL_PATH>` on `codex/ft-validation`.
- All Python execution and tests must use `tools/run_t2_radiomics.ps1 -PythonArguments ...` with the `t2_radiomics` environment from `environment.yml`; do not use arbitrary Python or direct conda commands.

## Required corrections

1. Paired comparisons must use a single common eligible population for both models, including the same training IDs, validation IDs and fold assignments; the five affected comparisons are M2 vs M3L, M2 vs M3H, M2 vs M4, M3L vs M3H and M4 vs M5. Record and test per-fold ID hashes.
2. The production A entry point must load/validate the frozen W07 repeat-1 artifact and canonical hash, seed, fold roles and complete A393 membership. Caller-supplied arbitrary five-fold tables must not be accepted as a substitute.
3. The A-only boundary must fail closed when A cohort identity/membership cannot be proven. Missing split/provenance columns or ambiguous/non-A inputs must be rejected before model execution.
4. Preserve FT03-consumable fitted model/preprocessing state or provide a tested interface that returns 36/60-month survival probabilities in addition to risk scores, with numerical semantics suitable for Brier, calibration, KM and DCA.
5. Validate structural availability consistency, at minimum reject `technically_available=1` with `structurally_defined=0`, while accepting the frozen P3B structural-state fields.

## Non-changes

Keep M0–M5, W_Original 107-feature Original-only definition, alpha=1, training-only preprocessing/λ selection, frozen split, candidate pools, A-only scope, B lock, and formal W08/L9 outputs unchanged. Do not read or generate B data.

## Required validation and deliverables

- Update FT-only runner/tests/audit only as needed.
- Add regression tests for common training populations/per-fold IDs, canonical W07 binding, A fail-closed, survival probabilities and structural-state validation.
- Run the complete FT02 suite and W07 regression suite through the wrapper; record commands, versions, pass counts and exit codes in `prognosis_analysis/ft/FT02_technical_audit.md`.
- Commit/push only FT02 remediation files; preserve unrelated changes and untracked contracts.

## Acceptance criteria

- All five corrections are enforced by executable code and tests.
- FT03 can consume the runner's fitted state/survival prediction interface without reconstructing hidden state.
- B remains unread and formal locks/output namespaces are unchanged.
- No later FT module is executed.
