# FT00 contract

## Role and boundary

Execute only FT00 of `T2WI-HS 生境预后快速验证（FT）方案书.md`: isolation and protocol freeze. This is a new exploratory FT branch, independent of formal L9/W08. Do not execute FT01 or any later unit.

Worker session constraints:

- This is already the independent Worker session. Do not create, open, spawn, delegate to, or request any other conversation, session, thread, subagent, child agent, nested agent, or equivalent.
- Complete the unit in this session; if impossible without delegation, stop and return the blocker.
- Use the local project at `<LOCAL_PATH>` and only the project-native files/data needed for FT00.
- All Python execution must use the locked `t2_radiomics` environment declared by `environment.yml` through `tools/run_t2_radiomics.ps1 -PythonArguments ...`; do not call an arbitrary Python executable or `conda run` directly.

## Authoritative inputs

- `T2WI-HS 生境预后快速验证（FT）方案书.md`
- `PROJECT_STATUS.md`
- `项目说明.md`
- `T2WI-HS-radiomics-analysis Pre-W08 整改、协议补丁与后续 A-only 建模分包工作流.md`
- `T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书.md`
- Existing project locks/configs/status, including `habitat_analysis/freeze_lock.json`, `prognosis_analysis/modeling_protocol.json`, `prognosis_analysis/execution_status.json`, and W07 frozen split assets.

## Required decisions and checks

1. Establish a clearly FT-scoped output namespace under the project-native local output area; do not modify formal W08/L9 outputs, locks, or B access state.
2. Record baseline repository HEAD and the exact source/protocol/config references needed for reproducibility.
3. Freeze the FT contract exactly as the scheme specifies: full_A habitat; existing A/B feature assets; W_Original as the whole-tumor Original feature block only (Wavelet and LoG/other filtered features excluded); R_low=49; R_high=10; M0, M1, M2, M3L, M3H, M4, M5; family=Cox; alpha=1 for high-dimensional models; ordinary single-layer 5-fold CV for A; reuse one pre-frozen W07 fold set (prefer repeat 1); A model freeze before B outcome access; B existing features only; no B re-extraction; exploratory label `exploratory_fullA_habitat_non_nested_validation`.
4. Verify the current project state is compatible with an FT start. If a prerequisite is absent or a lock/data boundary would be violated, fail closed and document the exact blocker rather than inventing a substitute.
5. Define the FT-to-L9 isolation boundary and confirm FT cannot write `prognosis_analysis/model_freeze_lock.json`, formal W08 outputs, or unlock B before FT04.

## Authorized writes

- FT-scoped protocol/audit files required by the scheme.
- FT-scoped output directory and minimal FT scaffolding only when required for later units.
- Project code/tests only if necessary to encode FT isolation/protocol contracts; do not implement modeling here.
- Do not alter unrelated project documents or sensitive source data.

## Required deliverables

- `FT00_protocol.json`
- `FT00_isolation_audit.md`
- Any minimal FT-scoped directory/scaffold required by FT01–FT06, with no patient-level data committed.

## Acceptance criteria

- The two FT00 artifacts are observable and internally consistent.
- The contract matches the scheme and current project locks without changing formal L9/W08 semantics.
- FT output and code boundaries are explicit; B remains locked and `model_freeze_lock.json` remains absent.
- Validation evidence is recorded using the wrapper and locked environment where execution is needed.
- No patient identifiers, raw imaging paths, clinical/outcome tables, patient-level derived files, credentials, or absolute local paths are placed in repository deliverables.
