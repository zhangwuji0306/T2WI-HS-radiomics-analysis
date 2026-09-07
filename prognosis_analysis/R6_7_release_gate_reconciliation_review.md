# R6-7 Release Gate Reconciliation Review

结论：**ACCEPT**

## 审查范围

- 基线：`6b93ed6`
- `prognosis_analysis/scripts/w08_formal_run_a.py`
- `tests/test_w08_formal_release_gate.py`

## 核验结论

| 项目 | 结论 | 说明 |
|---|---|---|
| 归档校验顺序与 R0 例外边界 | 通过 | 所有归档先经过共同 schema、身份、失败原因、B flags、提交可解析性和 final-output 检查；仅在已有显式失败归档时，固定的 `attempt_001_failed` R0 兼容归档可免于匹配当前 `execution_status`。 |
| explicit failed 对账 | 通过 | 显式失败归档仍要求目录身份、`failure_audit.json` 身份、`run_state.json` 身份、代码提交、失败阶段相互一致，并严格匹配 `execution_status.last_attempt`。 |
| legacy fail-closed | 通过 | 缺失失败阶段、非 false B 标志、错误归档身份等负例均被拒绝；R0 兼容识别仅接受固定 attempt 身份和受限的 W08 modeling 状态。 |
| 输出、staging、B、model-freeze 边界 | 通过 | canonical final outputs、stale staging、归档内 final outputs、B flags 和 model-freeze 检查均保持在 gate 中，未被例外路径绕过。 |
| 回归测试覆盖 | 通过 | 覆盖 legacy-only、legacy + newer explicit、legacy 负例，以及显式归档状态、字段和输出安全性负例。 |
| 真实本地 newer archive 身份不一致 | 通过 | 本地 newer archive 的目录名为 `attempt_1788647247630504_d8ea5057fc8b_failed`，内部 `attempt_id` 为不带 `_failed` 后缀的值；共同身份校验仍会 fail closed，保持 HARD HOLD。 |
| R5 / 科学 / 技术 / 统计边界 | 通过 | 差异仅涉及 prior-attempt reconciliation 与对应回归测试；未改动 R5 successor binding、B/model-freeze 边界或科学、技术、统计参数。 |

## 阻断发现

无。

## 非阻断发现

无。

## 验证结果

- `tools\run_t2_radiomics.ps1 -PythonArguments @('-m','unittest','tests.test_w08_formal_release_gate')`：25 tests，全部通过。
- `tools\run_t2_radiomics.ps1 -PythonArguments @('-m','compileall','-q','prognosis_analysis/scripts/w08_formal_run_a.py','tests/test_w08_formal_release_gate.py')`：通过。
- 未启动 formal W08，未读取 A/B 患者数据，未生成 prediction、performance 或 model artifact，未提交或推送。
