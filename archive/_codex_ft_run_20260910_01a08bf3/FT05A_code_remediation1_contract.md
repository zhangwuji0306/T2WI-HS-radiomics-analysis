# FT05A Code Remediation Worker — Round 1

## Role and isolation

- Act as a fresh, top-level FT05A remediation Worker using `gpt-5.6-luna` with xhigh reasoning.
- This is a leaf task. You MUST NOT create, fork, delegate to, or start any session, thread, subagent, descendant, Worker, or Reviewer.
- Work only on the FT05A code-preparation/pre-run gate. Do not access real B assets, do not execute real FT05A, and do not perform FT05B or later work.
- Do not report progress. Return only after implementation, verification, and local commit are complete, unless runtime exceeds one hour.

## Required sources

Read and follow repository `AGENTS.md`, the FT scheme and amendments, accepted FT00–FT04 records, `_codex_ft_run_20260910_01a08bf3/FT05A_code_prep_contract.md`, `prognosis_analysis/ft/FT05A_code_audit.md`, commit `7ddc4458f11fd631173e3778bd2a1ac518f74143`, and the current FT05A/FT04 implementation and tests.

## Environment and privacy boundary

- Every Python invocation MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`; do not invoke Python directly.
- Use static inspection and synthetic fixtures only.
- Do NOT enumerate, locate, read, hash, copy, or write real B images, ROIs, features, clinical data, outcomes, identifiers, or manifests derived from real B assets.
- Do not generate the real `FT05_B_feature_manifest.json`.

## Required remediation scope

Implement the first Reviewer's limited remediation plan completely and minimally:

1. Put cohort loading and every B technical read behind one fail-closed preflight. Bind the accepted code-audit record to the exact runner SHA-256, reviewed commit, and contract identity.
2. Replace self-relative path checks with fixed canonical FT05A output roots and exact technical source-root contracts. Reject resolved containment in formal, A, FT03, FT04, W08, L9, and other disallowed namespaces.
3. Preserve FT05A as technical-only. Reconcile its output/manifest with the accepted downstream consumer by deferring the nine clinical predictors to the later authorized join. Add an end-to-end synthetic contract test proving the actual FT05A technical manifest/table is accepted by the correct canonical downstream technical validator; do not expose B outcomes or clinical predictors to FT05A.
4. Add exclusive run ownership with atomic creation. Cryptographically bind each case artifact to its exact input hashes, W_Original row, processor result, flattened row, and schema. Reject mismatch. Test concurrent start, interrupted write, tampering, pilot resume, and completed-run refusal.
5. Implement and test frozen structural-absence and technical-small-ROI states in the production processor, including PyRadiomics 3.0.1 minimum-size boundary behaviour, without imputation or silent substitution.
6. Pilot mode may hash/read only selected pilot sources. Its completed artifacts remain part of the same canonical one-time run; remaining sources are hashed only on resume.
7. Make finalization a recoverable, explicitly ordered atomic state transition. Update the stale FT04 review-absence test so the combined accepted-state regression passes.

Keep all previously passing frozen-boundary, no-refit, candidate/order-hash, PyRadiomics-configuration, W_Original-reuse, duplicate-rejection, outcome-denylist, and resume guarantees intact.

## Verification

- Run focused and relevant regression tests only through the required wrapper.
- Include synthetic negative tests for every remediated failure mode.
- Validate the FT04 lock remains `VALID`.
- Ensure no real B asset was touched and no formal analysis directory was written.

## Deliverable and Git scope

- Modify only FT05A/FT04 code and tests strictly necessary for this remediation.
- Do not modify `prognosis_analysis/ft/FT05A_code_audit.md`; it remains the immutable first-round review record until the next independent Reviewer writes the canonical result.
- Create a deidentified tracked remediation audit if needed, but do not include patient rows, local absolute paths, or ephemeral control files.
- Commit only scoped project-safe files locally. Do not push.
- Do not stage unrelated changes, local outputs, the ephemeral control store, or the pre-existing stat-only `prognosis_analysis/ft/FT01_asset_manifest.json` worktree entry.

## Completion criteria

Complete only when all seven remediation items are implemented, focused and combined regressions pass, the FT04 lock remains valid, privacy boundaries were preserved, and a scoped local commit was created.
