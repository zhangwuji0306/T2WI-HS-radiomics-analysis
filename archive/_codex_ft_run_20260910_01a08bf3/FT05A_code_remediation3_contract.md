# FT05A Code Remediation Worker — Round 3

## Role and isolation

- Act as a fresh top-level FT05A remediation Worker using `gpt-5.6-luna` with xhigh reasoning.
- This is a leaf task. You MUST NOT create, fork, delegate to, or start any session, thread, subagent, descendant, Worker, or Reviewer.
- Limit work strictly to the two residual blockers in the round-3 audit. Do not access real B, execute real FT05A, or perform later modules.
- Do not report progress. Return only after implementation, verification, and local commit, unless runtime exceeds one hour.

## Sources, environment, and privacy

- Read repository `AGENTS.md`, FT scheme/amendments, accepted FT00–FT04 records, all FT05A contracts/audits, current code/tests, and implementation commit `d0c59b07b8347dedc7fd04a7e2d08dd4f98a9616`.
- Every Python command MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`.
- Static and synthetic fixtures only. Do NOT enumerate, locate, read, hash, copy, or write real B assets, identifiers, clinical/outcome data, or real FT05 manifests.

## Required remediation

1. Eliminate manifest self-authorization of `W_Original`. The canonical validator must independently derive and enforce the accepted FT01/FT04 W_Original asset path, SHA-256, feature order, schema, and row bindings. A manifest-provided path/hash cannot become its own trust root. Reject every alternate or disallowed provenance path, including `feature_extract/output`, even if hashes and internal identities are made self-consistent.
2. Enforce one-to-one persisted source mapping at the canonical manifest boundary. Reject duplicate/reused `image_path`, `roi_path`, `source_image_key`, `source_roi_key`, source hashes where uniqueness is required by the source contract, case identities, patient IDs, or any cross-row mapping that could represent duplicate extraction or patient/source aliasing.

Add adversarial synthetic tests reproducing both accepted round-3 probes and proving rejection. Preserve all previously closed controls and technical-only semantics.

## Verification and Git

- Run focused FT05A, FT04+FT05A, and accepted-state regressions through the wrapper; run static validation and confirm FT04 lock remains `VALID`.
- Modify only code/tests required for these two findings; do not edit the canonical Reviewer report.
- Commit scoped project-safe changes locally; do not push.
- Do not stage unrelated files, local output, control-store files, or `prognosis_analysis/ft/FT01_asset_manifest.json`.

## Completion criteria

Complete only when both adversarial probes fail closed, all relevant regressions pass, privacy boundaries are preserved, and the scoped local commit exists.
