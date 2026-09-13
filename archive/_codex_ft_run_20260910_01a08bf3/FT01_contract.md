# FT01 contract

## Role and boundary

Execute only FT01 of `T2WI-HS 生境预后快速验证（FT）方案书.md`: A/B existing asset and frozen full_A habitat audit. FT00 has been accepted for downstream use on `codex/ft-validation`.

Worker session constraints:

- This is already the independent Worker session. Do not create, open, spawn, delegate to, or request any other conversation, session, thread, subagent, child agent, nested agent, or equivalent.
- Complete only FT01; if it cannot be completed without delegation, stop and return the blocker.
- Work locally in `<LOCAL_PATH>` on the existing `codex/ft-validation` branch.
- All Python execution must use `tools/run_t2_radiomics.ps1 -PythonArguments ...` with the `t2_radiomics` environment from `environment.yml`; do not use arbitrary Python or direct conda commands.

## Authoritative inputs and accepted prerequisite

- FT scheme, `PROJECT_STATUS.md`, `项目说明.md`, current execution SOP/master protocol, and `prognosis_analysis/ft/FT00_protocol.json`.
- Accepted FT00 output and its source locks.
- Existing frozen full_A habitat assets, A technical cohort, A global descriptors, W02/W03 A feature assets, candidate freeze/schema/manifests, and existing B technical feature assets only as needed to verify provenance/schema.

## Required work

### A audit

Verify, without re-running extraction or optimization:

- full_A habitat, centers/boundary, SLIC 4 mm, K=2, `n_init=100`;
- C/H/G definitions;
- R_low=49 and R_high=10 with exact candidate hashes;
- W_Original existing whole-tumor Original feature asset and schema; Wavelet and LoG/other filtered features are excluded from FT;
- A IDs, row counts, feature names/order, availability and manifest provenance.

### B technical audit

Use only existing B technical feature assets and metadata/provenance. Do not read B DFS/OS/CSS, clinical outcome fields, or any B performance/validation result. Do not run B MRI preprocessing, SLIC, K-means, PyRadiomics, feature selection, imputation/scaling estimation, or model fitting.

Verify where available:

- B patient-ID schema without exposing identifiers in tracked deliverables;
- feature names and order;
- R_low/R_high/W_Original availability;
- candidate hashes;
- radiomics configuration provenance;
- compatibility of the existing B habitat feature definition with the FT full_A frozen definition.

If the required B technical assets cannot be inspected under the existing access boundary, or are incompatible, fail closed and document the exact reason. Do not bypass the boundary or re-extract B radiomics.

## Authorized writes

- `prognosis_analysis/ft/FT01_asset_manifest.json`
- `prognosis_analysis/ft/FT01_asset_audit.md`
- Minimal FT-only schema/provenance helper code/tests if necessary; no unrelated edits.
- No B patient-level content, raw IDs, absolute paths, clinical/outcome tables, or sensitive data in tracked files.

## Acceptance criteria

- A and B technical provenance/schema conclusions are directly supported by observable local evidence.
- Full_A and candidate definitions exactly match FT00 and the scheme.
- B outcome remains unread; no B extraction or optimization occurs.
- Existing technical assets are either compatible and ready for FT02/FT05, or the result is an explicit fail-closed blocker.
- Formal W08/L9 state and locks remain unchanged.
