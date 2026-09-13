# FT00 remediation contract

## Role and boundary

Remediate exactly FT00 after the first Reviewer rejected it. Do not execute FT01–FT06.

Worker session constraints:

- This is a new independent Worker session. Do not create, open, spawn, delegate to, or request any other conversation, session, thread, subagent, child agent, nested agent, or equivalent.
- Complete the remediation in this session; if impossible without delegation, stop and return the blocker.
- Work locally in `<LOCAL_PATH>`.
- All Python execution, if needed, must use `tools/run_t2_radiomics.ps1 -PythonArguments ...` with the `t2_radiomics` environment defined by `environment.yml`; do not use arbitrary Python or direct conda commands.

## Reviewer findings to remediate

1. The FT00 comparison set must match the scheme exactly: M0 vs M1; M0 vs M2; M2 vs M3L; M2 vs M3H; M2 vs M4; M3L vs M3H; M4 vs M5. For each comparison record the common eligible population; M4 vs M5 uses the intersection with both dual-radiomics and W available.
2. FT must be isolated on a dedicated branch/worktree/output namespace. The existing FT00 commit was placed on and pushed to `main`. Use a recoverable Git operation to move the accepted FT work onto a dedicated `codex/ft-validation` branch based on the pre-FT baseline `88ffcda16b8ba16324f6824637490d5bc1652ef8`, and remove the FT00 artifact change from `main` without destructive history rewriting. Preserve unrelated user work and the untracked scheme/contract files.

## Required checks

- Reconcile both FT00 artifacts and all comparison metadata with the scheme.
- Verify the dedicated FT branch contains FT00 deliverables and is the branch for all later FT units.
- Verify `main` no longer contains the FT00 artifact content after a recoverable revert/removal operation; do not rewrite published history.
- Re-verify source hashes, existing technical lock, frozen W07 repeat-1 split reference, locked environment, formal W08/L9 state, and B access flags.
- Keep formal `prognosis_analysis/model_freeze_lock.json` absent, B data unread, and formal outputs untouched.

## Required deliverables

- Corrected `prognosis_analysis/ft/FT00_protocol.json`
- Corrected `prognosis_analysis/ft/FT00_isolation_audit.md`
- Git evidence showing the dedicated FT branch/worktree and the safe main-branch cleanup.

## Acceptance criteria

- FT00 is internally consistent with the scheme and reviewer findings.
- No patient-level or sensitive data is added to tracked files.
- No later FT unit is executed.
- The dedicated FT branch is the only downstream handoff branch for this run.
