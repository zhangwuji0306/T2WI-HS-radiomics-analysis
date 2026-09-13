# V2-03～V2-07 Reviewer B 第三次补救最终复审记录

## 审查范围

本复审仅覆盖 Primary v2 的 V2-03～V2-07 当前补救状态，目标提交为 `08be56ef0435e4f41e18765be01879bb269432c5`。审查检查了当前 `prognosis_analysis/primary/` 的实际代码、JSON、既有 Reviewer B 记录及已接受的 V2-00～V2-02 合同；未修改被审查代码、JSON、测试或历史 Reviewer B 记录，未执行 V2-08 及以后。

未读取 `prognosis_analysis/output`、`habitat_analysis/output`、`feature_extract/output`、原始影像、ROI、临床/病理/预后表或其他患者级材料；本记录不含患者级信息、原始影像号、绝对本机路径或敏感数据。

## 验证证据

- 提交 `08be56ef0435e4f41e18765be01879bb269432c5` 仅修改 `prognosis_analysis/primary/test_equivalence.py`、`validate_assets.py` 和 `validate_external.py`。工作区另有未跟踪材料，未纳入本次审查记录或提交范围。
- 在项目锁定 `t2_radiomics` 环境（Python 3.7.12、pandas 1.3.5、numpy 1.21.6）中，通过 `tools/run_t2_radiomics.ps1 -PythonArguments @('-B','prognosis_analysis/primary/test_equivalence.py')` 直接运行 `test_equivalence.py`，退出码为 0。feature order、eligibility、training-only preprocessing、lambda-selection behavior、canonical coefficient repeatability 和 canonical fold metric contract 均为 `PASS`；FT04 coefficients、risk predictions 和 metrics 跨记录等价性明确为 `NOT EVALUATED`。
- 同一锁定环境中逐一执行 `test_equivalence.py` 的 8 个合成测试函数，全部通过。完整 163 行合成 B 基础 frame 可进入评价路径；1、162、164 行、重复 ID、错误 frame attrs、跨 cohort 字段、B107 身份及缺少完整 gate 的输入均被拒绝；model-specific eligible 子集仍被允许。
- `canonical_frame_hash` 在 pandas 1.3.5 下直接执行通过；显式 LF 换行的合成 hash 与原设计一致，结果保持确定性。目标 Python 文件通过 AST/compile，目标 JSON 通过解析，`git diff --check` 通过。
- 当前 evidence manifest、canonical lock、external registration 和 `final_report.build_final_report` 均通过直接验证。对 protocol hash、source ref/commit/hash、promotion timing、M5 population、A/B cohort identity、runtime model identity 和 source copied flags 的篡改测试均 fail-closed。external registration builder 生成的对象可通过自身 validator；错误来源、hash、cohort 或 copied flags 均被拒绝。
- 项目锁定环境未安装 pytest，`python -m pytest prognosis_analysis/primary/test_equivalence.py -q` 的实际结果为 `No module named pytest`。这是非阻断环境发现；未以 pytest 结果替代或掩盖已通过的 wrapper 直接测试。

## 已确认的最终状态

1. `validate_external.evaluate_frozen_predictions` 先调用统一的 `validate_frozen_b_predictors`，由该 gate 校验 registration、manifest、FT06 authorized B=163 token/hash、实际基础 frame 行数、frame attrs 和 cross-cohort 约束；随后校验 protected runtime model identity/state，并拒绝仅凭 predictions attrs、单行或不完整 frame 的输入。
2. `final_report.build_final_report` 在生成 aggregate-only 报告前完整校验 evidence manifest、canonical lock 和 external registration。A production path 绑定 exact A393 identity；M5 使用统一的 `W_Original_available` population token；各模型的 `model_id`、population、`model_input_hash`、transformed feature order hash 和 `state_sha256` 均被锁定并检查。
3. FT03、FT04、FT06 的 source ref/commit/path/hash 保持原绑定；promotion without recomputation、B=107 与 FT06 B=163 分母区分、B prediction frozen before evaluation 及 post-FT promotion timing 均保持。
4. Primary v2 的科学边界保持为 single repeat-1 5-fold、training-only preprocessing/lambda、LASSO `alpha=1`、fixed full-A habitat、B frozen prediction only。未发现 Primary v2 入口执行 Formal v1 的 10-repeat/50-fold、alpha grid、fold-specific habitat refit 或历史 remediation state machine。
5. 患者级 coefficients、predictions、metrics 和 outputs 未被复制到本次审查范围或提交中。受保护 FT04 coefficients、risk predictions 和 metrics 的跨记录 numerical equivalence 仍保持透明的 `NOT EVALUATED`，未被伪称完成。

## 下游风险与交接结论

本次未发现仍会改变队列分母、模型身份、B 评价边界、来源 provenance 或科学方法边界的实质性缺口。pytest 缺失仅限制 pytest 入口的执行，不影响已通过的锁定环境 wrapper 直接测试；受保护 FT04 跨记录 numerical equivalence 仍是明确的运行时验证边界，不应在后续材料中表述为已完成。

## 语义 disposition

**accepted for downstream use with non-blocking findings**

## 进入 V2-08～V2-12 的条件

可进入 V2-08～V2-12。后续必须继续保持当前 Primary v2 合同、promotion without recomputation、FT03/FT04/FT06 provenance、A393 与 FT06 B=163 身份区分、B frozen prediction only 以及患者级数据边界；pytest 未安装的环境事实和受保护 FT04 numerical equivalence 的 `NOT EVALUATED` 状态必须如实保留，不得改写为已验证完成。
