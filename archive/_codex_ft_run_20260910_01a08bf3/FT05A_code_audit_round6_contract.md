# FT05A Pre-run Code Reviewer Contract — Round 6

## Role and isolation

- You are the fresh independent top-level Reviewer for the completed FT05A exact-output-root remediation, using `gpt-5.6-sol` with medium reasoning.
- You are already the Reviewer for this unit. You MUST NOT create, open, fork, spawn, delegate to, request, or invoke any additional conversation, session, thread, subagent, child agent, nested agent, delegated agent, internal agent, Worker, Reviewer, or equivalent descendant.
- Do not further delegate. Complete this review inside this conversation; if impossible, return the blocker.
- Review only. Do not repair code, run real FT05A, access real B, or execute later modules.
- Do not report progress. Return only after review and the report-only local commit are complete, unless runtime exceeds one hour.

## Sources and environment

- Read repository `AGENTS.md`, FT scheme/amendments, accepted FT03/FT04 artifacts, the prior FT05A canonical audits and relevant contracts, remediation commit `e7a231c`, and actual current code/tests.
- Treat the pasted opinion based on obsolete commit `6d30aecc...` as non-authoritative history; independently inspect current artifacts.
- Every Python command MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`.
- Static inspection and synthetic fixtures only. Do NOT enumerate, locate, read, hash, copy, or write real B assets, identifiers, clinical/outcome data, or real FT05 manifests.

## Review scope

- Reproduce the fifth-round lexical-alias probes and verify relative paths, dot segments, parent-normalized paths, trailing-dot/space forms where applicable, slash variants if noncanonical, case variants, descendants, parents, junction/reparse aliases, and any other non-exact spelling are rejected before processor/source/W_Original/owner/state/output side effects.
- Verify the accepted spelling is the single literal absolute canonical constant and all downstream paths derive from that internal constant rather than caller text.
- Confirm reparse-resolution protections remain intact.
- Reassess all previously closed FT05A pre-run controls sufficiently to detect regression: frozen FT04 prerequisite, audit binding, technical-only/outcome isolation, no B fitting, frozen A boundary/PyRadiomics, W_Original provenance, one-to-one sources, pilot/resume, global ownership, finalization recovery, manifest/table/artifact provenance, structural states, and accepted-state regression.
- Judge whether the one Windows symlink permission skip is non-blocking based on equivalent code path and available junction/reparse evidence.

## Verdict and deliverable

- Use exactly `PASS`, `PASS_WITH_FINDINGS`, or `FAIL`; only the first two authorize a later real-B execution Worker.
- If not `PASS`, provide concrete findings but do not repair.
- Replace/update `prognosis_analysis/ft/FT05A_code_audit.md` with round-6 evidence and verdict, deidentified and without local absolute paths or patient-level data.
- Commit only the canonical report locally. Do not push or stage unrelated/local/control-store/FT01-manifest changes.

## Completion criteria

Complete only when independent wrapper-based review is finished, privacy boundaries are preserved, the verdict is explicit, and the report-only local commit exists.
