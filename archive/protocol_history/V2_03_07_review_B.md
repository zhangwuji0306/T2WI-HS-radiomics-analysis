# V2-03～V2-07 Reviewer B 独立审查记录

## 审查范围

本审查仅覆盖 Primary v2 的 V2-03～V2-07：canonical code、等价性验证、evidence promotion、canonical model freeze 和 external validation registration。审查对象为：

- `prognosis_analysis/primary/validate_assets.py`
- `prognosis_analysis/primary/run_cv.py`
- `prognosis_analysis/primary/refit_freeze.py`
- `prognosis_analysis/primary/validate_external.py`
- `prognosis_analysis/primary/final_report.py`
- `prognosis_analysis/primary/test_equivalence.py`
- `prognosis_analysis/primary/PRIMARY_V2_EVIDENCE_MANIFEST.json`
- `prognosis_analysis/primary/model_freeze_lock.json`
- `prognosis_analysis/primary/external_validation_registration.json`

审查基于实际工作区文件、目标提交 `dba5cab` 及其累计状态，先检查文件与代码行为，再参考已存在的 V2-00～V2-02 审查记录。未读取 `prognosis_analysis/output`、`habitat_analysis/output`、`feature_extract/output`、原始影像、临床/病理/预后表或其他患者级材料；未修改被审查代码、manifest、lock 或 registration；未执行 V2-08 及以后。

## 证据

- 五个正式入口均位于 `prognosis_analysis/primary/`；目标提交只新增 V2-03～V2-07 相关的 9 个正式文件，没有新增 output、原始数据或患者级材料。
- `validate_protocol`、`validate_evidence_manifest` 和 `validate_canonical_lock` 在当前文件上均通过。
- 直接运行 `python -B prognosis_analysis/primary/test_equivalence.py` 通过。合成 fixture 的 feature order、eligibility、training-only preprocessing、lambda-selection behavior、canonical coefficient repeatability 和 fold contract 均为 `PASS`；跨 FT04 coefficients、risk predictions 和 metrics 均明确为 `NOT EVALUATED`。
- 6 个 Primary v2 Python 文件通过 AST 解析，4 个 JSON 文件通过解析，`git diff --check` 通过。
- 当前 `model_freeze_lock.json` 的原始 FT04 hash、Primary v2 protocol hash、promotion date、`no_refit=true` 和 `no_B_tuning=true` 均存在；registration 明确记录 B prediction 在 B evaluation 前冻结，以及 Primary-v2 promotion 发生在 FT B 结果可见之后。

## 通过项

### Canonical code 与科学合同

- 入口代码明确使用 single-repeat 5-fold、固定 full-A habitat 标志、training-only preprocessing/lambda、`alpha=1` 和 B frozen-prediction-only 约束。
- `run_cv.py` 的 outer validation 只使用固定 repeat-1 split；eligibility 在预处理前确定；lambda 只在 outer-training 内的 inner 5-fold 中选择；没有调用旧 Formal v1 的 10-repeat/50-fold 执行入口、fold-specific habitat refit 或 alpha grid 状态机。
- 输出写入使用临时文件加 `os.replace` 的 transactional pattern；失败路径清理临时文件。患者级预测留在内存中，CLI 只写 aggregate summary。
- `PRIMARY_V2_EVIDENCE_MANIFEST.json` 采用 `PROMOTED_WITHOUT_RECOMPUTATION`，分别登记 FT03、FT04、FT06 及 habitat/R/W/C/cohort 的相对路径、hash 和身份；技术筛选 B=107 与 FT06 授权 B=163 被明确区分。
- `model_freeze_lock.json` 没有伪造系数正文，并明确把 FT04 作为 `promoted_from_FT04` 来源；registration 的禁用动作包含 B tuning、refit、cutoff、habitat/radiomics 重选和 B→A feedback。

### 等价性与证据边界

- `test_equivalence.py` 仅构造 synthetic fixture 和非患者级 split metadata，没有读取 B outcome 或 repository output。
- 测试没有把 protected FT04 的系数、风险预测或指标等价性伪称为已证明；这符合当前受保护运行时不可复核的边界。

### 范围与隐私

- 审查目标提交的文件范围符合 V2-03～V2-07；工作区中另有未跟踪材料，但未被本审查修改或纳入交付。
- 未发现患者隐私、原始影像、分析输出或本机绝对路径进入本次正式提交。

## 发现与未评估项

### 阻断发现 1：final report 不是 fail-closed

`final_report.py:67-75` 只检查 manifest 的 status、external registration 的 status，并调用 `validate_canonical_lock`；没有调用 `validate_evidence_manifest`，也没有校验 registration 的 protocol hash、source hash/ref/commit、B 身份、时间顺序或禁用动作。实际行为测试中，将 manifest 的 protocol hash 改为全零、将 B freeze timing 改为 `false`，以及将 lock 的 M5 population 改成错误值，`build_final_report` 仍分别接受并生成报告。

这使得被篡改或身份不一致的 promotion metadata 可以通过最终报告入口，违反 Primary v2 要求的 fail-closed 和 provenance handoff。

### 阻断发现 2：A/B 输入身份没有被强制绑定

`validate_assets.py:565-568` 在绑定 split 时只要求 frame ID 是 frozen split ID 的子集，而不是要求生产 A frame 与冻结 A393 队列完全相等。因此生产 CLI 可以在使用正确 split 的情况下处理不完整的 A frame。对应地，`validate_external.py:40-72` 只根据字段、availability 和可选的 `split` 列检查 B frame，不强制 FT06 authorized B=163 的 cohort identity 或 identity hash；实际将没有显式 cohort identity 的 synthetic frame 作为 B predictors 传入时被接受。

这会允许错误分母、截断队列或错误来源的 frame 进入 A validation/B prediction，实际削弱 A/B isolation 和下游分母可解释性。

### 阻断发现 3：模型状态与来源绑定不完整，且存在 M5 identity mismatch

- `validate_external.py:75-90` 的 `_validate_protected_state` 只比较 `model_input_hash` 和 transformed feature order，不比较 lock 中登记的 per-model `state_sha256`，也不验证运行时对象的状态身份。实际用匹配 input/order hash 但任意 runtime objects 的 synthetic state 调用该校验时被接受。
- `validate_external.py:161-192` 的 registration builder 接受调用者任意提供的 `source_ref` 和 report SHA-256，只做格式校验，不要求其等于已接受 FT06 source binding；实际用不受信 source ref 和伪造的 64 位 report hash 仍可构建 registration。
- `refit_freeze.py:39-69` 的 `_model_identity` 不校验 population。当前 lock 的 M5 population 为 `W_Original`，而 `validate_assets.py:222-223` 的 canonical `MODEL_SPECS` 使用 `W_Original_available`；当前 lock validator 未发现该不一致。

因此当前 lock 可以看起来已冻结，但仍不能充分证明实际运行时 model state、外部来源和 canonical model identity 是同一对象。

### 非阻断未评估项：受保护 FT04 跨记录数值等价性

`test_equivalence.py` 明确将 `cross_artifact_coefficients`、`cross_artifact_risk_predictions` 和 `cross_artifact_metrics` 标为 `NOT EVALUATED`。本项本身不构成拒绝理由：测试没有伪称证明，且当前审查边界不允许读取受保护 FT04 runtime state；但在下游正式使用前，仍必须完成受保护状态核对或明确保持该限制并禁止声称“跨记录 numerical equivalence 已证明”。

## 下游风险

当前 canonical 科学规则和 promotion 语义大体清晰，但上述三个阻断缺口会影响 provenance、队列身份和 B 评价边界。如果直接进入下游，最终报告可能接受被篡改的注册元数据，A/B 运行可能接受不完整或未授权 cohort，B prediction 也可能使用没有 state hash 绑定的 runtime model。该风险不是形式性文档问题，而是会改变分析对象或模型身份的实际风险。

## 语义 disposition

**not accepted for downstream use**

## 进入 V2-08 的条件

1. 使 `final_report.py` 在生成报告前 fail-closed 校验完整 evidence manifest、canonical lock 和 external registration，包括 protocol/source hash、source ref/commit、时间顺序、B cohort identity 和禁止动作；任何不一致均不得生成正式报告。
2. 生产 A 入口强制 frame 与冻结 A393 modeling population 完全一致并绑定其非患者级 identity hash；B 入口强制绑定 FT06 authorized B=163 cohort identity，并禁止仅凭列名/可选 split 列放行。
3. 使 canonical lock/runtime gate 校验每个模型的 population、selection、model input/order 和 `state_sha256`；修正或明确处理 M5 `W_Original` 与 `W_Original_available` 的 identity mismatch。
4. 在受保护运行时完成 FT04 coefficients、risk predictions 和 metrics 的跨记录 numerical equivalence；结果须按预先定义 tolerance 记录，不能把当前 `NOT EVALUATED` 改写成已证明。
5. 上述修改完成后重新运行 JSON 解析、Python 编译/测试、合成边界测试和 `git diff --check`，并重新进行独立审查；不得读取或提交患者级材料和 output 目录。
