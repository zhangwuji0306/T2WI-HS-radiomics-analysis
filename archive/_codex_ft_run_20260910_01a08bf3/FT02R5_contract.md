# FT02R5 remediation contract

## Objective

Eliminate the remaining FT02 provenance bypass. The production fitting boundary must independently establish the trusted A393/W07 repeat-1 provenance; it must not rely on a caller-supplied context, closure-extracted issuer, registry membership, copyable token, mutable flag, or equivalent externally recoverable state.

## Required constraints

- Work only within FT02 implementation, FT02 tests, and the directly necessary FT02 audit text. Do not start FT03 or any later module.
- Do not read, open, derive, or use B outcome/clinical/performance data. Do not perform B imaging processing, B habitat extraction, B K-means, PyRadiomics, or modeling.
- Preserve W whole-tumor Original-only radiomics, the A-only boundary, and the production binding to A393/W07 repeat 1.
- All Python execution must use `tools/run_t2_radiomics.ps1` with the repository `environment.yml` environment `t2_radiomics`.
- Before any script expected to exceed 40 minutes, make a small-sample or historical runtime estimate. Do not perform progress polling or provide progress reports while running.
- This is an independent top-level Worker. Do not create, open, delegate to, or use any session, subagent, descendant Worker, or Reviewer.
- Do not modify formal W08/L9 artifacts or unrelated project files; preserve unrelated working-tree changes.

## Remediation requirements

1. Remove the design in which a closure or registry can be reflected on/extracted to obtain a production issuer or to inject production provenance.
2. At the production fitting boundary itself, revalidate the trusted A393 population, W07 source/provenance file identity and hash, repeat-1 canonical split/hash, complete membership, and endpoint binding. A caller-provided context may not substitute for these checks.
3. Ensure arbitrary synthetic frame/split inputs, closure issuer extraction, registry extraction/copy/injection, forged contexts, and mutated state all fail closed; keep the legitimate verified A393/W07 path functional.
4. Add regression tests covering closure issuer discovery/extraction, registry state extraction/copy/injection, forged context, state mutation, arbitrary synthetic provenance, and the valid verified path. Keep synthetic fitting strictly test-only.
5. Run the complete FT02 suite and W07 contract suite through `tools/run_t2_radiomics.ps1` and update `prognosis_analysis/ft/FT02_technical_audit.md` with only the current evidence.
6. Commit the scoped remediation on `codex/ft-validation` and attempt to push. If push fails, report the exact failure and retain the local commit; never claim remote synchronization without evidence.

## Completion criteria

- No reachable/reflected/duplicated production issuer or registry route can make arbitrary data acceptable.
- The production fitting boundary itself verifies all required A393/W07 repeat-1 provenance and endpoint bindings.
- Valid verified production path works; FT02 and W07 tests pass with the new regressions.
- No B or later-module work occurs.
- Scoped commit exists and push status is accurate.

## Required final response

Report only the final remediation result, test evidence, commit/push status, and blockers. Do not include progress narration.
