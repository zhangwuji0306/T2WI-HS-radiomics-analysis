# FT02R3 Reviewer contract

## Scope

Independently review the FT02R3 remediation commit and the current FT02 implementation, tests, and FT02 technical audit. Review only FT02; do not modify files and do not begin FT03 or any later module.

## Acceptance criteria

- The production fitting boundary cannot be bypassed by constructing or mutating an unverified/forged `_ValidatedFitContext` or equivalent object.
- The valid A393/W07 verified production path remains functional and bound to the required split/provenance.
- A test-only synthetic path, if present, cannot weaken or substitute for production provenance checks.
- The regression test covers the forged/unverified-context case.
- FT02 tests pass and the W07 contract suite passes, using `tools/run_t2_radiomics.ps1` with the `t2_radiomics` environment.
- No B outcome/clinical/performance data was accessed and no later-module work was performed.
- The audit text reflects the current state and no unrelated files are modified.

## Disposition

Return exactly one disposition: `accepted for downstream use`, `accepted with nonblocking findings`, or `not accepted for downstream use`. If the result is not plain acceptance, provide a concrete remediation plan limited to FT02R3/FT02, with no instructions to start later modules. Do not repair the implementation yourself.

## Isolation

You are an independent top-level Reviewer. Do not create, open, delegate to, or use any session, subagent, descendant Worker, or Reviewer. Do not provide progress updates; return only the final disposition and concise evidence.
