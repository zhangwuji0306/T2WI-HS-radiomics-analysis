# FT05A Pre-run Code Reviewer Contract — Round 5

## Role and isolation

- Act as the independent fifth-round FT05A pre-run code Reviewer using `gpt-5.6-sol` with medium reasoning.
- This is a fresh top-level leaf task. You MUST NOT create, fork, delegate to, or start any session, thread, subagent, descendant, Worker, or Reviewer.
- Review only; do not repair, access real B, run FT05A, or perform later modules.
- Do not report progress. Return only after review and local report-only commit, unless runtime exceeds one hour.

## Sources, environment, and privacy

- Read repository `AGENTS.md`, FT scheme/amendments, accepted FT00–FT04 records, all FT05A contracts/audits, current code/tests, and remediation commit `a5351b7dfcd2721aed0fdca3b4430aa10788a736`.
- Every Python command MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`.
- Static inspection and synthetic fixtures only. Do NOT enumerate, locate, read, hash, copy, or write real B assets, identifiers, clinical/outcome data, or real FT05 manifests.

## Review scope

- Reproduce the round-4 alternate-descendant-root attack and verify every non-exact output root, relative/case-normalized alias, and available Windows reparse/symlink alias fails before ownership creation or extraction.
- Verify one immutable canonical owner/state/artifact/staging/table namespace globally prevents repeated pilot/full extraction.
- Reassess the complete FT05A pre-run gate and all previously closed controls, including W_Original trust binding, source uniqueness, audit binding, preflight order, manifest/table provenance, finalization recovery, pilot/resume, structural states, outcome isolation, no B fitting, frozen boundary/PyRadiomics, and accepted-state regression.
- Treat a platform-permission test skip according to whether equivalent fail-closed path-resolution logic and non-privileged adversarial coverage provide sufficient evidence; document the judgment.

## Verdict and deliverable

- Use exactly `PASS`, `PASS_WITH_FINDINGS`, or `FAIL`; only the first two authorize the later real-B execution Worker.
- If not `PASS`, record concrete findings; do not repair.
- Replace/update `prognosis_analysis/ft/FT05A_code_audit.md` with round-5 evidence and verdict, deidentified and without local absolute paths or patient-level data.
- Commit only the canonical report locally. Do not push or stage unrelated/local/control-store/FT01-manifest changes.

## Completion criteria

Complete only when independent wrapper-based review is complete, privacy boundaries are preserved, the verdict is explicit, and the report-only local commit exists.
