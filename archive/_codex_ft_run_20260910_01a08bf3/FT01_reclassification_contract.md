# FT01 reclassification contract

## Role and boundary

Reconcile the existing FT01 audit with the approved FT protocol amendment dated 2026-09-11. Execute only FT01. The amended rule is that B habitat radiomics are historically `NOT_YET_GENERATED` and are intentionally deferred to one-time outcome-blind FT05A after FT04 model freeze; this state does not block A-only FT02–FT04. Do not execute FT02–FT06 in this session.

Worker session constraints:

- This is a new independent Worker session. Do not create, open, spawn, delegate to, or request any other conversation, session, thread, subagent, child agent, nested agent, or equivalent.
- Complete this unit in the current session; if impossible without delegation, stop and return the blocker.
- Work locally in `<LOCAL_PATH>` on `codex/ft-validation`.
- All Python execution must use `tools/run_t2_radiomics.ps1 -PythonArguments ...` with the `t2_radiomics` environment from `environment.yml`; do not use arbitrary Python or direct conda commands.

## Required work

1. Read the updated FT scheme and `prognosis_analysis/ft/FT_protocol_amendment_20260911.json` as the effective FT01 authority, plus FT00 and existing FT01 artifacts.
2. Verify A/full_A technical assets, frozen habitat parameters, R_low/R_high candidate hashes, existing W_Original 107-feature asset, canonical order, and provenance.
3. Verify B W_Original schema/provenance at the technical level without reading B outcome, and register B R_low/R_high as `NOT_YET_GENERATED` rather than a failure. Confirm the new scheme authorizes A-only FT02–FT04 and defers B habitat generation to FT05A after FT04 freeze.
4. Keep W_Original Original-only; Wavelet, LoG, and all other filtered whole-tumor features remain excluded.
5. Confirm no B imaging-level processing, B K-means, B PyRadiomics, model fitting, or outcome access occurred in FT01.
6. Preserve formal W08/L9 state/locks and commit/push only in-scope FT01 reconciliation artifacts and minimal audit helper changes.

## Required deliverables

- Updated `prognosis_analysis/ft/FT01_asset_manifest.json`
- Updated `prognosis_analysis/ft/FT01_asset_audit.md`
- Minimal audit helper updates only if needed
- Evidence that `FT02_ready=true` authorizes only A-only FT02–FT04

## Acceptance criteria

- FT01 conclusion is exactly `FT01_A=PASS`, `FT01_B_habitat_assets=NOT_YET_GENERATED`, `FT01_overall=PARTIAL_PASS`, with `FT02_ready=true`.
- The former missing-B-assets fail-closed interpretation is not retained as the effective FT01 state.
- No B outcome or B imaging-level extraction is performed.
- No formal W08/L9 outputs or locks are changed.
