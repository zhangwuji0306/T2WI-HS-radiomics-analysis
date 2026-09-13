# R6-5 numerical equivalence remediation review

## Disposition

`accepted with non-blocking findings` — 项目原生结论：`R6-5 NUMERICAL EQUIVALENCE AND REGRESSION ACCEPTED`。

R6-5 数值等价性、selection reducer/grid/tie-break 等价性、canonical coordinate/provenance binding 和回归验证均满足当前授权范围。W08 gate 继续保持 `HOLD`。唯一允许的下一阶段是单独分包执行 R6-6/G3R；不得直接进入 R6-6.5 或正式 W08。R6-6.5 仍须在 G3R 接受后强制执行。

## Resolution of first-round blockers

### Performance-free selection path

`tests/test_r6_5_validation.py` 不再调用 `tune_elastic_net`，也不调用 `uno_c_index` 或任何 C-index、AUC、Brier、calibration、prediction-performance 路径。selection 测试通过 `inspect.getsource` 分别取得历史和当前 `_select_candidate` 的函数体，将历史性能字段 token 替换为 `selection_score`，编译为独立的内存函数后直接执行。替换后的源码还对残留性能 token fail closed。

独立运行时检查确认，两个 reducer 的可执行代码均不引用调参或性能函数；输入只包含预先赋值的非性能 utility。测试没有通过删除断言或 synthetic outcome 标签掩盖底层指标调用。第一轮关于实际生成 Uno C-index 的阻断已解除。

### Complete 4 × 100 selection fixture

selection fixture 包含冻结 alpha `[0.1, 0.5, 0.9, 1.0]` 与每个 alpha 的 100 个 lambda ratio，共 400 条 candidate records。测试验证了：

- `lambda_count=100`，每个 alpha 恰有 100 条记录；
- lambda indices 完整覆盖 `0..99`；
- ratio 从 `1.0` 到 `1e-4`，在 log 空间等距；
- candidate 的 index-to-ratio 映射与 `np.geomspace(1.0, 1e-4, 100)` 一致；
- lambda indices 37 与 42 的 utility 差为 `5e-13`，进入注册的 `1e-12` tie window；
- tie-break 先选择更大的 lambda ratio，再按冻结顺序选择更小的 alpha index。

历史与当前 reducer 均选择 `alpha=0.1`、`alpha_index=0`、`lambda_index=37`、`lambda_ratio=0.031992671377973826`。该证据证明的是完整候选记录上的 reducer、grid mapping 与 tie-break semantics 等价性；它不声称执行了 100 次 solver fit、inner CV 或任何 performance calculation。

## Numerical and solver equivalence

历史 solver 可从 commit `899cf71e1895985f1f2eb5daf482d1c595dad154` 的 `prognosis_analysis/scripts/w08_nested_cv.py` 恢复，Git blob SHA-1 为 `075fe9624d8b8130f31016cd488d926feff3486c`，历史 Elastic-Net budget 明确为 `max_iter=250`。

允许的 deterministic synthetic direct-fit 比较在注册阈值 `1e-10` 内通过。旧/新 objective、coefficient vector 和仅用于实现比较的 synthetic risk-score vector 完全一致，最大绝对差均为 `0.0`，两侧均在 6 次迭代后以相同原因收敛。该比较未生成正式 prediction 或 performance metric，阈值没有放宽。

当前 solver 仍统一使用 `max_iter=3000` 和 `tolerance=1e-7`。objective、gradient、convergence criteria、zero start、`warm_start=false`、penalty semantics、candidate pools/order、alpha/lambda semantics、W07 split、population 和 `minimumROISize=10` 均未改变。

已接受 R6-4A stress evidence 保持原绑定：16/16 converged，0 failed，最大迭代数 1814，所有候选统一使用 3000 次预算，无 candidate deletion 或 skipping。

## Coordinate and provenance binding

canonical coordinate 为 `repeat=1 / outer_fold=1 / population=R_high`。full outer train/validation 为 `314/79`；eligible 为 `282/67`；R_high 状态计数为 train `282/21/11`、validation `67/7/5`（extractable / structural absence / technical small ROI）。

两侧 full/eligible ID hashes、P3B train/validation/combined state hashes、W07 split hash、R6-5R evidence hashes、W04/W07A/technical-freeze/config/candidate-pool/solver bindings 均与实际文件匹配。P3B 仍使用 `minimumROISize=10`，eligibility 位于 provider transform 之后、任何 preprocessing 之前。`AOnlyFoldFeatureProvider` 仍仅在 full outer training side 拟合；validation IDs 未用于 provider 或 boundary fitting。

## Regression and stage boundary

锁定环境独立复跑结果：

| Suite | Tests | Failures | Errors | Skips | Exit |
|---|---:|---:|---:|---:|---:|
| R6-4A/W08 targeted plus R6-5 | 81 | 0 | 0 | 0 | 0 |
| W07, B-blinding, A-access binding/negative | 37 | 0 | 0 | 0 | 0 |
| compileall | — | 0 | 0 | 0 | 0 |

81 项套件中的 formal-output transaction case 使用临时目录、mock runner 和单条 synthetic result，只验证发布事务，不读取真实 A/B 数据、不拟合模型，也不产生真实预测或性能结果。

既有 provenance reconciliation 套件仍为 32 tests、1 failure、7 errors、0 skips：7 个 errors 均来自同一 `manifest.successor_revision_history.pre_w08_sop[1]` snapshot mismatch，1 个 failure 来自既有 `execution_status` failure-summary wording assertion。modeling protocol 单独复跑为 7 tests、1 个相同 snapshot error。R6-5 未改写这些绑定或测试以绕过失败；该既有问题不改变本轮两个阻断的返修结论。

`B_data_read=false`、`B_reader_invoked=false`、`B_source_opened=false`、`B_statistics_generated=false`。未执行真实 A-side outer-final Cox、正式 W08、R6-6/G3R、R6-6.5、W09 或 B validation；未生成正式 risk score、prediction、performance artifact 或 model-freeze lock。第一轮拒绝报告保持原文件，Reviewer 未修改 Worker evidence、代码、配置或协议，也未提交或推送。

## Non-blocking findings

1. Worker audit 将 direct-fit 与 selection fixture 合称为 `outcome-free synthetic fixtures`；其中 selection fixture 确实无 outcome，但 direct-fit 使用 deterministic synthetic survival time/event。其表格和 JSON 已准确标明 direct-fit fixture 类型与 event count，因此这是措辞精度问题，不影响授权边界或数值证据。
2. Worker audit 的 worktree inventory 只列出 JSON、audit 和测试文件，遗漏同样保留为未跟踪文件的第一轮 review。Reviewer 报告写入前的 Git status 可明确区分四个 Worker/首轮 R6-5 文件，且遗漏项是审查报告，不是代码、数据或患者级产物，因此不构成下游阻断。
