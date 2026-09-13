# FT04 third-review remediation Worker contract

## Role and isolation

You are a new independent top-level Worker for the third FT04 remediation only.

- Required model: `gpt-5.6-luna`; reasoning: `xhigh`.
- This conversation is already the authorized Worker.
- Do not create/open/spawn/delegate/request any conversation, session, thread, Worker, Reviewer, subagent, child/nested/delegated/internal agent, or equivalent feature.
- Complete work inside this conversation. If impossible without delegation, return the blocker.
- Do not self-review, act as Orchestrator, or start FT05A/later modules.
- Return only the final result; no progress updates unless work exceeds one hour.

## Scope

Read and obey `AGENTS.md`, the FT scheme/amendment, accepted FT00–FT03, all FT04 contracts and review records, current FT04 code/lock/digest/audit/tests/local model states, and commits through third review `850767a1de585d2ca6042919d526703893ad9f74`.

The third-round review in `prognosis_analysis/ft/FT04_review.md` is `not accepted for downstream use`. Remediate only its two residual review-gate blockers. Preserve all fitted model states, scientific content, accepted FT04 contract closures, and B/formal isolation.

Do not touch/stage the FT01 manifest working-tree indication or orchestration control directory.

## Required remediation

1. Require the canonical accepted FT04 review record to contain and validate the exact SHA-256 of `prognosis_analysis/ft/FT04_lock_sha256.json`. Compute the current digest-file SHA-256 independently and fail closed when the marker is absent, malformed, or different. Add positive and negative wrapper tests.
2. Require the review marker `FT04 reviewed remediation commit` to equal exactly `7e509690789d52df78573f8da89606ce1da43252`. Do not accept another ancestor merely because it resolves or contains FT04 files. Continue to verify that the exact pinned commit resolves, is an ancestor, and contains the declared FT04 paths. Add negative tests substituting `624789feac69d002587d6e79b4ff0b7810d66055` and another valid ancestor.
3. Regenerate/update only directly affected FT04 code, tests, lock/digest and audit bindings as needed. Preserve truthful non-circular Git semantics: `7e509690...` is the exact previously completed remediation being reviewed by the downstream gate; do not claim the new commit contains itself.
4. Run FT04 plus FT03/FT02/W07 suites and lock validation through the wrapper. Confirm all previously closed negative paths remain closed.

## Environment and boundaries

- Every Python execution must use `tools/run_t2_radiomics.ps1` with `environment.yml` `t2_radiomics`.
- Do not read any B source/data/outcome, create FT05 artifacts, or modify formal locks/outputs.
- Do not expose patient identifiers, patient-level values, private paths, or sensitive outputs.
- Estimate first if any run is expected to exceed 40 minutes; obey the project monitoring rule.

## Version control and final response

Stage only directly necessary FT04 remediation files and create a local commit on `codex/ft-validation`. Do not push; accumulated push waits for FT04 acceptance.

Return only closure of the two blockers, wrapper tests and lock validation, preservation of model-state hashes/scientific content/B/formal locks, local commit hash, no-push confirmation, and any blocker. Do not start FT05A.
