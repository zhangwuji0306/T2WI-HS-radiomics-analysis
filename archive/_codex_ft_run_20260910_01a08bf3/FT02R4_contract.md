# FT02R4 remediation contract

## Objective

Resolve the remaining FT02 provenance-boundary bypass: `_issue_production_fit_context(frame, split)` (or any equivalent production-context issuer) must not be directly callable by an unverified caller to obtain a context accepted by `_fit_fold_a`.

## Required constraints

- Work only within FT02 implementation, FT02 tests, and the directly necessary FT02 audit text. Do not start FT03 or any later module.
- Do not read, open, derive, or use B outcome/clinical/performance data. Do not perform B imaging processing, B habitat extraction, B K-means, PyRadiomics, or modeling.
- Preserve W whole-tumor Original-only radiomics and the A-only boundary, including production binding to A393/W07 repeat 1.
- All Python execution must use `tools/run_t2_radiomics.ps1` with the repository `environment.yml` environment `t2_radiomics`.
- Before any script expected to exceed 40 minutes, make a small-sample or historical runtime estimate. Do not perform progress polling or provide progress reports while running.
- This is an independent top-level Worker. Do not create, open, delegate to, or use any session, subagent, descendant Worker, or Reviewer.
- Do not modify formal W08/L9 artifacts or unrelated project files; preserve unrelated working-tree changes.

## Remediation requirements

1. Redesign the effective production-context issuer so an external caller cannot directly invoke it with arbitrary frame/split data and obtain a context accepted by the production fitting path.
2. Do not rely on a caller-provided or copyable token, a mutable boolean, or an externally constructible object as the sole provenance proof. Use an internal, non-forgeable issuance path or equivalent fail-closed design consistent with the existing codebase.
3. Ensure the legitimate A393/W07 verified wrapper remains functional.
4. Add regression tests for: direct issuer invocation, copied issuer/token or equivalent forged context, mutated verification state, and the valid verified production path. Keep synthetic tests isolated from production entry points.
5. Run the complete FT02 suite and W07 contract suite through `tools/run_t2_radiomics.ps1` and update `prognosis_analysis/ft/FT02_technical_audit.md` with current evidence.
6. Commit the scoped remediation on `codex/ft-validation` and attempt to push. If push fails, report the exact failure and retain the local commit; never claim remote synchronization without evidence.

## Completion criteria

- No direct or forged route can obtain an accepted production context without the verified A393/W07 flow.
- The valid verified production path works.
- FT02 and W07 tests pass, including the new bypass regressions.
- No B or later-module work occurs.
- Scoped commit exists and push status is accurate.

## Required final response

Report only the final remediation result, test evidence, commit/push status, and blockers. Do not include progress narration.
