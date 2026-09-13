# FT01 remediation contract

## Role and boundary

Remediate only the FT01 blocker identified by the first Reviewer: determine whether project-native, already-generated, outcome-blind B `R_low`/`R_high` habitat feature tables and complete provenance exist, and if so complete the FT01 compatibility audit. Also make the canonical W_Original feature order explicit. Do not execute FT02–FT06.

Worker session constraints:

- This is a new independent Worker session. Do not create, open, spawn, delegate to, or request any other conversation, session, thread, subagent, child agent, nested agent, or equivalent.
- Complete only this FT01 remediation; if it cannot be completed without delegation, stop and return the blocker.
- Work locally in `<LOCAL_PATH>` on `codex/ft-validation`.
- All Python execution must use `tools/run_t2_radiomics.ps1 -PythonArguments ...` with the `t2_radiomics` environment from `environment.yml`; do not use arbitrary Python or direct conda commands.

## Required work

1. Search only project-native/local allowed asset locations for pre-existing B technical feature tables and provenance. Filename/index/schema discovery is allowed; do not read B clinical/outcome/performance data.
2. If B `R_low`/`R_high` feature tables and provenance exist, verify patient-ID schema, feature names/order, candidate hashes, radiomics configuration, full_A definition compatibility, and W_Original canonical order without exposing patient identifiers in tracked files.
3. If the required B assets are absent or incompatible, record the exact fail-closed blocker. Do not create substitute features, run MRI preprocessing/SLIC/K-means/PyRadiomics, or bypass any B access lock.
4. Ensure FT01 manifest/report define W_Original canonical order consistently with the actual feature table and state that Wavelet/LoG/filtered features are excluded.
5. Preserve formal W08/L9 state and locks; no B outcome read, no B model/validation work.

## Authorized writes

- Update only `prognosis_analysis/ft/FT01_asset_manifest.json`, `prognosis_analysis/ft/FT01_asset_audit.md`, and minimal FT01 audit helper code if needed.
- No patient-level B data, raw IDs, absolute paths, credentials, or unrelated changes in tracked files.

## Acceptance criteria

- The result is either a fully evidenced compatible existing B asset handoff or an explicit fail-closed blocker.
- No B radiomics re-extraction or outcome access occurs.
- W_Original canonical order is explicit and consistent.
- No FT02–FT06 work is executed.
