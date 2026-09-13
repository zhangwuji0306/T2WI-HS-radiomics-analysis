# V2-13 Final Scientific Audit

## 审查结论

本审查对 Primary v2 当前主线、V2-00～V2-12 审查记录、当前 `main` 提交树、Primary v2 方案书、归档引用和两个 immutable tags 进行了独立静态/合成核对。未读取 `prognosis_analysis/output/`、`habitat_analysis/output/`、`feature_extract/output/`、原始影像、ROI、临床/病理/预后原始表、患者级特征/预测/分析结果或 `local_private/image_id_mapping.csv`；未运行真实影像、临床或患者级分析。

科学方法边界本身保持一致：Primary v2 是当前唯一活动的 Primary 预后分析合同，M0–M5、固定 full-A habitat、A-only training-only 验证和 B frozen prediction only 均未发现因观察性能而改变。当前工作树仍不能签发“整改完成/可直接运行”的最终放行结论，原因有二：

1. Windows 工作树的 `core.autocrlf=true` 将 `protocol.json` 读为 CRLF，而 manifest、canonical lock 和 external registration 保存的是 Git LF blob 的 SHA-256。当前 `sha256_file()` 按原始字节计算，导致自身 provenance gate 失败，并连带阻断部分合成 B/registration 测试。
2. 方案书第二十一部分要求“只有 `main` 为长期主分支”，但当前仍有历史本地/远程 `codex/*` refs；本任务明确不删除分支、不修改远程 refs，因此该严格 Git 完成条件未满足。

这两项不证明模型设计或患者级结果错误，但会阻断当前工作树的完整 provenance/外部验证执行放行。受保护 FT04 coefficients、risk predictions 和 metrics 的跨记录 numerical equivalence 仍为 `NOT EVALUATED`，本审查未将其改写为 PASS。

## 审查对象与状态锚点

- 当前分支：`main`；HEAD：`98a7c26788a7f35cf3c7703ee19b7b919993d61c`。
- 重点提交：`33c4f59d2d899a5c5b44de9f60fa37b4ad43be48`（V2-08～V2-12 归档整理）和 `98a7c26788a7f35cf3c7703ee19b7b919993d61c`（Reviewer C 记录）。
- `archive/formal-nested-cv-v1-20260913`：annotated tag，peeled commit `b09306182e072d0d913d8820d849b4da54d7f1ba`。
- `archive/ft-validation-v1-20260913`：annotated tag，peeled commit `3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34`。
- 工作区已有的未跟踪 Primary v2 人类方案书和 `_codex_ft_run_20260910_01a08bf3/` 保持原样，未纳入本次提交。

## 逐项审查

| 项目 | 结论 | 证据 | 下游含义 |
|---|---|---|---|
| 1. Scientific identity | **PASS** | `prognosis_analysis/primary/protocol.json:3-9, 326-382` 固定 `PRIMARY_ANALYSIS_V2`、版本 `2.0` 和活动合同状态；`prognosis_analysis/primary/README.md:3-5`、根目录 `README.md:17-25`、`prognosis_analysis/archive_reference.md:3-28` 均把 Primary v2 指定为当前主线，并将 Formal/FT 定为归档或历史来源。`archive/formal_nested_cv_v1/README.md:3-13` 和 `archive/ft_validation_v1/README.md:3-17` 明确 historical-only。 | 未发现第二个活动 Primary protocol。根目录科学主协议和 Pre-W08 SOP 是上游方法/执行文档，不构成另一个 Primary v2 protocol。未发现 Formal v1 或 FT 作为当前 Primary 输入入口。 |
| 2. No performance-driven redesign | **PASS** | `protocol.json:9-24, 170-240, 416-420` 明确记录换轨理由、`performance_driven_model_redesign=false`、`retain_all_M0_M5=true`，且模型顺序为 M0、M1、M2、M3L、M3H、M4、M5；候选池仍为 `R_low=49`、`R_high=10`、`W_Original=107`。方案书第三部分、第五部分和第十一部分明确禁止按 FT03/FT06 表现删候选或升级冠军模型。活动代码没有读取 FT06 性能指标来选择模型或候选特征。 | 未见因 FT06 结果删除模型、改 candidate pool、调参或重构科学分析。Primary v2 的 post-FT 身份仍需在结果解释中保留，不能把“未因性能重设计”误写成“B 结果前预先指定”。 |
| 3. B integrity | **PASS** | `protocol.json:355-372` 固定 B 顺序与禁用动作；`validate_external.py:40-98,105-197,236-343` 依次校验 registration、FT06 cohort identity、163 行完整基础 frame、模型 runtime identity 后才允许 predict/evaluate，且没有 B fit、lambda tuning、feature selection、cutoff optimization、habitat refit、radiomics candidate re-selection 或 B→A 反馈路径。`run_cv.py:410-495` 只接受 A 验证入口。 | B 不能参与 A 训练或 Primary 模型重拟合。当前实际执行仍会先被 protocol hash gate 拒绝，属于运行时完整性阻断，不改变 B-only/frozen-only 科学边界。 |
| 4. Fixed phenotype | **PASS** | `protocol.json:90-114` 固定 full-A habitat、3D SLIC 4 mm、cross-case K-means、K=2、`n_init=100`，并禁止 CV outer fold、B 和 DFS boundary adjustment 重拟合。`validate_assets.validate_protocol`（`validate_assets.py:326-382`）执行同样约束；`run_cv.fit_outer_cv`（`run_cv.py:320-372`）只消费同一输入 frame，并登记 `outer_validation_used_for_habitat_fit=false`。Primary 入口没有调用 `run_w08_in_memory` 或 fold-specific feature provider。 | CV fold 和 B 不重建 centers、boundary 或 habitat radiomics；同一 frozen full-A phenotype 是当前模型比较的共同定义。 |
| 5. A validation isolation | **PASS** | `validate_assets.py:27-32,643-692` 固定 repeat=1、5 folds、seed=12345，并拒绝 split regeneration；`run_cv.select_lambda`（`run_cv.py:154-235`）只在 outer-training set 的 inner 5-fold 中选择 lambda，`CanonicalPreprocessor.fit` 在训练 frame 上拟合；`fit_outer_cv`（`run_cv.py:320-389`）按 fold 先分训练/验证再拟合，登记所有 outer-validation selection/lambda/habitat flags 为 false。`protocol.json:294-328` 固定 `alpha=1` 与 training-only 操作。当前 `test_synthetic_equivalence` 通过。 | A 的 preprocessing、feature selection、lambda 和高维 alpha 规则满足训练/验证隔离；不应恢复旧 repeated 10×5 或 alpha grid。 |
| 6. External validation | **PASS（科学边界）** | `external_validation_registration.json:21-52` 和 `protocol.json:51-58,355-372` 固定 B frozen prediction only、FT06 authorized B=163（42 events、121 censored），并显式记录技术筛选 B=107 不合并。`validate_external._validate_b_frame_completeness`（`validate_external.py:157-197`）要求实际 predictor frame 恰为 163 行；`test_equivalence.py:255-293` 覆盖 1/162/164 行、重复 ID、错误 attrs、跨 cohort 字段和 B107 身份拒绝。 | 语义上 B=163 与 B=107 已区分且 B 只能使用冻结模型。当前工作树在进入该 B gate 前先因 protocol hash mismatch 失败，故不能把当前环境称为已完成的可执行外部验证 handoff；本审查未读取或重跑患者级 B 结果。 |
| 7. Transparency | **PASS** | `PRIMARY_ANALYSIS_V2_TRANSITION_20260913.md:5-29`、`protocol.json:9-24`、`external_validation_registration.json:29-33` 和 `primary/README.md:5` 均明确：Primary v2 是 `post-FT protocol transition`，FT03/FT06 结果在 promotion decision 时已可见，`retrospective_prespecification_claim=false`；同时保留 pipeline 在 B evaluation 前冻结的区分。 | 结果可作为 frozen framework 下的验证/解释证据，但不能声称 Primary v2 是 B 结果未知时的正式 preregistration。 |
| 8. Archive clarity | **PASS（活动科学路径）** | `archive/formal_nested_cv_v1/README.md`、`archive/ft_validation_v1/README.md`、`prognosis_analysis/archive_reference.md` 和 `V2_08_12_review_C.md:11-52` 将 Formal v1、FT history、W08/R5/R6 记录和 FT evidence 分为历史归档；`README.md`、`项目说明.md`、`PROJECT_STATUS.md` 只将 Primary v2 作为当前主线。`primary/run_cv.py` 未调用旧 `run_w08_in_memory`、fold-specific provider 或旧 W08 orchestrator。 | 旧 repeated 10×5 nested CV、fold-specific habitat reconstruction、Formal W08 R6 remediation 和 FT engineering recovery chain 未作为当前科学流程输入。非阻断维护性注意：`run_cv.py:31-37` 仍通过 `w08_nested_cv` 模块名复用通用 preprocessing/Cox 数值原语；当前 Primary 未调用该模块的旧 W08 orchestration，但若要求文件级彻底移除历史命名，应另行处理，不能在本审查中擅改。 |
| 9. Completion definition | **FAIL（严格完成条件）** | 方案书第二十一部分（`...Primary v2...md:1270-1322`）列出的方法、表型、M0–M5、repeat-1 5-fold、alpha=1/training-only lambda、B freeze、post-FT disclosure、无 FT06 驱动重设计和 README/PROJECT_STATUS 条件均通过静态核对；但“Git：Formal v1/FT 归档，只有 main 为长期主分支”未满足。`git branch -a -vv` 显示本地 `codex/l7-current-code-technical-preflight`、`codex/w00-formal-archive`，以及多个远程历史 `origin/codex/*` refs；两个本地历史分支仍被 linked worktree 占用。另有当前 Windows provenance hash mismatch，导致完整 gate/test suite 不能在当前工作树通过。 | Primary v2 科学基线可以继续作为活动方法，但项目不能在当前状态宣称满足方案书的全部“整改完成”条件。未删除分支或修改远程 refs，符合本任务范围。 |

### 第 9 项完成定义逐条结果

| 方案书条件 | 结论 | 证据摘要 |
|---|---|---|
| 只有一个正式 protocol：Primary Prognostic Analysis v2 | **PASS** | 活动 `protocol.json` 的 ID/version/status 与 README、archive reference 一致；Formal/FT 仅归档。 |
| H-low/H-high 使用固定 full-A definition | **PASS** | 3D SLIC 4 mm、K=2、`n_init=100`、full-A scope 与 refit 禁止项一致。 |
| M0–M5 保持原 FT 预设 | **PASS** | 当前 protocol 与 `validate_assets.MODEL_SPECS` 均为 M0、M1、M2、M3L、M3H、M4、M5。 |
| 固定 repeat-1 5-fold | **PASS** | `OUTER_REPEAT=1`、`OUTER_FOLDS=5`、`validate_split` fail-closed。 |
| LASSO alpha=1、lambda training-only CV | **PASS** | `protocol.json:294-318`、`run_cv.select_lambda` 和 synthetic equivalence 通过。 |
| 最终模型在 B 评价前冻结 | **PASS（metadata/code）** | canonical lock 的 `no_refit=true`、`no_B_tuning=true`，registration 的 `B_prediction_was_frozen_before_B_evaluation=true`；protected runtime numerical identity 仍未评估。 |
| B frozen prediction only | **PASS（科学边界）** | registration allowed sequence 与 forbidden actions、B completeness/runtime identity gate 均存在；当前运行被上游 hash mismatch 阻断。 |
| Primary v2 promotion decision 明确为 post-FT | **PASS** | transition、protocol、registration 均记录 FT03/FT06 visible 和不得追溯 preregistration。 |
| 不因 FT06 删除模型、改变量或 candidate pool | **PASS** | 全部 M0–M5 和 49/10/107 候选规模保持；方案书明确禁止 performance-driven redesign。 |
| Formal/FT 归档且只有 main 为长期主分支 | **FAIL** | archive/tag 条件通过，但历史 local/remote `codex/*` refs 仍存在；不在本任务中删除。 |
| README 与 PROJECT_STATUS 只描述当前 Primary v2 | **PASS** | 两者的当前主线和状态均为 Primary v2；历史内容以归档说明存在，不被列为 active next step。 |

## 运行与静态验证结果

### 通过项

- 当前 Primary v2 六个 Python 模块通过 AST parse；四个活动 JSON 通过 JSON parse。
- Primary v2 contract assertions：协议 ID/version/status、M0–M5、49/10/107、fixed full-A phenotype、repeat-1/5-fold、post-FT timing 全部通过。
- 锁定环境直接运行 `tools/run_t2_radiomics.ps1 -PythonArguments @('-B','prognosis_analysis/primary/test_equivalence.py')`：主 synthetic wrapper 退出码 0；feature order、eligibility、training-only preprocessing、lambda-selection behavior、canonical coefficient repeatability 和 fold metric contract 为 PASS；cross-artifact coefficients/risk predictions/metrics 为 `NOT EVALUATED`。
- 当前版本逐函数 synthetic 结果：`test_synthetic_equivalence`、`test_fail_closed_promotion_metadata`、`test_synthetic_cohort_identity_boundaries`、`test_synthetic_runtime_model_identity_gate` 和 `test_evaluate_frozen_predictions_requires_complete_b_gate` 通过。
- `git diff --check` 通过。
- `git ls-files` 未发现 `local_private/`、`prognosis_analysis/output/`、`habitat_analysis/output/`、`feature_extract/output/` 或 `_codex_ft_run_*`；未发现 CSV/影像/模型二进制等敏感患者级文件进入版本控制。Formal/FT 归档 18 个 JSON 均可解析，递归结构检查未发现患者级 ID、risk/prediction 数组容器。

### 当前失败项及定位

工作树状态：`git config core.autocrlf=true`。`protocol.json` 的工作树字节包含 426 个 CRLF 换行，Git HEAD blob 为 426 个 LF 换行；其内容在换行归一化后相同，但原始 SHA-256 不同：

- Git LF blob / manifest、lock、registration 记录：`8d0e8239558ad9ecd2f5605bc1ecce29ef93f7769452319c3c804cda20b28e89`。
- 当前 Windows 工作树 `sha256_file(protocol.json)`：`db671001c00bbe2eaac1985ebeff1c48f681f99b5a1cb343d0656a23c5dbce3b`。
- `validate_assets.sha256_file`（`validate_assets.py:272-278`）按原始文件字节计算；`validate_evidence_manifest`（`validate_assets.py:747-749`）和 `refit_freeze.validate_canonical_lock`（`refit_freeze.py:172-180`）因此拒绝当前静态 manifest/lock。`validate_external_registration`（`validate_external.py:40-52`）和 `final_report.build_final_report`（`final_report.py:69-75`）依赖同一 gate。

在当前真实工作树、未修改任何 canonical 文件的条件下，8 个 synthetic test functions 中 3 个因该上游 hash mismatch 失败：

- `test_b_frame_completeness_is_bound_to_ft06_denominator`：尚未进入 B=163 completeness 断言即被 manifest hash gate 拒绝。
- `test_external_registration_builder_is_self_consistent`：在 builder 的 canonical lock validation 处因 protocol hash 拒绝。
- `test_evaluate_frozen_predictions_accepts_only_complete_b_frame`：尚未进入 complete B frame evaluation 即被 manifest hash gate 拒绝。

将 protocol bytes 在内存中仅作 CRLF→LF 归一化的诊断 wrapper（不改文件、不写输出、不读取患者数据）后，上述 3 项和其余 5 项均通过。这只定位了失败原因，不能作为当前工作树正式验证结果，也不改变审计中的 FAIL。

## 非阻断未评估项

以下状态必须继续透明保留：

1. `V2_03_07_review_B_final.md:12-24` 和 `V2_08_12_review_C.md:47-48` 已记录：受保护 FT04 coefficients、risk predictions、metrics 的跨记录数值等价性需要 protected runtime fixture，本审查没有读取该 fixture，因此为 `NOT EVALUATED`。
2. 本审查没有重新执行患者级 A/B 分析、FT03/FT04/FT06 重算或真实 B outcome evaluation；这符合 Primary v2 的 promotion-without-recomputation 和本审查的患者数据边界，不构成把历史结果重新验证为新结果。
3. 项目锁定环境缺少 pytest 的既有事实仍保留为环境发现；直接 wrapper 不是 pytest 结果的替代性伪称。
4. Primary v2 人类方案书按 `archive_reference.md:28` 保留为本地未跟踪文件；tracked 机器可读合同是 `prognosis_analysis/primary/protocol.json`。本审计不把未跟踪方案书误称为已进入 `main`。

## 未发现的禁用路径

在允许的静态范围内未发现：

- Primary v2 根据 FT06 数值表现删除 M0–M5、收缩候选池、调 alpha/lambda 或升级单一冠军模型；
- B feature selection、B lambda tuning、B coefficient refit、B cutoff optimization、B habitat refit、B radiomics candidate re-selection 或 B→A feedback；
- CV outer fold 或 B 中的 SLIC/K-means habitat reconstruction、boundary adjustment 或 habitat-specific radiomics regeneration；
- Primary 入口调用旧 `run_w08_in_memory`、10×5/50-fold orchestrator、Formal W08 R6 remediation state machine 或 FT engineering recovery chain；
- 输出目录、原始影像/ROI、临床/病理/预后原始表、image ID mapping、患者级 prediction/metric/feature 文件进入本次审查记录或提交。

## 科学放行建议

当前建议为：**科学合同可继续作为唯一 Primary v2 基线，但暂不宣称 V2-13 完成或在当前 Windows 工作树可直接执行放行。**

在另一项获得授权的技术修复中，应只处理 provenance hash 的跨平台字节规范化/一致 checkout 约定，然后在不读取患者数据的前提下重新执行当前全部 synthetic tests、manifest/lock/registration/final-report validators、AST/JSON/compile 和 `git diff --check`。修复后仍必须保留 FT04 三项跨记录 numerical equivalence 的 `NOT EVALUATED`，不能为了完成 gate 而伪造 coefficients、risk predictions 或 metrics。

若项目仍要求严格满足方案书“只有 main 为长期主分支”，应在 linked worktree 安全解除且获得明确授权后另行处理本地/远程旧 refs；本审查不强制删除分支、不修改远程 refs，也不把该 housekeeping 条件改写为已完成。

## 审计框架参考

本记录采用科学方法学、偏倚风险、训练/验证污染和证据边界的结构化审查框架：Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents* (arXiv version 2). https://doi.org/10.48550/arXiv.2609.00065

## 本审计提交边界

本次只新增本文件 `prognosis_analysis/V2_13_final_scientific_audit.md`，不修改 Primary v2 canonical code、protocol、manifest、model lock、external registration、README、PROJECT_STATUS、归档文件、分支或远程 refs；不推送远程。
