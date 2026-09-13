# R6-7 Formal Release Gate Archive-Identity Remediation Review

结论：**ACCEPT**

## 审查范围

- 基线：`fa62737`
- `prognosis_analysis/scripts/w08_formal_run_a.py`
- `tests/test_w08_formal_release_gate.py`

## 核验结论

| 项目 | 结论 | 说明 |
|---|---|---|
| archive-id 解析边界 | 通过 | 只接受单一 `_failed` 后缀表示的归档身份；空 raw id、双重 `_failed` 后缀、`/` 或 `\` 路径分隔符以及缺失后缀均被拒绝。 |
| writer-style 身份 | 通过 | 目录 `attempt_002_failed` 仅在 `failure_audit.json` 和 `run_state.json` 均显式保存 raw id `attempt_002` 时被接受；任一内部 id 缺失或不一致均 fail closed。 |
| registered-style 身份 | 通过 | `failure_audit.json` 内部 id 必须精确等于归档目录 id；`run_state.json` 如存在 `attempt_id` 也必须精确相等。仅保留历史 registered/R0 记录中 `run_state.json` 无 `attempt_id` 的兼容语义，未将其扩展为任意 mismatch 兼容。 |
| 失败证据 fail-closed 检查 | 通过 | `stage/status`、非空 `failure_stage`、非空 failure reason、commit 交叉对账与可解析性、B 访问标志、`final_outputs_generated` 和归档内 final outputs 检查均保持 fail closed。 |
| R0 与 legacy/newer explicit | 通过 | 固定 `attempt_001_failed` 的 R0 兼容边界未改变；legacy + newer explicit 仍严格对账 newer attempt 与 `execution_status.last_attempt`。 |
| 测试覆盖 | 通过 | 新增 writer-style PASS，并分别覆盖 failure id 不一致与 run-state id 不一致的 FAIL；原有 inflight status、缺字段、unsafe B flag、final output、R0 误识别等负例保留并通过。 |
| 其他 release-gate 边界 | 通过 | 差异未改动 R5 successor binding、G3、B/model-freeze 边界，也未改动科学、技术、统计或 solver 参数。 |

## 阻断发现

无。

## 非阻断发现

无。

## 验证结果

- 锁定环境 `python -m unittest tests.test_w08_formal_release_gate -v`：27 tests，全部通过。
- 锁定环境 `python -m compileall -q prognosis_analysis/scripts/w08_formal_run_a.py tests/test_w08_formal_release_gate.py`：通过。
- archive-id 边界探针：有效单后缀解析通过；空 raw id、双重后缀、正反斜杠路径分隔符和缺失后缀均按预期拒绝。
- `git diff --check` 通过。
- 未启动 formal W08，未读取 A/B 患者数据，未生成 prediction、performance 或 model artifact，未提交或推送。

## 放行边界

允许主控提交上述两个代码/测试文件。本 ACCEPT 仅表明 archive-identity remediation 可接受，不等于允许绕过 dirty worktree 或当前 HEAD 尚未重建的 G3/R5 evidence binding gate；真实 formal release gate 仍应保持 HOLD，直至这些治理条件独立满足。
