# FT00 protocol amendment contract

## Role and boundary

Apply and verify the user's explicit FT protocol amendment: whole-tumor radiomics block `W` is Original-only; Wavelet, LoG, and other filtered features are excluded for consistency with habitat radiomics. This supersedes the earlier FT00 W definition. Execute only this FT00 amendment; do not execute FT01–FT06.

Worker session constraints:

- This is a new independent Worker session. Do not create, open, spawn, delegate to, or request any other conversation, session, thread, subagent, child agent, nested agent, or equivalent.
- Complete the amendment in this session; if impossible without delegation, stop and return the blocker.
- Work locally in `<LOCAL_PATH>` on `codex/ft-validation`.
- All Python execution, if needed, must use `tools/run_t2_radiomics.ps1 -PythonArguments ...` with the `t2_radiomics` environment from `environment.yml`; do not use arbitrary Python or direct conda commands.

## Required work

1. Verify the current scheme file contains the amendment and that it is reflected consistently in `prognosis_analysis/ft/FT00_protocol.json`, the FT00 isolation audit, and the active FT01 contract.
2. Ensure M5 is represented as `C + W_Original`, and the M4 vs M5 population is the intersection of dual-radiomics and W_Original availability.
3. Ensure no FT code/config/contract still silently treats Wavelet, LoG, or other filtered whole-tumor features as part of W. Do not broaden scope to redesign unrelated modeling code.
4. Re-verify existing habitat/candidate locks, A/B boundary, formal W08/L9 state, B access flags, and absence of `prognosis_analysis/model_freeze_lock.json`.
5. Commit and push only the protocol-amendment artifacts and any minimal FT-scoped metadata needed for later units. Preserve the untracked scheme/contract files and all unrelated changes.

## Required deliverables

- Updated `prognosis_analysis/ft/FT00_protocol.json`
- Updated `prognosis_analysis/ft/FT00_isolation_audit.md`
- Updated FT01 contract evidence if needed
- A concise audit of the amendment and its validation

## Acceptance criteria

- The W definition is Original-only everywhere in the FT protocol surface.
- The amendment does not change full_A habitat, candidate pools, endpoints, splits, alpha, or other FT parameters.
- No B outcome or B re-extraction is performed.
- Formal W08/L9 outputs and locks are untouched.
- The dedicated FT branch remains the downstream handoff branch.
