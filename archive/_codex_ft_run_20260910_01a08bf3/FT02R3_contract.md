# FT02R3 remediation contract

## Objective

Remediate the sole blocker identified by FT02 Reviewer 3: prevent the low-level FT02 fitting path from accepting a caller-constructed `_ValidatedFitContext` that was not created by the verified A393/W07 provenance flow.

## Required constraints

- Work only within FT02 files and the directly necessary FT02 tests/audit text. Do not start FT03 or any later module.
- Do not read, open, derive, or use B outcome/clinical/performance data. Do not perform B imaging processing, B habitat extraction, B K-means, PyRadiomics, or modeling.
- Preserve the W whole-tumor contract: Original-only radiomics; no Wavelet, LoG, or other filtered features.
- Preserve the A-only boundary and the verified production binding to A393/W07 repeat 1.
- All Python execution must use `tools/run_t2_radiomics.ps1` with the repository `environment.yml` environment `t2_radiomics`; do not invoke another Python executable.
- Before any script expected to exceed 40 minutes, make a small-sample or historical runtime estimate. Do not perform progress polling or provide progress reports while running.
- This is an independent top-level Worker. Do not create, open, delegate to, or otherwise use any session, subagent, descendant Worker, or Reviewer.
- Do not modify formal W08/L9 artifacts or unrelated project files.

## Remediation requirements

1. Make `_fit_fold_a`/the effective low-level fitting path reject any context that is not demonstrably issued by the verified A provenance flow. A caller must not be able to bypass the boundary by constructing `_ValidatedFitContext(a_verified=False)` or an equivalent forged object.
2. Keep legitimate production calls through the A393/W07-verified wrapper working.
3. If synthetic fitting is needed for unit tests, move it to a clearly test-only path that cannot be imported as the production fitting entry point; do not weaken production provenance checks for test convenience.
4. Add a regression test that constructs a forged/unverified context and proves the production fitting path rejects it, plus retain tests for the valid verified path and existing FT02 contracts.
5. Run the complete FT02 test suite and the W07 contract suite through the wrapper. Update `prognosis_analysis/ft/FT02_technical_audit.md` only with the current FT02 state and evidence.
6. Commit the scoped remediation on `codex/ft-validation` and attempt to push it. If push fails, report the exact failure and leave the local commit intact; do not claim remote synchronization.

## Completion criteria

- Forged/unverified contexts are fail-closed at the production boundary.
- Valid A393/W07 verified production path remains functional.
- FT02 tests and W07 contract tests pass.
- No B outcome/clinical/performance access or later-module work occurs.
- Scoped commit exists, with push attempted and accurately reported.

## Required final response

Report only the remediation result, tests, commit/push status, and any blocking issue. Do not include progress narration.
