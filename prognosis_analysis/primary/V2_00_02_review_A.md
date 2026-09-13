# V2-00～V2-02 Reviewer A 独立审查记录

## 审查范围

本审查仅覆盖 Primary v2 的 V2-00～V2-02：历史 refs 冻结核对、方法学转换记录和 Primary scientific contract。审查对象为：

- `PRIMARY_ANALYSIS_V2_TRANSITION_20260913.md`
- `prognosis_analysis/primary/protocol.json`
- `prognosis_analysis/primary/README.md`

未读取 `prognosis_analysis/output`、`habitat_analysis/output`、`feature_extract/output` 或任何原始/患者级材料；未修改上述三份交付物，未执行 V2-03 及以后模块。

## 证据摘要

审查基于实际工作区文件和 Git refs，不以 Worker 自述替代文件证据。

- `main`：`b09306182e072d0d913d8820d849b4da54d7f1ba`
- `archive/formal-nested-cv-v1-20260913`：annotated tag，peeled commit 为 `b09306182e072d0d913d8820d849b4da54d7f1ba`，与换轨前 `main` HEAD 一致。
- `codex/ft-validation`：`3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34`
- `archive/ft-validation-v1-20260913`：annotated tag，peeled commit 为 `3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34`，与 FT HEAD 一致。
- `codex/primary-v2-transition` 存在，审查目标提交为 `207e39a94e8c8b5d03ac56aa3859da2325ae77e4`，其父提交为换轨前 `main` HEAD。
- 审查目标提交仅包含上述三份 V2 文档；未包含分析输出、原始数据、患者级材料或映射文件。

执行并通过的核对包括：

- `git show-ref --heads --tags`、`git rev-parse --verify`、`git log -1`：refs 与历史 HEAD 对齐。
- `ConvertFrom-Json` 及关键字段断言：`protocol.json` 可解析，核心科学参数完整且准确。
- 关键词、模型集合、分母和边界断言：转换披露与合同约束一致。
- `git diff-tree --no-commit-id --name-only -r HEAD`：提交范围符合 V2-00～V2-02。
- `git diff --check HEAD`：通过。

## 审查发现

### 科学合同

通过。转换记录明确说明 Formal W08 v1 未成功完成、Formal v1 superseded、三项换轨理由、FT03/FT06 在决定时已可见，并准确包含 `post-FT protocol transition`。文档没有把本次决定伪装成 B 验证前的事前预指定，也没有因性能删减模型；M0–M5 全部保留，B 不再用于新的 tuning。

`protocol.json` 和 `README.md` 一致记录了 fixed full-A habitat、3D SLIC 4 mm、K=2、`R_low=49`、`R_high=10`、`W_Original=107`、C/G、LASSO `alpha=1`、W07 repeat-1 single 5-fold、training-only lambda selection 和 B frozen prediction only。

### 分母与证据身份

通过。技术筛选参考中的 B=107 与 FT06 授权外部验证中的 B=163 被标记为不同来源/分母；合同禁止将二者静默合并，并要求后续 B 输入绑定 FT06 authorized cohort identity。

### Downstream contamination risk

V2-00～V2-02 未引入 B→A 污染。剩余风险位于后续实现：V2-03～V2-07 若让 B 参与 feature selection、lambda tuning、coefficient refit、cutoff optimization、habitat refit 或任何 B→A 反馈，即会违反当前科学合同。现有合同已将这些路径列为 forbidden，并要求在 B 评价前冻结模型。

### Scope compliance

通过。审查目标提交仅有三份方法/合同文档；没有修改输出目录、原始数据、患者级材料或历史 refs。工作区中与本模块无关的未跟踪材料保持原样，未被纳入本审查交付。

### Handoff readiness

已具备进入 V2-03～V2-07 的条件。后续代码提取、等价性验证、evidence promotion 和 model registration 必须以当前 `protocol.json` 为唯一科学合同，并保持既有 FT03/FT04/FT06 身份与 B=163 授权分母，不得重写历史 refs 或重新设计模型集合。

## Semantic disposition

**accepted for downstream use**

## 允许进入 V2-03～V2-07 的条件

1. 保持当前 Primary v2 合同中的固定 full-A habitat、C/G、R_low/R_high、W_Original、M0–M5、alpha=1 和 repeat-1 5-fold 规则不变。
2. 保持 lambda 及其他预处理/特征选择操作的 training-only 隔离；B 只执行 frozen prediction only。
3. 将技术筛选 B=107 与 FT06 授权 B=163 作为不同来源身份处理，不静默改写分母。
4. 继续遵守患者隐私、原始数据和分析输出不进入仓库的边界，并仅在本模块范围内推进。

## 审查框架参考

本审查采用科学方法学、偏倚/污染风险和证据边界的结构化检查框架：Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. arXiv:2609.00065. https://doi.org/10.48550/arXiv.2609.00065
