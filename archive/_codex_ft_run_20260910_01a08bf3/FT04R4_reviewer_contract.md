# FT04 fourth-round Reviewer contract

You are the independent fourth-round Reviewer for current FT04.

## Isolation

- Required model: `gpt-5.6-sol`; reasoning: `medium`.
- This conversation is already the authorized Reviewer.
- Do not create, open, spawn, delegate, or request any conversation, session, thread, Worker, Reviewer, subagent, child agent, nested agent, delegated agent, internal agent, or equivalent feature.
- Complete the review here. If impossible without delegation, return the blocker.
- Do not repair implementation, act as Worker or Orchestrator, or start FT05A or later modules.
- Return only the final review. If work exceeds one hour, one hourly status is permitted.

## Sources and scope

Read and obey `AGENTS.md`, the FT scheme and amendment, accepted FT00–FT03 records, all FT04 contracts and prior review records, and current FT04 code, tests, lock, lock digest, audit, and ignored local model states.

Review the current branch through remediation commit `f838ff87bd2d0acf0d77cbf02e1f496acc680118`. Inspect actual files, diffs, Git history, and test evidence independently.

## Required checks

1. Reassess the entire original FT04 contract and all prior blocking findings.
2. Verify the accepted-review gate requires and validates the exact canonical `FT04_lock_sha256.json` file SHA-256 marker.
3. Verify the accepted-review gate requires `FT04 reviewed remediation commit` to equal exactly `7e509690789d52df78573f8da89606ce1da43252`, rejects `624789feac69d002587d6e79b4ff0b7810d66055` and other valid ancestors, and still validates commit ancestry and declared files.
4. Verify current runner, lock bytes, digest, feature-table binding, W_Original accepted-asset binding, R candidate hashes, canonical FT05 paths, full FT05A prerequisite validation, and outcome gate are mutually consistent and fail closed.
5. Confirm all seven model-state hashes and scientific contents remain unchanged and reloadable.
6. Confirm no B source/data/outcome was read, no real FT05A/FT05B/FT06 artifact exists, B stays locked, and the formal model lock stays absent.
7. Inspect tracked files for identifiers, patient-level values, private paths, secrets, unexpected large files, unrelated changes, and formal contamination.
8. Run FT04 plus FT03/FT02/W07 tests and FT04 lock validation through `tools/run_t2_radiomics.ps1` using `environment.yml` `t2_radiomics`. Every Python execution must use this wrapper.

Apply the downstream contamination criterion; do not reject for style.

## Disposition and canonical review

Return exactly one:

- `accepted for downstream use`;
- `accepted with nonblocking findings`;
- `not accepted for downstream use`.

Update only the canonical `prognosis_analysis/ft/FT04_review.md` to the current fourth-round disposition. Git history preserves previous rounds.

If accepted, independently compute and include the exact marker syntax required by `ft04_runner.py` for independent acceptance, lock identity, serialized lock SHA-256, canonical digest-file SHA-256, current FT04 runner SHA-256, and reviewed remediation commit `7e509690789d52df78573f8da89606ce1da43252`. Run an actual wrapper validation showing the canonical review passes the production review gate without any real B access.

Include concise evidence, test results, closure of all prior blockers, blocking/nonblocking findings, and downstream decision. Do not expose patient identifiers or sensitive paths.

Stage and commit only `prognosis_analysis/ft/FT04_review.md` on `codex/ft-validation`. Do not push. Do not touch/stage the FT01 manifest indication or orchestration directory.

## Final response

Return only the disposition, closure status, essential evidence/findings, wrapper results, local review commit, confirmation no push was attempted, and any blocker. Do not start FT05A.
