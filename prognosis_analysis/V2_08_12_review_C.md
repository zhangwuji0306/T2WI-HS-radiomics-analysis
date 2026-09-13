# V2-08～V2-12 Reviewer C 独立审查记录

## 审查范围

本审查独立覆盖 Primary v2 的 V2-08～V2-12，目标提交为 `33c4f59d2d899a5c5b44de9f60fa37b4ad54be48` 的实际提交树；目标提交父提交为 `0c8c173ed8591fa2ce34b23b5448f7494425b868`。检查对象包括 Formal/FT 归档树、`README.md`、`项目说明.md`、`PROJECT_STATUS.md`、`.gitignore`、`prognosis_analysis/archive_reference.md`、Primary v2 活动合同和既有 V2-00～V2-07 Reviewer A/B 记录，以及两个 immutable tag 的对象和提交树。

未读取 `prognosis_analysis/output/`、`habitat_analysis/output/`、`feature_extract/output/`、原始影像、ROI、临床/病理/预后原始表、患者级特征/预测/分析结果或 image ID mapping；未执行 V2-13；未修改被审查文件、活动代码、分支或远程 refs。本次只新增本审查记录。

## 证据与发现

### V2-08 Formal v1 归档

- `archive/formal_nested_cv_v1/` 共 49 个版本化文件；其中 48 个 blob 可在 `archive/formal-nested-cv-v1-20260913` 的提交树中找到，唯一新增 blob 是归档目录 README。
- 归档内容为旧 Formal W08 SOP、`W08_*` 记录、R5/R6 审查/复核/失败分类/整改/聚合证据。未发现 habitat、feature、candidate、active schema 或活动代码被移入该目录；当前 `habitat_analysis/`、`feature_extract/`、`prognosis_analysis/primary/` 及相关活动脚本仍在活动树。
- `archive/formal_nested_cv_v1/README.md` 明确标记 `archived / superseded`，并说明目录内容仅用于历史追溯，不作为当前分析入口、参数选择依据或脚本输入；历史完整性由 `archive/formal-nested-cv-v1-20260913` 保证。

### V2-09 FT 历史归档

- `archive/ft_validation_v1/` 共 15 个版本化文件；其中 14 个 blob 与 `archive/ft-validation-v1-20260913` 提交树中的原始 FT blob 一致，唯一新增 blob 是归档目录 README。
- 文件集合覆盖 FT protocol、FT03 A aggregate/report/review、FT04 freeze metadata/lock attestation/audit/reviews、FT06 B aggregate/report/final summary，以及 FT final uniform audit；未复制 FT output、患者级 prediction/metric 表或其他本地敏感材料。
- FT03 与 FT06 JSON 均成功解析。结构检查显示模型级 `local_prediction` 仅登记路径、SHA-256 和行数元数据；指标、校准、DCA、KM 和 paired comparison 均为聚合结构。未发现患者级 ID 字段、患者级预测/风险数组或明细记录数组；FT06 的 `cohort.unique_ids` 为聚合标志而非 ID 明细。
- 归档 Markdown/JSON 未发现绝对本机路径；未发现具体 `patient_id`/`image_id`/`case_id`/`subject_id` 字段或原始预测/风险数组。大 JSON 未因文件大小被自动放行，而是按 JSON 结构完成检查。

### V2-10～V2-11 主线文档与状态

- `README.md` 与 `项目说明.md` 均准确列出：MRI/radiomics freeze → full-A habitat freeze → candidate freeze → Primary v2 fixed 5-fold A validation → full-A model freeze → frozen B external validation → final interpretation。
- 两份入口文档均明确 Formal W08 v1 为 `archived / superseded`，FT 为 Primary v2 的历史开发来源；旧 W08/G3/R5/R6 不再是 active next step。
- `PROJECT_STATUS.md` 精确记录 Primary Prognostic Analysis v2、frozen full-A K=2、A validation promoted from FT03、model freeze promoted from FT04、B external validation promoted from FT06、Formal superseded、FT archived，以及当前下一阶段 `Scientific interpretation / manuscript-ready analysis`。
- `prognosis_analysis/archive_reference.md` 列明活动方法、活动机器可读合同、长期分支 `main`、两个 immutable tag、两个主要归档目录、项目状态历史目录及未归档的活动上游资产。其对未跟踪 Primary v2 人类方案书和本地 transition contracts 的保留说明与当前工作区状态一致；仓库中的 `prognosis_analysis/primary/protocol.json` 仍是可追踪的机器可读活动合同。

### V2-12 Git 与恢复性

- 两个 tag 均为 annotated tag：`archive/formal-nested-cv-v1-20260913` 指向 Formal 过渡前提交 `b09306182e072d0d913d8820d849b4da54d7f1ba`，`archive/ft-validation-v1-20260913` 指向 FT 提交 `3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34`；审查期间未改变 tag refs。
- `33c4f59d2d899a5c5b44de9f60fa37b4ad54be48` 位于本地 `main`。本地仍保留 `codex/l7-current-code-technical-preflight` 和 `codex/w00-formal-archive`，但二者均被 linked worktree 占用；保留分支避免破坏现有 worktree，属于保守且可恢复的处理。未要求或修改远程旧分支。
- `prognosis_analysis/archive_reference.md`、两个 tag 和 `main` 之间的恢复关系可由当前 refs 与提交树复核；未发现归档提交删除远程 refs 或改变 tag 指向。

### Git/data boundary 与 scope

- `0c8c173..33c4f59` 的变更仅涉及 `.gitignore`、README/项目状态文档、Formal/FT/项目状态归档及 `archive_reference.md`；活动 canonical code、Primary v2 contract、evidence manifest、model lock、external registration、habitat/feature 配置和测试均未被本提交改动。
- Formal/FT/项目状态归档共 65 个路径均通过 `.gitignore` allowlist；未发现仍被正向 ignore 规则遮蔽的归档文件。
- 本次变更的 18 个 JSON 全部解析成功，`git diff --check 0c8c173..33c4f59` 通过。
- 目标提交树中未发现 `local_private/`、输出目录、患者级数据文件、映射表、CSV/XLSX、影像/模型二进制、凭据或绝对本机路径。

## 非阻断发现

1. 两个旧本地分支因 linked worktree 占用而保留。待对应 worktree 不再使用时可按项目策略清理；当前不应通过强制删除分支破坏 worktree，也不涉及远程分支删除。
2. 人类可读的 Primary v2 方案书按 `archive_reference.md` 约定保留在本地未跟踪状态；机器可读 `prognosis_analysis/primary/protocol.json` 已在活动树中。后续交接应继续以 tracked contract 和该本地方案书的当前版本保持一致，不应把该未跟踪文件误称为已进入本提交。
3. V2-03～V2-07 最终 Reviewer B 记录中的既有非阻断边界——锁定环境未安装 pytest，以及受保护 FT04 coefficients/risk predictions/metrics 跨记录数值等价性仍为 `NOT EVALUATED`——在本次整理中未被改写；V2-13 仍需如实保留这些状态。

## 验证结果

本次未发现实质性数据边界问题、当前协议误标、错误归档、不可恢复 tag、活动代码误移或 V2-03～V2-07 越界改动。Formal 与 FT 归档均可由各自 immutable tag 追溯；主线文档与 PROJECT_STATUS 已切换到 Primary v2 当前状态；归档内容未携带患者级预测、ID 或明细。

## Semantic disposition

**accepted for downstream use with non-blocking findings**

## 进入 V2-13 的条件

可进入 V2-13。V2-13 应继续保持：

- `main`、两个 immutable tag、Primary v2 tracked contract 和活动上游资产不被改写；
- Formal/FT 归档仅作为 historical-only / promoted evidence 使用，不重新作为活动分析输入；
- FT03/FT04/FT06 的 post-FT disclosure、B107 与 FT06 B163 身份区分及 B frozen prediction only 口径不变；
- 患者级数据、预测、输出、mapping 和绝对本机路径不进入仓库；
- linked worktree 占用的本地旧分支不被强制删除，既有 pytest 缺失和 protected FT04 numerical equivalence 的 `NOT EVALUATED` 状态不被改写为已完成。

## Commit hash

- Review target: `33c4f59d2d899a5c5b44de9f60fa37b4ad54be48`
- Review target parent: `0c8c173ed8591fa2ce34b23b5448f7494425b868`
- Formal immutable tag peeled commit: `b09306182e072d0d913d8820d849b4da54d7f1ba`
- FT immutable tag peeled commit: `3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34`
