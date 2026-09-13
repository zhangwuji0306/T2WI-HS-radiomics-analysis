# FT02R4 Reviewer contract

## Scope

Independently review the FT02R4 remediation commit and current FT02 implementation, tests, and FT02 technical audit. Review only FT02. Do not modify files and do not begin FT03 or any later module.

## Acceptance criteria

- No direct or equivalent public route can issue an accepted production context from arbitrary frame/split data.
- Caller-copyable tokens, mutable flags, externally constructible objects, copied issuer state, and mutated context state cannot bypass the production fitting boundary.
- The valid A393/W07 repeat-1 verified production path remains functional.
- Synthetic fitting, if present, is test-only and cannot weaken production provenance checks.
- Regression coverage includes direct issuer invocation, copied/forged context or token, mutated verification state, and the valid verified path.
- FT02 and W07 contract tests pass through `tools/run_t2_radiomics.ps1` using `t2_radiomics`.
- No B outcome/clinical/performance data was accessed; no later-module work occurred; unrelated working-tree changes remain untouched.
- The audit text reports the current FT02 state.

## Disposition

Return exactly one disposition: `accepted for downstream use`, `accepted with nonblocking findings`, or `not accepted for downstream use`. If not plain acceptance, provide a concrete remediation plan limited to FT02, with no later-module instructions. Do not repair the implementation.

## Isolation

You are an independent top-level Reviewer. Do not create, open, delegate to, or use any session, subagent, descendant Worker, or Reviewer. Do not provide progress updates; return only the final disposition and concise evidence.
