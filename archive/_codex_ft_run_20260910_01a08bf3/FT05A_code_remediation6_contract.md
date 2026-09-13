# FT05A Code Remediation Worker — Round 6

## Role and isolation

- You are the fresh independent top-level Worker for the existing FT05A pre-run remediation unit, using `gpt-5.6-luna` with xhigh reasoning.
- You are already the Worker for this unit. You MUST NOT create, open, fork, spawn, delegate to, request, or invoke any additional conversation/session/thread, subagent, child/nested/delegated/internal agent, Worker, Reviewer, or equivalent descendant.
- Do not further delegate. Complete this unit inside this conversation or return the blocker. Do not act as Reviewer or Orchestrator.
- Do not report progress. Return only after implementation, verification, and local commit, unless runtime exceeds one hour.

## Sources, environment, and privacy

- Read repository `AGENTS.md`, FT scheme/amendments, accepted FT03/FT04 artifacts, all relevant FT05A contracts/audits, current implementation/tests, and round-6 audit commit `16a395b6a05a310f3ec0c50d36a81a0cd0829740` reviewing implementation commit `e7a231c2f4eed0f57abb11613d98dd0f2b068291`.
- Every Python command MUST use repository `environment.yml` environment `t2_radiomics` through `tools/run_t2_radiomics.ps1`.
- Static/synthetic fixtures only. Do NOT enumerate, locate, read, hash, copy, or write real B assets, identifiers, technical rows, clinical/outcome data, or real FT05 manifests. Do not run real FT05A or later modules.

## Authorized remediation only

Fix the single round-6 production-default namespace defect:

- Make the canonical tracked paths for `FT05_B_feature_manifest.json`, `FT05A_code_audit.md`, and `FT05A_B_technical_generation_audit.md` pass namespace validation on Windows.
- Apply one consistent path-normalization representation to both the tested candidate and the trusted canonical-artifact set; do not compare normalized set members to an unnormalized candidate.
- Preserve exact-path admission: only the three intended canonical tracked files may use this branch. Case variants, relative forms, dot segments, parents, descendants, alternate filenames, junction/symlink/reparse aliases, and normalized-but-lexically-different spellings must remain rejected before side effects.
- Do not loosen the exact literal `CANONICAL_OUTPUT_ROOT` gate or any technical-source/formal-directory restriction.
- Add production-default synthetic tests using the actual canonical constants, plus negative alias/case/path variants, instrumented to prove failure occurs before any B technical side effect.
- Preserve all previously accepted controls and scientific definitions.

## Verification and Git

- Run focused FT05A tests, relevant FT04+FT05A tests, accepted-state regression, FT05A static validation, and FT04 lock validation through the wrapper.
- Modify only FT05A implementation/tests necessary for this defect. Do not edit the canonical Reviewer report.
- Commit scoped project-safe code/tests locally. Do not push or stage unrelated/local/control-store/FT01-manifest changes.

## Completion criteria

Complete only when all three production-default canonical artifact paths pass, every non-exact variant fails before side effects, relevant regressions pass, FT04 remains `VALID`, no real B asset was touched, and a scoped local commit exists.
