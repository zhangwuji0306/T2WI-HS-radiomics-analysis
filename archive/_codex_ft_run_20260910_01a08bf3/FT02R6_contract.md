# FT02R6 remediation contract

## Objective

Replace the FT02 production provenance trust model with authoritative revalidation at the fitting boundary. Do not further harden Python token/context/registry secrecy; these objects are not security credentials in the CPython threat model.

## Required constraints

- Work only within FT02 implementation, FT02 tests, and the directly necessary FT02 audit text. Do not start FT03 or any later module.
- Do not read, open, derive, or use B outcome/clinical/performance data. Do not perform B imaging processing, B habitat extraction, B K-means, PyRadiomics, or modeling.
- Preserve W whole-tumor Original-only radiomics, the A-only boundary, and all FT02 split/model contracts.
- All Python execution must use `tools/run_t2_radiomics.ps1` with the repository `environment.yml` environment `t2_radiomics`.
- Before any script expected to exceed 40 minutes, make a small-sample or historical runtime estimate. Do not perform progress polling or provide progress reports while running.
- This is an independent top-level Worker. Do not create, open, delegate to, or use any session, subagent, descendant Worker, or Reviewer.
- The prior FT02R5 Worker was interrupted. Inspect and reconcile any partial FT02 changes in the working tree; do not discard unrelated FT01 changes or the orchestration control directory.
- Do not modify formal W08/L9 artifacts or unrelated project files.

## Mandatory trust-model change

The following principle is binding:

> Production provenance must be established from authoritative frozen artifacts at the fitting boundary; possession of any Python object, token, context, closure, registry entry, or prior validation result must never itself authorize fitting.

1. Remove production provenance dependence on issuer/token/WeakKeyDictionary/registry secrecy. A context may remain as an ordinary data container but must never be treated as a credential or proof of prior verification.
2. Change the production `_fit_fold_a` interface so caller-provided `train_frame + validation_frame + context` are not trusted facts. Prefer `model_id + fold`, or accept a complete A frame only if the function internally revalidates it. Do not accept caller-provided proof as a substitute for verification.
3. Implement an explicit `verify_authoritative_production_inputs()` inside the production fit boundary. It must reload the frozen W07 artifact through the authoritative loader and independently verify artifact SHA, repeat-1 canonical SHA, complete A393 membership, seed/role, A393 membership, and DFS endpoint binding using the repository’s existing authoritative sources/contracts. From the verified complete A393 frame and W07 split, derive train/validation internally.
4. Keep `run_ft02_a_for_testing()` as a synthetic frame/split test-only entry point, completely separate from production fitting and unable to weaken production checks.
5. Add adversarial regression coverage for closure issuer extraction, registry extraction/injection, registry copy, and synchronized context+registry mutation. In every case, production `_fit_fold_a` must reject or independently revalidate rather than accept the attacker-controlled state. Retain valid verified-path tests and existing FT02/W07 contract tests.
6. Update `prognosis_analysis/ft/FT02_technical_audit.md` so it describes the current trust model accurately and explicitly states that reported FT02/W07 results are local wrapper test results, not GitHub CI status checks or a GitHub gate.
7. Run the complete FT02 suite and W07 contract suite through the wrapper. Commit the scoped result on `codex/ft-validation` and attempt to push; if push fails, retain the local commit and report the exact failure without claiming remote synchronization.

## Completion criteria

- Production fitting is authorized only after fresh authoritative artifact/input revalidation at the fitting boundary.
- Context, token, issuer, closure, registry, copied state, or prior validation result cannot independently authorize fitting.
- Valid A393/W07 repeat-1 production flow remains functional; test-only synthetic flow remains separate.
- All required adversarial, FT02, and W07 tests pass.
- No B or later-module work occurs; scoped commit and push status are accurate.

## Required final response

Report only the final remediation result, test evidence, commit/push status, and blockers. Do not include progress narration.
