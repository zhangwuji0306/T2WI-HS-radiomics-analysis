# P1A A-only reader 安全审计

## 审计范围与时间

- 审计时间：2026-09-02T14:23:43+08:00。
- 基线提交：`c7158a656b82f956f9b559a2e7bb1f5d5735f8c6`。
- 审计对象：`feature_extract/scripts/data_split_guard.py` 的三个显式 reader、兼容别名，以及 W05/W06/W08 A-only 正式调用链。
- 数据边界：仅使用临时 synthetic fixture 和内存对象；未读取真实 B source、患者级数据或患者级缓存；未执行 Cox、性能指标、预测或 50-fold preflight。
- W08 状态保持 `HOLD`；科学冻结参数、W07 split、候选池和 B 不可读边界未改变。

## Synthetic bypass reproduction

恶意 synthetic reader 返回同时含有 allowlisted A 行和 disallowed B 行的 pandas DataFrame；调用分别指定 A-only 或 B-only `allowed_ids`。预期是授权过滤发生在应用级行物化之前，或至少拒绝任意未声明的 reader。

实际结果：

| 入口 | allowlist | 返回的 synthetic ID | 结论 |
|---|---|---|---|
| `read_technical_A` | A1 | A1、B1 | bypass confirmed |
| `read_A_outcomes` | A1 | A1、B1 | bypass confirmed |
| `read_B_validation` | B1 | A1、B1 | bypass confirmed |
| `read_technical_data` | A1 | A1、B1 | bypass confirmed |
| `read_a_outcome` | A1 | A1、B1 | bypass confirmed |
| `read_b_data` | B1 | A1、B1 | bypass confirmed |
| `read_b_csv` | B1 | A1、B1 | bypass confirmed |
| `read_b_excel` | B1 | A1、B1 | bypass confirmed |

根因位于 `_authorized_read()`：`allowed_ids` 虽被规范化，但 `reader is not None` 时直接执行 `reader(path, *args, **kwargs)` 并原样返回，既不向 callable 传递 `allowed_ids`、`id_column` 或 `usecols`，也不对返回帧执行过滤。因而 B1 已在恶意 reader 内物化并进入应用 DataFrame，事后删除或筛选不构成授权隔离。

## 各 reader/alias 的授权时序结论

| API | source-open 前锁校验 | 默认 CSV/XLSX allowlist | 任意 `reader=` 的授权结果 |
|---|---|---|---|
| `read_technical_A` | 无 outcome/model lock；technical A 由调用方提供 allowlist 或显式 A-only `allow_full` | 是 | 不安全；callable 直接返回 |
| `read_A_outcomes` | first-stage freeze lock | 是 | 锁顺序安全，行授权不安全 |
| `read_B_validation` | first-stage freeze lock 后 model-freeze lock | 是 | 锁顺序安全，行授权不安全 |
| `read_technical_data` | 同 `read_technical_A` | 是 | 直接别名，仍可绕过 |
| `read_a_outcome` | 委托 `read_A_outcomes` | 是 | 委托后仍可绕过 |
| `read_b_data` | 委托 `read_B_validation` | 是 | 委托后仍可绕过 |
| `read_b_csv` / `read_b_excel` | 委托 `read_B_validation` | 是 | 委托后仍可绕过 |

锁时序单独通过：缺失 first lock 时，`read_A_outcomes` 和 `read_B_validation` 均在 reader 调用前 hard fail；first lock 有效但缺失 model-freeze lock 时，`read_B_validation` 也在 reader 调用前 hard fail。兼容别名沿用相同委托路径，未发现锁前调用。

## W05/W06/W08 production path 可达性

- W05 `build_model_dataset_a.py` 不暴露 `reader` 参数。技术 ID、混合 raw feature 和 A outcome 入口均使用默认 `data_split_guard` 路径，并传递 A allowlist；当前 W05 正式调用链未把任意 callable 注入 reader。
- W06 `run_w06()` 先验证 first-stage freeze lock、确认 model-freeze lock 不存在，再读取 technical A ID 和 A DFS 列；当前入口不暴露任意 callable。该脚本在接收一个已经被绕过的 A outcome DataFrame 后，未额外断言返回 ID 是 allowlist 的子集，`eligible` 结果随后直接用于 A modeling population，因此是实际的下游污染点。
- W08 `w08_formal_run_a.py` 的 `_read_a_csv()` 使用默认 `read_technical_A(..., allowed_ids=...)`，没有 reader 参数；`w08.run_w08()` 再以 code-bound W06 A population 做精确 ID 对齐。正式 W08 调用链未暴露任意 reader callable，混入额外 ID 的 in-memory frame 会在正式建模前被拒绝。
- `w08.run_w08_in_memory()` 是可供 synthetic/preflight 使用的 in-memory 接口，不是文件 reader；非 formal 模式允许调用方直接提供 frame，因此不应被当作 production ingestion boundary。

结论：当前 W05/W06/W08 正式入口没有实际传入任意 reader，故本次审计未证明正式运行已经通过该 callable 读取真实 B 数据；但共享 reader API 和兼容别名仍公开了可达的授权绕过，任何未来 connector 或直接调用一旦传入 `reader=` 即可触发。

## 正常 streaming 路径

现有 synthetic 回归保持正常路径的行隔离：

- CSV：混合 A/B feature source 通过默认 streaming reader 后只返回 allowlisted A 行。
- XLSX：混合 source 通过 identifier-first、selected-row/selected-column parser 后只返回 allowlisted A 行；disallowed 行的 sensitive cell 未被解析。

该结果不覆盖任意自定义 callable；漏洞仅存在于 `reader=` 分支。

## 风险等级与下游污染风险

风险等级：高（P1；对任何允许任意 `reader=` 的 production 或 connector 调用为 release-blocking）。

具体失败场景：first-stage lock 有效时，恶意 A outcome reader 返回 A+B；W06 当前逻辑按 `eligible` 处理所有返回行，并将其写入标记为 A393 的 modeling population。由此 B outcome 可进入 A-only 患者级建模输入，造成队列污染、事件统计污染和 A/B 盲态破坏。即使后续某个 builder 因 A cohort 过滤而不写出该行，B 行也已进入应用内存；不能以事后筛选替代 source-level authorization。

同样地，custom technical reader 可把 B feature 行带入 W05 中间 DataFrame；当前部分调用点会随后因 split 检查失败，但失败发生在行已物化之后。B validation reader 则可能把不属于授权 B 集的 A 行交给下游验证逻辑。当前真实 B 访问仍受锁阻断，风险来自 API 契约本身而非本次审计读取。

## 推荐 API/契约和 regression tests

### 最小整改

1. Production reader API 移除任意 `reader=` 参数；若保留该参数，默认必须对非 `None` callable 立即 hard fail。所有生产文件读取统一进入现有 CSV/XLSX streaming 实现。
2. 如确有 connector 需求，只接受显式标记的 authorized adapter，不接受普通 callable。契约至少为：

   ```text
   read_authorized(source, *, allowed_ids, id_column, usecols)
   ```

   adapter 必须在 source read 层执行 ID 和列过滤，并返回只含授权行的受控 row iterator/表；不得先返回 A+B DataFrame 再事后删除 B。锁校验必须继续位于 adapter/source open 之前。
3. 在 reader 返回边界增加 defense-in-depth：要求 identifier column 存在、规范化后唯一，并 hard fail `returned_ids - allowed_ids` 非空。该检查只能阻止下游继续，不能单独解决“B 已进入内存”的问题。
4. 兼容别名必须收敛到同一受控 API；不得继续接受可绕过显式授权契约的 positional/keyword reader。`allow_full=True` 仅限经明确声明的 A-only technical artifact，不得用于混合 source。

### 必须加入的 regression tests

- 对三个显式 reader 和全部兼容别名传入 malicious arbitrary callable：调用应在 callable 被执行前拒绝，或只能接受 authorized adapter；禁止返回包含 disallowed ID 的 DataFrame。
- first lock 缺失、model-freeze lock 缺失及 lock 内容无效：source/adapter 均不得被调用；覆盖全部 alias。
- synthetic CSV streaming：B 行和 B-only sensitive 列不得进入返回 DataFrame。
- synthetic XLSX streaming：identifier-first 过滤必须发生在非授权行的 sensitive cell 解析之前。
- W06 synthetic outcome：若 reader/adapter 返回 allowlist 外 ID，应在写出 A modeling population 前 hard fail，并验证不产生患者级 population artifact。
- W08 formal synthetic frame：额外 ID、非 A split 或非 A393 technical cohort 必须在建模前拒绝；`run_w08_in_memory()` 仅作为显式 synthetic/test boundary 使用。

## 科学冻结、B 数据与产物状态

- 科学冻结参数、candidate pool、W07 split 和 W08 HOLD 状态未修改。
- `B_data_read=false`；本审计未打开真实 B source，未生成 B 统计或预测。
- 本审计未创建、修改或提交患者级 artifact；仅新增本脱敏审计报告。

## Evidence files/commands

证据文件（均为仓库相对路径）：

- `feature_extract/scripts/data_split_guard.py`
- `prognosis_analysis/scripts/build_model_dataset_a.py`
- `prognosis_analysis/scripts/w06_endpoint_qc.py`
- `prognosis_analysis/scripts/w08_formal_run_a.py`
- `prognosis_analysis/scripts/w08_nested_cv.py`
- `tests/test_w05_access.py`
- `tests/test_w00b_integration.py`
- `tests/test_w06_endpoint_qc.py`
- `prognosis_analysis/W07A_pre_W08_remediation_baseline.md`

执行结果：

- `python -m unittest discover -s tests -p "test_w05_access.py"`：11 tests，PASS。
- `python -m unittest discover -s tests -p "test_w00b_integration.py"`：9 tests，PASS。
- `python -m unittest discover -s tests -p "test_w06_endpoint_qc.py"`：6 tests，PASS。
- synthetic malicious-reader/lock-order reproduction：8 个 reader/alias bypass 均复现；A first-lock、B first-lock、B model-lock 缺失均在 reader 调用前 hard fail。
- `python -m unittest discover -s tests -p "test_w08_nested_cv.py"`：16 tests 中 13 通过、3 个既有环境兼容性错误；错误均为当前 W08 代码/测试使用 `line_terminator`，而本机 pandas 2.2.2 的 `DataFrame.to_csv()` 不接受该关键字，与本 P1A reader bypass 无关，未对其进行修改。
- `git diff --check`：PASS。
