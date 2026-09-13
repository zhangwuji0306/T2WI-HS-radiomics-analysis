# FT05A Code Remediation Worker — Round 2

## Role and isolation

- Act as a fresh top-level FT05A remediation Worker using `gpt-5.6-luna` with xhigh reasoning.
- This is a leaf task. You MUST NOT create, fork, delegate to, or start any session, thread, subagent, descendant, Worker, or Reviewer.
- Limit work strictly to the four residual blockers in the round-2 FT05A pre-run audit. Do not access real B, execute real FT05A, or perform FT05B/later work.
- Do not report progress. Return only after implementation, verification, and local commit are complete, unless runtime exceeds one hour.

## Sources and environment

- Read repository `AGENTS.md`, FT scheme/amendments, accepted FT00–FT04 records, all prior FT05A contracts, the current `prognosis_analysis/ft/FT05A_code_audit.md`, remediation commit `35f873ac8333f4f8c0e8e770b87a79e36635d4da`, and current FT05A/FT04 code/tests.
- Every Python invocation MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`; never invoke Python directly.
- Static and synthetic fixtures only. Do NOT enumerate, locate, read, hash, copy, or write real B assets, identifiers, clinical/outcome data, or real FT05 manifests.

## Required remediation

1. Make `FINALIZING` recovery fail-closed: constrain every transaction source/target to canonical FT05A namespaces; revalidate the technical table, full technical manifest, table/manifest binding, completed-case evidence, W_Original binding, and transaction contents before install or `COMPLETED`; reject any mutable-state inconsistency. Add synthetic tamper and interrupted-transition tests.
2. Make the canonical technical-manifest validator cryptographically and semantically bind every source record: exact allowlisted root containment, referenced-file hash where applicable, recomputed case identity, one-to-one table-row correspondence, patient/case ordering, and exact W_Original asset/row binding. Reject formal/disallowed paths and forged hashes/identities. Add end-to-end tamper tests.
3. Correct audit binding so the required report-only commit does not invalidate an otherwise unchanged reviewed implementation. Require an explicit independent-review marker, exact reviewed implementation commit, exact runner SHA-256 and contract identity; prove the reviewed implementation is the relevant unchanged code state/ancestor while permitting only the canonical audit-report commit afterward. Reject intervening code changes, forged free text, and stale runner hashes.
4. Ensure pilot reads/hashes only selected technical sources, including selected W_Original rows. Use a bounded/streamed selection strategy that does not materialize or hash the complete B W_Original asset during pilot. Preserve the exact whole-asset and row binding required when the canonical run resumes/finalizes, without recomputing pilot extraction. Add instrumentation-based synthetic tests proving no unselected W_Original row is read during pilot.

Preserve all previously closed controls and keep FT05A technical-only.

## Verification, deliverable, and Git

- Run focused and accepted-state combined tests through the wrapper, plus FT04 lock/static validation.
- Update only implementation/tests necessary for this limited remediation; do not rewrite the Reviewer report.
- Commit only scoped code/tests locally. Do not push.
- Do not stage unrelated files, local output, control-store files, or the pre-existing `prognosis_analysis/ft/FT01_asset_manifest.json` worktree entry.

## Completion criteria

Complete only when all four blockers are closed with synthetic regression evidence, prior controls remain passing, privacy boundaries are preserved, and a scoped local commit exists.
