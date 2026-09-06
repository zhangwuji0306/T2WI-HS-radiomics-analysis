# R6-5R first-failure coordinate reconciliation review

## Disposition

`not accepted for downstream use` — 对应项目原生含义：`HARD HOLD`。R6-5 继续 `HOLD`；不得进入 R6-6/G3R、正式 W08 或任何真实 A-side outer-final Cox。

## Blocking finding

批准的 Protocol-Owner Disposition 对协议分支有明确的数值条件：

- I：历史 canonical 与当前 canonical 均为 `288/68`，且必要的 boundary、hash 与 P3B deterministic equality 一致；
- II：历史 canonical 为 `282/67`、当前 canonical 为 `288/68`，进入 HARD HOLD 并定位 drift；
- III：历史 exact replay runner 不可恢复，但仍只能陈述 current canonical=`288/68`，并登记 `historical_diagnostic_runner_not_exactly_recoverable`。

Worker evidence 将自身标为“III on the runner-recovery axis”，但其 Path B current canonical 明确为 `282/67`。因此实际结果不满足 I、II 或 III。`282/67` 与 R6-2 nominal coordinate 一致，不能替代裁定要求，也不能作为 historical canonical equivalence 或 release 条件。该不一致直接改变协议分支判定，故本单元不能供下游使用。

## Independent verification

- 审查范围仅为 `repeat=1`、`outer_fold=1`、`population=R_high`。
- Path A 的 exact runner 在 R6-2 记录的 commit 与当前 worktree 均不可用；所要求的 literal `historical_diagnostic_runner_not_exactly_recoverable` 已登记；未将 `282/67` 改写为历史 exact replay 结果。
- Path B 的记录包含冻结 W07 split、full outer training-only provider fit、train/validation transform、P3B 八字段校验和既有 `derive_fold_populations(..., R_high)`。训练侧 `314=282+21+11`，验证侧 `79=67+7+5`；`minimumROISize=10`，boundary、provider state、train/validation ID hashes、split hash 与 P3B hashes 均已记录且可与当前文件核对。
- 独立运行 technical/binding regression：`28 tests`，exit code `0`。
- 合并 provenance regression：`60 tests`，`1 failure/7 errors`。失败均来自既有 `pre_w08_sop` snapshot mismatch 或 `execution_status` wording assertion，未指向本单元新增 evidence；本次目标文件仍为 untracked，未修改这些既有绑定文件。

## Boundary, safety and provenance

- `B_data_read=false`、`B_reader_invoked=false`、`B_source_opened=false`、`B_statistics_generated=false`。
- 未调用 Cox fit，未生成 risk score、prediction、performance、model freeze lock；formal W08 状态保持 `HOLD`。
- 当前审查前的 git 工作区仅新增本单元两个 evidence 文件；W07、W07A、R6-2、R6-3、R6-4A、科学/技术/统计参数及其记录 hash 未被修改。目标 JSON 记录的 provenance hashes 与实际文件 hash 一致。
- 审查文件不含患者级信息、患者标识或绝对本机路径。

## Required protocol consequence

在得到符合批准分支条件的 coordinate reconciliation 证据前，保持 `HARD HOLD`，不作任何数值等价性解释，不启动 R6-6/G3R、正式 W08、B validation 或真实 A-side outer-final Cox。
