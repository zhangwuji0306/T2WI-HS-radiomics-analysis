# FT05A Code Remediation Worker — Round 4

## Role and isolation

- Act as a fresh top-level FT05A remediation Worker using `gpt-5.6-luna` with xhigh reasoning.
- This is a leaf task. You MUST NOT create, fork, delegate to, or start any session, thread, subagent, descendant, Worker, or Reviewer.
- Limit work strictly to the round-4 output-root/ownership blocker. Do not access real B, execute real FT05A, or perform later modules.
- Do not report progress. Return only after implementation, verification, and local commit, unless runtime exceeds one hour.

## Sources and environment

- Read repository `AGENTS.md`, FT scheme/amendments, accepted FT00–FT04 records, all FT05A contracts/audits, current code/tests, and commit `c8682c4d6f321ff17a1f02cab3fe555805eb4f92`.
- Every Python command MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`.
- Static/synthetic fixtures only. Do NOT enumerate, locate, read, hash, copy, or write real B assets, identifiers, clinical/outcome data, or real FT05 manifests.

## Required remediation

- Enforce exactly one immutable canonical FT05A output/run namespace. Caller-supplied descendants, aliases, symlink/junction escapes, case variants, relative variants, or alternate roots must not create independent owner/state/artifact/staging/table namespaces.
- Make the ownership/run identity global to that exact canonical FT05A run so the same cohort/case cannot be piloted or extracted twice through alternate paths.
- Add an adversarial synthetic regression reproducing two descendant-root invocations and prove the second is rejected before processing; cover path normalization/alias cases appropriate to Windows.
- Preserve all prior accepted controls and the technical-only boundary.

## Verification and Git

- Run focused FT05A and accepted-state combined regressions, static validation, and FT04 lock validation through the wrapper.
- Modify only code/tests necessary for this blocker; do not edit the canonical Reviewer report.
- Commit scoped project-safe changes locally; do not push or stage unrelated/local/control-store/FT01-manifest changes.

## Completion criteria

Complete only when alternate output namespaces fail closed before extraction, relevant regressions pass, privacy boundaries are preserved, and a scoped local commit exists.
