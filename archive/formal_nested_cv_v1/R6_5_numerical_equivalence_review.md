# R6-5 numerical equivalence and implementation regression review

## Disposition

`not accepted for downstream use` — 项目原生含义：`R6-5 未通过；继续 HOLD`。需要新的 Worker 返修并重新提交 R6-5 证据；本轮 Reviewer 不修复 Worker 结果。

## Blocking findings

### 1. 禁止期实际生成并比较了 Uno C-index

项目 Pre-W08 SOP 的“正式 W08 前不得产生模型性能”规则明确规定，整改期间禁止产生或查看 `C-index`、`Uno C-index`、AUC、Brier、calibration 和相关性能量。该条款没有为 synthetic fixture 设置例外。

`tests/test_r6_5_validation.py:185-200` 的 selected alpha/lambda 等价性测试分别调用旧版和当前版 `tune_elastic_net`，并断言：

- `old_selection["mean_uno_c_index"]` 与 `new_selection["mean_uno_c_index"]` 数值相等；
- 该值参与 selected alpha/lambda 的一致性验证。

实际实现 `prognosis_analysis/scripts/w08_nested_cv.py:2428-2437` 对 synthetic validation risk 调用 `uno_c_index`，并在 `2494-2506` 汇总为 `mean_uno_c_index`；该指标同时由 `_select_candidate` 用于选择。R6-5R superseding disposition 允许 deterministic synthetic Cox、risk score、objective 和 coefficient 等价性，但没有授权 synthetic C-index/Uno C-index。因而“synthetic”及 JSON 中 `performance_generated=false`（仅表示未生成正式 performance artifact）不能消除该越界执行。

需要新的 Worker 在现有授权边界内重做 selection-equivalence 证据，或先取得明确的 protocol-owner 例外授权；在此之前不得将该测试结果作为 R6-5 PASS 使用。

### 2. selection equivalence 未覆盖实际 100 点协议 lambda grid

协议和实现本身均锁定 100 点 grid：`prognosis_analysis/scripts/w08_nested_cv.py:87` 的 `LAMBDA_COUNT=100`，配置文件的 `lambda_grid.values_per_alpha=100`，以及 `tests/test_r6_5_validation.py:117-121` 的静态锁定断言均存在并通过。

但实际旧/新 selection 比较在 `tests/test_r6_5_validation.py:189-194` 显式传入 `lambda_count=2`，因此只比较了两个 synthetic lambda 点；报告中的 selected index `1` 和 ratio `1e-4` 也是该两点 fixture 的结果，不是 100 点协议 grid 中的 selection output。单个 direct-fit 等价性和已保留的 R6-4A 16 个 stress fits 不能替代其余 98 个候选点的 selection equivalence。iteration budget 变化可能在不同候选点产生不同收敛状态，因此当前静态 100 点锁定不足以证明实际协议 grid 的选择结果不变。

该覆盖缺口需要新的 Worker 提供完整 100 点协议 grid 的、同时满足性能禁令边界的等价性证据；本轮 Reviewer 不自行改写测试。

## Independent verification

### Old solver provenance

旧 solver commit `899cf71e1895985f1f2eb5daf482d1c595dad154` 存在，提交信息为 R6-0 baseline bookkeeping remediation，且是 R6-4A 提升预算提交的祖先。路径 `prognosis_analysis/scripts/w08_nested_cv.py` 的旧 blob SHA-1 为 `075fe9624d8b8130f31016cd488d926feff3486c`，与 R6-5 JSON 一致；旧源码明确为 `max_iter=250`。该 provenance 检查通过。

### Coordinate, protocol and evidence binding

R6-5 JSON 与 R6-5R 注册值一致：canonical coordinate 为 `repeat=1 / outer_fold=1 / population=R_high`，full outer train/validation 为 `314/79`，eligible 为 `282/67`；R_high 状态计数为 train `282/21/11`、validation `67/7/5`（extractable / structural absence / technical small ROI）。eligible ID hashes、full outer ID hashes、P3B train/validation/combined state hashes、W07 split、provider fit scope/boundary 和 `minimumROISize=10` 均匹配注册记录。

R6-5 JSON 注册的 R6-5R 两份 evidence、superseding disposition、R6-4A JSON 和 audit 的实际 SHA-256 全部匹配；W04、W07A、technical-freeze、W07/W08 configuration、candidate-pool、solver source 和本测试源 hash 也全部匹配。

### Solver, stress and regression

统一 `Elastic-Net max_iter=3000`、`tolerance=1e-7`、alpha/lambda grid、objective、gradient、convergence criteria、zero-start、`warm_start=false`、penalty semantics、candidate pool/order、W07 split 和 population binding 均保持锁定。已接受的 R6-4A stress evidence `16/16` converged、最大迭代 `1814`、统一 budget、无 candidate deletion/skipping 的记录被完整保留。

在锁定环境中独立复跑：

| Suite | Tests | Failures | Errors | Skips | Exit |
|---|---:|---:|---:|---:|---:|
| R6-4A/W08/R6-5 targeted | 81 | 0 | 0 | 0 | 0 |
| W07, B-blinding, A-access binding/negative | 37 | 0 | 0 | 0 | 0 |
| compileall | — | 0 | 0 | 0 | 0 |

既有 provenance reconciliation 相关失败已在 Worker evidence 中单独标为 pre-existing unrelated failure，未通过改写历史绑定绕过；该事项不是本轮新增的 R6-5 文件变更。

### Stage boundary and privacy

本轮未发现 R6-5 测试实际读取 B 数据、调用真实 A-side outer-final Cox 或启动 formal W08；R6-5 JSON/R6-5R 的四项 B flags 均为 `false`，`model_freeze_lock.json` 不存在，W08 gate 保持 `HOLD`。direct synthetic risk score 属于被允许的内部等价性对象，不能与上面的禁止期 synthetic Uno C-index 混同。审查未修改 Worker evidence、代码、配置、协议或状态文档，未提交或推送。

## Required consequence

在两个阻断均由新的 Worker 返修并经新的独立 Reviewer 复核前，继续保持 `HOLD — AUTHORIZED FOR R6-5 ONLY`。不得进入 R6-6/G3R、R6-6.5、formal W08、真实 A-side outer-final Cox、prediction、performance evaluation、model freeze 或 B validation。
