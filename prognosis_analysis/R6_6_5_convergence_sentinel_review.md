# R6-6.5 first-failure convergence sentinel independent review

## Disposition

`ACCEPT_WITH_FINDINGS`

无阻断问题。R6-6.5 证据支持在固定坐标上完成一次 A-only convergence
sentinel，并允许进入 R6-7。该接受不授权 formal W08、outer-validation
prediction、performance evaluation、W09、model freeze 或 B validation。

## 1. Evidence and binding verification

- JSON 可解析，schema=`r6_6_5_convergence_sentinel`、version=`1.0`，status=`PASS`。
- 坐标与授权一致：`repeat=1 / outer_fold=1 / M3H / R_high`。
- 完整 outer population 为 `314/79`；R_high eligible population 为 `282/67`。
- P3B 状态计数为 training `282/21/11`、validation `67/7/5`
  （extractable / structural_absence / technical_small_roi），两侧分别回加
  `314` 与 `79`；`minimumROISize=10`，状态定义与已接受绑定一致。
- R_high eligible ID hashes、full outer ID hashes、P3B train/validation/combined
  state hashes、W07 split hash、R_low/R_high candidate hashes 与 R6-5/G3R
  记录一致。
- JSON 中列出的 11 项代码/配置 SHA-256 均与当前文件一致；W07 split artifact
  的实际 SHA-256 也匹配。`git_head` 与当前 HEAD
  `a83cd991c6522d42a82d35837c6ffda2fc41c340` 一致。
- audit Markdown 中的坐标、population、计数、参数、边界和 safety 状态与 JSON
  一致；Markdown 记录的 evidence SHA-256 与当前 JSON 一致。

## 2. Tuning and convergence

- inner tuning 明确为 outer-training-only、固定 5-fold；alpha grid 为
  `[0.1, 0.5, 0.9, 1.0]`，每个 alpha 使用 100 个 lambda，minimum ratio 为
  `1e-4`。`5 × 4 × 100 = 2000` 次 candidate attempts，与证据一致。
- metric 为 protocol-defined `mean inner-validation Uno C-index`，并明确标记
  `metric_scope_is_inner_tuning_only=true`、`outer_validation_used=false`。
  静态核对 `w08_nested_cv.py` 的 `tune_elastic_net` 与 `_fit_outer_model`
  （约第 2365–2538、2731–2867 行）确认 inner splits、preprocessing、lambda
  max 和 final refit 的输入路径均以传入的 training frame 为源；outer validation
  仅在后续正式 prediction 路径使用。
- selected alpha=`0.1`、lambda index=`97`、ratio=`0.00012045035402587811`
  与固定 log-spaced grid 一致；ratio 与 outer lambda max 的乘积等于记录的
  final lambda `0.0006337852975282527`。
- outer-training final M3H refit 为 `n=282`、events=`66`、censors=`216`，
  `max_iter=3000`、tolerance=`1e-7`、zero start、no warm start；658 次迭代后
  以 `objective_stagnation` 收敛。最后 objective improvement
  `4.850400469713634e-06` 小于当前 objective-stagnation threshold，数值记录自洽。
- candidate failures、candidate deletion、candidate skipping、iteration-budget
  exhaustion 和 clipping-related failure 均为零/false；唯一稳定动作是既有
  solver 路径中的 `backtrack_objective`。未见候选池、参数、fold 或失败样本的
  后验修改证据。

## 3. Safety and privacy boundary

- `B_data_read`、`B_reader_invoked`、`B_source_opened`、`B_statistics_generated`
  均为 `false`。
- `formal_prediction_generated`、`held_out_prediction_generated`、
  `performance_generated`、`risk_score_generated`、`validation_survival_prediction`
  和 `model_comparison_generated` 均为 `false`；`formal_W08`、`W09` 和
  `model_freeze` 均未启动。
- provider 确实对 outer validation 执行了 transform，但证据明确限定为
  `outer_validation_transformed_for_P3B_only=true`；validation IDs 未参与
  provider/boundary fit。该 transform 用于 P3B 状态与 population-state 核对，
  不等同于 outer-validation prediction。
- evidence 与 audit 未发现患者 identifier literals、绝对本地路径或患者级输出。
  临时 runner 与 bytecode 均标记为清理完成；当前也不存在
  `prognosis_analysis/scripts/_r6_6_5_convergence_sentinel.py` 或
  `model_freeze_lock.json`。
- 两条 warning 均为 A-only feature-frame assembly 阶段的 pandas
  `PerformanceWarning`，没有 solver、convergence、B access 或 output-safety
  关联；属于非致命 warning。

## 4. Non-blocking findings

1. `scope.technical_only=false` 与本次实际允许的 inner tuning 和
   outer-training final Cox refit 相符；它不应被解释为 formal W08。当前
   `formal_W08=false` 及各项 prediction/performance/freeze flags 已构成有效边界。
   建议后续状态读取器保留这一语义区分，但无需返修本次结果。
2. 临时 runner 已按审计要求删除，但证据未保留该 runner 的 source hash 或
   可复核的 orchestration digest。因此 exact runner orchestration 不能独立重放；
   当前 protected code/config hashes、固定结果不变量和 fail-closed flags 足以支持
   本次 sentinel 的阶段判断，但后续同类 sentinel 可在删除前记录 runner SHA-256
   以增强可追溯性。该项不阻断 R6-7。
3. `canonical_population.training_events` 与 `training_censors` 的数值合计为
   R_high eligible training `282`，而不是完整 outer training `314`；audit 的
   final-refit 小节已明确其实际 scope。后续若更新 schema，宜将字段显式命名为
   eligible-training counts；不需要改变本次数据或协议。

## 5. Blocking findings

无。

## Reviewer conclusion

R6-6.5 首次 convergence sentinel 的 evidence chain、固定绑定、population
reconciliation、inner-training-only tuning、outer-training final refit、B-lock、
prediction/performance fail-closed 边界和隐私清理均满足本轮审查要求。

结论：`ACCEPT_WITH_FINDINGS`。允许进入 R6-7；R6-7 仍须遵守其自身授权范围，
本报告不改变 formal W08 或 B validation 的现有门禁。
