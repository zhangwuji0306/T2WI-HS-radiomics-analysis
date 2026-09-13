# FT04 third-round Reviewer contract

## Role and isolation

You are the new independent third-round Reviewer for the twice-remediated FT04 module.

- Required model: `gpt-5.6-luna`; required reasoning: `xhigh`.
- This current conversation is already the authorized Reviewer.
- Do not create/open/spawn/delegate/request any additional conversation, session, thread, Worker, Reviewer, subagent, child/nested/delegated/internal agent, or equivalent feature.
- Complete the review inside this conversation. If impossible without delegation, return the blocker.
- You did not execute either remediation. Do not repair implementation artifacts, act as Worker/Orchestrator, or start FT05A/later modules.
- Return only the final review; no progress updates unless work exceeds one hour.

## Sources and review scope

Review only current FT04. Read and obey `AGENTS.md`, the FT scheme/amendment, accepted FT00–FT03 records, the original FT04 contract, both FT04 remediation contracts, the first- and second-round review records, and the actual current FT04 code/lock/digest/audit/tests/local model states.

Relevant commits:

- original FT04: `8bc0bb0c3fee67b1c81c35cef1aec30ca22a812d`;
- first remediation: `a084a0bd5dd5f0fcb92c189ed01eb2fc4fd53674`;
- second-round review: `31e15f4b1aa22677c894184e44b7d50dba3d5ccd`;
- second remediation under review: `7e509690789d52df78573f8da89606ce1da43252`.

Inspect actual artifacts and diffs before using Worker summaries.

## Mandatory checks

1. Reassess the complete original FT04 acceptance contract and confirm seven model-state hashes/scientific content remain unchanged and reproducible.
2. Reassess all findings from the first and second reviews. In particular verify:
   - production prediction is bound to the exact canonical manifest feature table and rejects a distinct caller frame, changed values/rows/columns/order/hash, duplicates, and alternate paths;
   - W_Original is bound to the accepted FT01 existing asset path, exact asset SHA-256, 107-feature order hash, and reuse-only status rather than manifest self-report;
   - canonical `FT04_lock_sha256.json` validates the exact serialized bytes of `FT_model_freeze_lock.json` and rejects mutated lock bytes or an incorrect digest;
   - downstream accepted-review validation requires the exact current lock-file SHA-256, canonical digest SHA-256, current FT04 code SHA-256, and reviewed remediation commit `7e509690789d52df78573f8da89606ce1da43252`;
   - canonical FT05A manifest and FT_B_unlock paths, full FT05A prerequisites, R candidate hashes, accepted code/technical reviews, and B prediction-only/no-fit rules remain fail-closed.
3. Confirm no real FT05A/FT05B/FT06 artifact exists, no B source/outcome/data was read, B remains locked, and the formal model lock remains absent.
4. Inspect tracked changes for privacy, identifiers, sensitive paths, secrets, unexpected large files, unrelated changes, and formal-output contamination.
5. Run FT04 plus FT03/FT02/W07 tests and the FT04 lock validation through `tools/run_t2_radiomics.ps1` using `environment.yml` `t2_radiomics`. Every Python execution must use this wrapper.

Apply the downstream contamination criterion. Do not reject for style.

## Disposition and canonical review record

Return exactly one semantic disposition:

- `accepted for downstream use`;
- `accepted with nonblocking findings`;
- `not accepted for downstream use`.

Update the canonical tracked review record `prognosis_analysis/ft/FT04_review.md` to reflect this third-round current disposition. Git history preserves the first-round record; the current file must represent the current accepted/rejected state and may cite prior review commit hashes concisely.

If and only if the evidence supports acceptance, the canonical review must include the exact markers required by the production review gate, derived from actual files/code rather than copied without verification:

- independent review status;
- accepted semantic disposition;
- current FT04 lock identity SHA-256;
- exact serialized FT04 lock-file SHA-256;
- canonical lock-digest file SHA-256;
- current FT04 runner/code SHA-256;
- reviewed remediation commit `7e509690789d52df78573f8da89606ce1da43252`.

Inspect `ft04_runner.py` and tests for the exact accepted marker syntax, then independently compute and verify every value. Do not modify code/lock/digest/audit/tests.

The review record must also contain concise evidence, wrapper tests, closure status for all prior blockers, blocking/nonblocking findings, and downstream decision. It must contain no patient identifiers, patient-level values, private paths, or internal reasoning.

Stage and commit only `prognosis_analysis/ft/FT04_review.md` on `codex/ft-validation`. Do not push. Do not touch/stage the FT01 manifest working-tree indication or orchestration control directory.

## Final response

Return only the disposition, closure status of prior blockers, essential evidence/findings, wrapper test and lock validation results, canonical review path, local commit hash, confirmation no push was attempted, and any blocker. Do not start FT05A.
