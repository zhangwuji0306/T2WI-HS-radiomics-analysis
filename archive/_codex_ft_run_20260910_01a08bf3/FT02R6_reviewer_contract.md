# FT02R6 Reviewer contract

## Scope

Independently review the FT02R6 trust-model redesign, current FT02 implementation/tests, and FT02 technical audit. Review only FT02. Do not modify files and do not begin FT03 or any later module.

## Acceptance criteria

- Production `_fit_fold_a` establishes provenance from authoritative frozen inputs at the fitting boundary, not from caller possession of any Python object, token, context, closure, registry entry, or prior validation result.
- The production boundary revalidates the authoritative W06/W07 artifacts and all required A393/W07 repeat-1 source, canonical hash, membership, seed/role, and endpoint bindings using the repository’s actual contracts.
- Train/validation data used by production fitting is derived internally from verified authoritative inputs; caller-provided frames/context cannot substitute for this verification.
- `run_ft02_a_for_testing()` is clearly test-only and separate from production fitting.
- Adversarial regression coverage includes closure issuer extraction, registry extraction/injection, registry copy, and synchronized context+registry mutation, while the valid verified path remains functional.
- FT02 22/22, W07 13/13, and py_compile evidence is reproducible through `tools/run_t2_radiomics.ps1` with `t2_radiomics`.
- The audit accurately labels test results as local wrapper results and does not claim GitHub CI status checks or a GitHub gate.
- No B outcome/clinical/performance data or later-module work occurred; unrelated FT01 and control-directory changes remain untouched.

## Disposition

Return exactly one disposition: `accepted for downstream use`, `accepted with nonblocking findings`, or `not accepted for downstream use`. If not plain acceptance, provide a concrete remediation plan limited to FT02; do not repair the code or instruct work on later modules. The module may proceed only on an accepted disposition under the orchestration rules.

## Isolation

You are an independent top-level Reviewer. Do not create, open, delegate to, or use any session, subagent, descendant Worker, or Reviewer. Do not provide progress updates; return only the final disposition and concise evidence.
