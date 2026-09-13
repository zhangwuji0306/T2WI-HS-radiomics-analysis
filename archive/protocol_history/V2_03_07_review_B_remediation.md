# V2-03～V2-07 Reviewer B 补救复审记录

## 审查范围

本复审仅覆盖 Primary v2 的 V2-03～V2-07 补救结果。审查对象为补救提交 `cadcc7097cf587f97a337b06519f17af9d9fe592`、当前工作区中的 `prognosis_analysis/primary/` 实际模块文件，以及已接受的 V2-00～V2-02 合同和当前 Primary v2 方案书。

未读取 `prognosis_analysis/output`、`habitat_analysis/output`、`feature_extract/output`、原始影像、临床/病理/预后表或其他患者级材料；未修改被审查代码、JSON、测试或历史 Reviewer B 记录；未执行 V2-08 及以后。复审仅新增本脱敏记录。

## 验证证据

- 补救提交仅涉及 `prognosis_analysis/primary/` 的 11 个模块安全文件；未纳入 output 目录、原始数据、患者级派生结果或映射文件。FT03、FT04、FT06 的 source ref/commit/path/hash 保持当前已接受绑定，B=107 与 FT06 B=163 仍被区分。
- `final_report.build_final_report` 对当前 manifest、canonical lock 和 external registration 通过完整校验并生成 aggregate-only report。`final_report.py:69-75` 已依次调用 `validate_evidence_manifest`、`validate_canonical_lock` 和 `validate_external_registration`。
- 当前静态 JSON 的 AST/compile 与 JSON 解析通过；`git diff --check` 通过。
- `test_equivalence.py` 的 synthetic equivalence、promotion metadata、cohort identity 和 runtime model identity 四个测试入口均通过。直接运行 synthetic equivalence 输出中，feature order、eligibility、training-only preprocessing、lambda selection、coefficient repeatability 和 fold contract 为 `PASS`；受保护 FT04 数值等价性仍为 `NOT EVALUATED`。

## 已确认的补救结果

- A production gate 在 `validate_assets.py:635-685` 和 `run_cv.py:417-423` 中要求 repeat-1、五折、生产 split 的 A393 完整规模及 canonical split hash，并要求 frame ID 集与冻结 split 完全相等；`validate_a_cohort_binding` 还要求显式 A token/hash、manifest 绑定、393 例和 89 个 DFS event。验证不依赖真实 ID 的 synthetic boundary test。
- manifest、lock 和 registration 已形成闭环：manifest 校验 FT03/FT04/FT06 的状态、路径、hash、来源 commit、时间顺序、A/B identity 和 isolation；canonical lock 校验每个模型的 `model_id`、population、`model_input_hash`、transformed feature order hash、`state_sha256` 和 selection 约束；registration 校验 protocol hash、FT06 source ref/commit/path/hash、canonical lock hash、B freeze timing、promotion timing、authorized B identity 和 forbidden actions。
- M5 的 active population token 已统一为 `W_Original_available`，与 `MODEL_SPECS`、protocol 和 canonical lock 一致；lock 的 state provenance 明确为非患者级 identity-only protected runtime verification，且没有伪造 coefficients。Primary v2 仍是 single-repeat-1 five-fold、training-only preprocessing/lambda、`alpha=1`、fixed full-A habitat、B frozen prediction only；未发现带回 Formal v1 的 10-repeat/50-fold、fold-specific habitat refit 或 alpha grid。

## 阻断发现

### 1. B gate 仍接受不完整授权队列

`validate_external.py:105-130` 的 `validate_frozen_b_predictors` 会校验完整 registration、manifest、B token/hash、B=163 元数据和 predictor schema，但没有要求传入的 B `feature_frame` 具有授权队列的完整 163 行，也没有其他显式的 frame completeness binding；最终只检查 `eligible.any()`。

实际使用正确的 FT06 B token/hash、当前静态 manifest/registration 和一个满足 M0 clinical schema 的单行 synthetic frame 时，函数返回 `eligible_n=1`，未拒绝该不完整输入。由此，B107/wrong-token substitution 虽能被拒绝，但 authorized token 被复用在截断或不完整 frame 上仍可进入 prediction gate。

下游影响：B prediction 可在错误分母或截断队列上产生，FT06 B=163 的 cohort identity 只绑定到了 metadata，未绑定到实际输入规模；这会破坏外部验证分母解释和 handoff safety，属于实质性 downstream contamination risk。

### 2. external registration builder 与其 validator 不自洽

`validate_external.py:264-359` 的 `build_external_registration` 返回的 `source` 只包含 ref、commit、aggregate、report 和 `immutable`，没有写入 `patient_level_predictions_copied: false` 与 `patient_level_metrics_copied: false`。

但同文件 `validate_external_registration:54-60` 将这两个字段作为 source binding 的强制条件。用与当前 FT06 registry、canonical lock 和 cohort 元数据一致的 synthetic aggregate 调用 builder 后，生成对象无法通过自身 `validate_external_registration`，错误为 `external registration source binding mismatch`。当前仓库内手工登记的静态 registration 因包含这两个字段而能通过，但 V2-07 的生成入口本身不能完成可验证的 provenance handoff。

下游影响：重新生成或交接 external registration 时会被 fail-closed 拒绝，V2-07 不能作为稳定的 canonical registration producer 进入后续阶段；这也是实际 provenance/handoff readiness 缺口，而非仅为测试形式问题。

## 负向测试覆盖缺口

现有 `test_equivalence.py:173-221` 覆盖了 manifest protocol hash、registration timing/source/report hash、M5 population、A 子集、wrong token、B107 token 和 runtime identity 字段篡改，但没有覆盖“正确 B token/hash + 不完整 frame”，也没有调用 `build_external_registration` 后再验证其输出。因此现有 synthetic tests 不能发现上述两个阻断行为。

## 非阻断未评估项

受保护 FT04 coefficients、risk predictions 和 metrics 的跨记录 numerical equivalence 仍明确为 `NOT EVALUATED`。本复审边界不读取 protected runtime state，因此不将其伪称为通过；后续任何记录均不得声称该 numerical equivalence 已完成。

## 下游风险与交接结论

Primary v2 的科学规则、A-only 训练隔离、promotion without recomputation、来源 hash 身份和 B 禁止动作在当前静态合同中保持一致；但 B 实际输入完整性和 registration builder 自洽性两个缺口仍会分别影响外部验证分母和 provenance handoff。补救结果在修复并重新验证这两项前，不具备进入 V2-08～V2-12 的安全条件。

## 语义 disposition

**not accepted for downstream use**
