# FT04 second-review remediation Worker contract

## Role and isolation

You are a new independent top-level Worker for the second FT04 remediation only.

- Required model: `gpt-5.6-luna`; required reasoning: `xhigh`.
- This conversation is already the authorized Worker.
- Do not create/open/spawn/delegate/request any conversation, session, thread, Worker, Reviewer, subagent, child/nested/delegated/internal agent, or equivalent feature.
- Complete the work inside this conversation. If impossible without delegation, return the blocker.
- Do not review your own work, act as Orchestrator, or start FT05A/later modules.
- Return only the final result; no progress updates unless work exceeds one hour.

## Sources and scope

Read and obey `AGENTS.md`, the FT scheme and amendment, accepted FT00–FT03 records, the original FT04 contract, the first and second FT04 review records, both prior FT04 contracts, commits `8bc0bb0c3fee67b1c81c35cef1aec30ca22a812d` and `a084a0bd5dd5f0fcb92c189ed01eb2fc4fd53674`, and the current FT04 code/lock/audit/tests/local model states.

The current second-round review is `not accepted for downstream use` in `prognosis_analysis/ft/FT04_remediation_review.md` at commit `31e15f4b1aa22677c894184e44b7d50dba3d5ccd`. Remediate only its three blocking findings. Do not change the seven fitted models or scientific results unless a demonstrated inconsistency requires it.

Do not touch or stage the pre-existing FT01 manifest working-tree indication or the orchestration control directory.

## Required remediation

1. **Bind prediction input to the canonical manifest table**
   - Production `predict_b_from_frozen` must not accept an arbitrary caller-provided feature frame as authoritative.
   - It must load the feature table from the exact canonical path recorded by the canonical `prognosis_analysis/ft/FT05_B_feature_manifest.json`, and verify the table file SHA-256, row count, unique patient count, duplicate status, exact ordered columns, required feature values/finite status, and model-specific input schema before prediction.
   - If a frame parameter remains for test/internal use, production must either reject it or independently verify byte/value identity against the canonical table. Prefer a separate explicitly test-only helper for synthetic frames.
   - Reject alternate paths, mismatched hashes, reordered/extra/missing columns, altered values, altered rows, duplicate IDs, or a separately supplied forged frame even when the manifest itself is otherwise valid.

2. **Bind W_Original to the accepted existing asset**
   - Freeze the accepted FT01/FT04 B W_Original asset logical path, exact asset-file SHA-256, ordered 107-feature name hash, and reuse-only status in the FT04 lock/downstream contract, using only already accepted FT01 metadata; do not read B data during this remediation.
   - Future FT05A manifest validation must require exact equality to that frozen existing-asset binding. A self-reported manifest hash or arbitrary synthetic W_Original asset must not satisfy production validation.
   - Keep whole-tumor re-extraction prohibited.

3. **Exact current serialized lock-file hash**
   - Add a non-self-referential exact SHA-256 binding for the current serialized `prognosis_analysis/ft/FT_model_freeze_lock.json`.
   - A valid approach is a separate canonical tracked digest/attestation file that records the exact lock-file SHA-256, while the later independent accepted FT04 review records and validates both the lock hash and its remediation commit. Do not place a self-hash field inside the lock or claim a commit contains itself.
   - Lock validation must require the canonical digest/attestation, verify the exact current lock bytes, verify referenced Git/file identities truthfully, and reject an injected/incorrect digest or mutated lock.
   - Production downstream validation must additionally require the canonical accepted FT04 review record to attest the exact current lock-file SHA-256 and reviewed remediation commit. Tests may use synthetic temporary accepted-review fixtures; do not create a real accepted review yourself.

4. **Tests and audit**
   - Add focused negative tests for forged caller frames, table hash/row/column/value mismatch, arbitrary W_Original assets, self-reported hashes, altered lock bytes, incorrect digest, missing review lock hash, and review commit mismatch.
   - Preserve and rerun all earlier FT04 remediation tests plus FT03/FT02/W07 suites.
   - Update only the FT04 audit and directly affected FT04 code/lock/tests. A separate canonical lock digest/attestation file is authorized if used.
   - Do not create real FT05A/FT05B artifacts or read any B source/data.

## Environment and data boundary

- Every Python execution must use `tools/run_t2_radiomics.ps1` with `environment.yml` `t2_radiomics`. Do not call another Python directly.
- B sources, outcomes, images, features, clinical data, and distributions remain unread.
- No patient identifiers, patient-level values, sensitive paths, or formal outputs may enter tracked files or responses.
- For any expected runtime over 40 minutes, estimate first and obey the project monitoring rule.

## Version control

Stage only directly necessary FT04 remediation files, inspect the staged diff, and create a local commit on `codex/ft-validation`. Do not push. Accumulated push is attempted only after FT04 acceptance.

## Completion and final response

Return only closure status for the three blocking findings, exact wrapper tests and lock validation result, confirmation model-state hashes/scientific content are unchanged, B/formal-lock status, local commit hash, confirmation no push was attempted, and any blocker. Do not start FT05A.
