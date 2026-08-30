# T2WI-HS-radiomics-analysis 冻结前代码修复任务书

**适用基准版本：** commit `91e32984d26a375d88f95be31aae8559c69c0579`\
**目标：** 在不读取结局、不使用 B 集进行方法选择的前提下，完成正式生境分析冻结前最后一轮代码修复，使 A 集定义、bootstrap 门禁、数据隔离、预处理 provenance 与特征提取流程具有代码级强制约束。

---

# 一、总原则

本轮只修复分析基础设施和技术流程，不进行任何结局分析。

必须保持以下原则：

1. 不读取 DFS、OS、CSS 或其他结局。
2. 不使用 B 集进行参数选择、ICC 筛选、稳定性判断或方法比较。
3. 不修改已经冻结的 M1 方法学定义：
   - muscle mean normalization；
   - `[1,1,2] mm`；
   - 4 mm 3D SLIC；
   - `[4,4,2]` voxel supergrid；
   - 全部有效超体素；
   - 每病例总权重=1；
   - cross-case K-means K=2。
4. 当前正式目录不得由 smoke/preflight 运行覆盖。
5. 所有正式冻结操作必须通过代码门禁，而不能仅依赖人工记忆或文档约定。
6. 修复代码后，首先核对重新生成的 A393 与当前 A393 是否完全一致；只有确认一致，才允许沿用已有 post-SLIC 技术结果。

当前 SLIC 尺度修复已经正确实现，不应回退。

---

# 二、Bootstrap 方案：20 / 200 / 1000 三级模式

## 2.1 设计决定

将 bootstrap 明确定义为三个模式：

| 模式          |   次数 | 用途             | 能否解锁 freeze |
| ----------- | ---: | -------------- | ----------- |
| `smoke`     |   20 | 检查代码、I/O、数值稳定性 | 否           |
| `preflight` |  200 | 当前电脑上的正式前技术测试  | 否           |
| `formal`    | 1000 | 最终方法冻结         | 是           |

### 为什么 200 次适合作为测试

200 次对以下目的完全可用：

- 检查 bootstrap 是否能够稳定完成；
- 检查是否存在退化聚类；
- 初步观察中心和 boundary 分布；
- 检查病例 assignment stability；
- 检查 structural-state stability；
- 判断1000次正式计算是否值得继续。

而不建议把200直接作为最终 formal bootstrap，主要原因是当前方法使用 percentile 95% interval：

`2.5%–97.5%`

200 次中每侧尾部理论上只有约5个 bootstrap replicate，区间端点容易受少量 replicate 影响。

1000 次时每侧约25个 replicate，更适合作为最终冻结结果。

因此：

> **200次用于“是否值得继续正式运行”的技术预检；1000次仍作为最终冻结标准。**

如果机器无法一次完成1000次，不应降低到200，而应实现**断点续跑**。1000次可以分成若干批次完成。

---

# 三、任务 T01：修复 bootstrap 模式与正式冻结误触发风险

## 文件

`habitat_analysis/scripts/revised_workflow_technical.py`

## 涉及函数

- `stage4_bootstrap()`
- `fit_balanced_values()`
- `stage7_freeze()`
- CLI `main()`
- 建议新增：
  - `bootstrap_run_config()`
  - `bootstrap_checkpoint_path()`
  - `validate_formal_bootstrap()`

## 修改要求

### 1. 删除当前单一 `--smoke` 二元设计

改为：

```text
--bootstrap-mode smoke
--bootstrap-mode preflight
--bootstrap-mode formal
```

固定映射：

```text
smoke      = 20
preflight  = 200
formal     = 1000
```

正常运行不得允许随意覆盖 formal 次数。

如需要调试，可额外设置隐藏/开发参数，但任何非1000次运行均不得生成 formal 状态。

### 2. 三种运行必须写入不同目录

例如：

```text
bootstrap_stability_A_post_slic_fix/
    smoke/
    preflight/
    formal/
```

不得继续让20次与1000次写同一个：

```text
bootstrap_stability_summary.csv
```

### 3. summary 增加字段

至少包括：

```text
bootstrap_mode
n_bootstrap_requested
n_bootstrap_completed
n_bootstrap_success
random_seed
completion_status
formal_eligible
```

其中：

```text
formal_eligible = 1
```

只有：

```text
bootstrap_mode == "formal"
AND n_bootstrap_requested == 1000
AND n_bootstrap_completed == 1000
```

时才可能成立。

### 4. `stage7_freeze()` 不得仅检查 `bootstrap_operational_pass`

当前实现只检查 pass 字段，因此理论上 smoke 结果可能进入 freeze。

改为至少同时检查：

```text
bootstrap_mode == formal
n_bootstrap_requested == 1000
n_bootstrap_completed == 1000
bootstrap_operational_pass == 1
```

以及非退化拟合比例符合既定标准。

### 5. 实现 bootstrap 断点续跑

考虑本地算力有限，必须支持：

```text
0 → 200
200 → 400
400 → ...
→ 1000
```

建议每完成25或50 replicate 保存一次 checkpoint。

每个 replicate 必须保存明确的：

```text
bootstrap_index
seed
C_low
C_high
boundary_b
fit_status
```

恢复运行时：

- 已存在 index 不重新计算；
- 只执行缺失 index；
- 最终按 index 排序；
- 不得产生重复 replicate。

### 6. 保证中断前后确定性一致

不要依赖一个持续推进、无法恢复状态的全局 RNG。

建议每次 bootstrap 使用：

```text
seed = BASE_SEED + bootstrap_index
```

使：

```text
一次完成200次
```

与：

```text
先完成80次 + 后续恢复120次
```

得到完全相同结果。

---

## 验收测试

新增：

`tests/test_bootstrap_modes.py`

必须包含：

### test\_01\_smoke\_cannot\_unlock\_freeze

生成20次通过结果。

断言：

```text
bootstrap_operational_pass 可以为1
formal_eligible 必须为0
stage7_freeze 必须拒绝
```

### test\_02\_preflight\_200\_cannot\_unlock\_freeze

生成200次通过结果。

断言：

```text
bootstrap_mode == preflight
n_bootstrap_requested == 200
formal_eligible == 0
stage7_freeze 拒绝
```

### test\_03\_formal\_requires\_1000

模拟：

```text
formal + 999 completed
```

freeze 必须失败。

只有：

```text
formal + 1000 completed
```

才可进入下一门禁。

### test\_04\_resume\_reproducibility

比较：

```text
一次性200次
```

与：

```text
100次 + resume 100次
```

所有 bootstrap center 和 boundary 必须完全一致或满足机器精度一致。

### test\_05\_output\_isolation

smoke、preflight、formal 输出不得互相覆盖。

---

# 四、任务 T02：修复 A/B split 的位置对齐风险

## 文件

`prognosis_analysis/scripts/build_model_dataset.py`

## 函数

`cohort_table()`

## 当前风险

当前代码先从 scanner 表计算 `is_a`，然后直接与 manifest 的 `影像号` 按数组位置组合。

如果：

```text
manifest.csv
scanner_map.csv
```

患者顺序不同，就可能发生静默错误分组。

## 修改要求

必须首先：

```python
manifest.merge(scanner, on="影像号", validate="one_to_one")
```

然后在同一行上判断：

```text
GE MEDICAL SYSTEMS
DISCOVERY MR750
3.0 T
```

禁止再通过两个 dataframe 的行位置关联 split。

同时增加断言：

```text
影像号唯一
scanner mapping 唯一
不存在无法匹配 scanner 的目标病例
```

---

## 验收测试

新增：

`tests/test_split_alignment.py`

### test\_01\_order\_independent

构造相同数据：

- manifest 正序；
- scanner 随机打乱。

断言 A/B split 完全相同。

### test\_02\_duplicate\_scanner\_rejected

scanner 同一 ID 两行。

必须异常退出。

### test\_03\_missing\_scanner\_rejected

目标患者没有 scanner mapping。

必须明确报错，不得默认归为 B。

---

# 五、任务 T03：建立纯技术 A 集清单，解除 habitat 对 prognosis 数据集依赖

## 新文件

`habitat_analysis/scripts/build_technical_cohort_manifest.py`

## 修改文件

`habitat_analysis/scripts/technical_dry_run_A.py`

## 当前问题

`technical_dry_run_A.py` 当前从：

```text
prognosis_analysis/output/modeling_v2/dataset_primary_raw_A.csv
```

读取 A393 ID。虽然只读取 `影像号`，但该文件属于包含临床和结局信息的 prognosis 数据链。

技术生境分析不应依赖 prognosis 输出。

## 新技术清单

仅允许读取：

```text
feature_extract/output/manifest.csv
feature_extract/output/scanner_map.csv
habitat_analysis/output/high_signal_eligibility_audit/...
```

禁止读取：

```text
prognosis_analysis/data/*
prognosis_analysis/output/modeling_v2/*
```

输出：

```text
habitat_analysis/output/technical_cohort_manifest/
    cohort_A_lenient.csv
    cohort_A_strict.csv
    cohort_summary.json
    provenance.json
```

预期：

```text
A lenient = 393
A strict  = 137
```

## 修改 `technical_dry_run_A.load_cases()`

删除：

```text
A_TABLE
```

改为读取：

```text
cohort_A_lenient.csv
```

---

## 验收测试

新增：

`tests/test_technical_cohort_manifest.py`

必须测试：

1. A393 数量正确；
2. strict A137 为 A393 真子集；
3. scanner 表顺序变化不影响结果；
4. 生成技术队列期间不需要 prognosis 文件；
5. 删除/屏蔽 prognosis 目录后仍能成功生成技术队列。

---

# 六、任务 T04：修复后首先进行 A393 身份一致性审计

这是**本轮最重要的运行时验收之一**。

修改代码后重新生成：

```text
new_A393.csv
```

与目前 post-SLIC 使用过的 A393 ID：

```text
old_A393.csv
```

比较：

```text
old - new
new - old
intersection
```

输出：

```text
A393_identity_audit.csv
A393_identity_audit.md
```

## 判定

### 如果 symmetric difference = 0

允许：

- 保留现有 corrected post-SLIC A393 结果；
- 不必重跑 SLIC；
- 继续200次 preflight bootstrap。

### 如果 symmetric difference > 0

必须停止。

以下所有结果失效并重算：

```text
A393 M1 center
structural state
local-global diagnostics
bootstrap
technical robustness
A137 sensitivity
freeze features
```

不得进入结局分析。

---

# 七、任务 T05：真正执行 B 集冻结前不可见

## 文件

`prognosis_analysis/scripts/stage6_qc.py`

## 函数

- `load_pairs()`
- `process_table()`

## 当前问题

虽然候选特征只根据 `ICC_A` 筛选，但脚本同时计算：

```text
icc_B
n_B
```

因此 B 的可靠性表现已经在冻结前暴露。

## 修改要求

冻结前 stage6 只能计算：

```text
icc_A
n_A
```

删除：

```text
icc_B
n_B
```

B ICC 应移动到：

```text
post_freeze_validation
```

阶段。

---

## 同时修改

`feature_extract/scripts/extract_features.py`

`feature_extract/scripts/extract_features_filters.py`

增加：

```text
--split A
--split B
--split all
```

冻结前推荐默认：

```text
--split A
```

运行 B 或 all 时必须进行 B-unlock 检查。

---

## 验收测试

新增：

`tests/test_b_blinding.py`

必须验证：

1. stage6 prefreeze 输出不含 `icc_B`；
2. prefreeze 模式不能生成 B reliability report；
3. 未存在合法 freeze lock 时，B validation 模式拒绝运行；
4. A-only 流程完全不需要读取 B 数据。

---

# 八、任务 T06：建立 `freeze_lock.json`

## 文件

建议：

`habitat_analysis/scripts/revised_workflow_technical.py`

也可拆出：

`habitat_analysis/scripts/freeze_lock.py`

## 生成时机

只有 `stage7_freeze()` 全部门禁通过后才能生成。

## 至少包含

```text
analysis_id
git_commit

A393_id_hash
A137_id_hash

manifest_hash
scanner_map_hash
high_signal_screen_hash

preprocessing_config_hash
slic_config_hash

slic_supergrid_voxels_xyz
slic_actual_supergrid_mm_xyz

global_center_low
global_center_high
global_boundary_b

bootstrap_mode = formal
bootstrap_requested = 1000
bootstrap_completed = 1000
bootstrap_success
bootstrap_summary_hash

technical_failure_case_hash

main_feature_dictionary_hash

outcome_columns_read = false
B_data_read = false

freeze_timestamp
```

## 下游要求

`prognosis_analysis/scripts/build_model_dataset.py`

正式读取临床/结局文件前必须验证：

```text
freeze_lock.json
```

不存在或不匹配时停止。

---

## 验收测试

新增：

`tests/test_freeze_lock.py`

测试：

- smoke不能产生 lock；
- preflight不能产生 lock；
- formal未完成不能产生 lock；
- config 修改后旧 lock 无效；
- A393 ID 改变后旧 lock 无效；
- 合法 lock 才允许 prognosis 阶段启动。

---

# 九、任务 T07：增强 preprocessing 断点续跑有效性

## 文件

`feature_extract/scripts/preprocess_core.py`

## 函数

- `pipeline_stamp()`
- `build_metadata()`
- `case_is_current()`

## 当前问题

当前 `.pipeline_stamp` 主要依赖：

```text
PIPELINE_VERSION
preprocessing config
```

而 `case_is_current()` 没有重新比较当前输入文件是否发生变化。

## 修改要求

保存并比较当前输入至少：

```text
relative path
file size
mtime_ns
```

建议另外记录：

```text
git_commit
```

如果：

```text
输入文件 size/mtime 变化
或 pipeline code version 变化
或 preprocessing config 变化
```

则：

```text
case_is_current() = False
```

不要求每次 skip 检查都重新 SHA256 整个大型 NRRD，以避免不必要 I/O。

正式处理时仍可记录更强 provenance。

---

## 验收测试

扩展：

`tests/test_preprocess_stamp.py`

新增：

- input mtime 改变 → stale；
- input size 改变 → stale；
- config 改变 → stale；
- pipeline version 改变 → stale；
- 完全未变化 → current。

---

# 十、任务 T08：σA 计算必须 fail-fast

## 文件

`feature_extract/scripts/compute_sigma_a.py`

`feature_extract/scripts/compute_sigma_a_filters.py`

## 当前问题

当前存在病例缺失时可能记录 warning 后继续冻结 σA。

## 修改要求

正式计算必须同时满足：

```text
n_expected_cases == n_used_cases
missing_cases == 0
empty_roi_cases == 0
failed_cases == 0
```

否则：

```text
不覆盖现有 sigma_a.json
不覆盖 sigma_a_filters.json
退出非0状态
```

输出错误清单。

建议使用：

```text
*.tmp
```

完整成功后再 atomic replace。

JSON 增加：

```text
n_cases_expected
n_cases_used
n_cases_failed
complete_case_pass
```

---

## 验收测试

新增：

`tests/test_sigma_a_complete.py`

测试：

1. 缺1例 → 不写正式JSON；
2. 空ROI → 不写；
3. filter失败 → 不写；
4. 全部成功 → atomic promotion。

---

# 十一、任务 T09：修复 `extract_features.py --force` 空目录 bug

## 文件

`feature_extract/scripts/extract_features.py`

## 当前问题

`_empty_like()` 使用全局：

```python
pd.DataFrame
```

但 `pandas as pd` 当前只在 `main()` 内导入。

## 修改

将：

```python
import pandas as pd
```

移动到模块顶层。

## 验收测试

新增：

`tests/test_force_empty_output.py`

模拟：

```text
全新空 output
--force
```

验证：

- 不出现 `NameError`；
- 正常创建结果；
- filtered extractor 调用共享 helper 时同样正常。

---

# 十二、任务 T10：更新方法文档

必须同步修改：

```text
PROJECT_STATUS.md
habitat_analysis/analysis_freeze.md
habitat_analysis/README.md
AGENTS.md（如涉及执行规则）
```

明确写入：

```text
bootstrap smoke = 20
bootstrap preflight = 200
bootstrap formal = 1000
```

并说明：

> 200次 bootstrap 仅用于正式冻结前技术稳定性测试，不构成正式冻结依据。

同时明确：

> B集在 freeze\_lock 生成前禁止用于 ICC、分布诊断、参数调整或模型选择。

以及：

> habitat A集身份来自独立 technical cohort manifest，不再依赖 prognosis dataset。

---

# 十三、200次 preflight 的执行和判读

修复完成并确认 A393 身份没有变化后，执行：

```text
bootstrap-mode = preflight
n = 200
```

建议每50次保存一个累计检查点：

```text
50
100
150
200
```

重点观察：

```text
nondegenerate_fit_rate
bootstrap boundary
boundary 95% interval
boundary interval width / center distance
case assignment stability median
case assignment stability p05
structural state stability median
structural state stability p05
delta H_high_fraction
```

200次结果只做三类判断：

### CLEAR FAIL

如果主要稳定性指标明显无法达到原定标准，则停止，不运行1000次。

先检查方法或实现问题。

### MARGINAL

如果结果非常接近门槛，例如某指标随50/100/150/200变化较明显：

不做方法选择，也不宣布失败。

继续正式1000次后判断。

### CLEAR PASS

如果：

- 200次全部或几乎全部成功；
- boundary 分布稳定；
- assignment stability 有明显裕量；
- 结构状态稳定；
- 不存在异常病例集中；

则认为正式1000次值得运行。

但仍：

```text
formal_eligible = 0
```

---

# 十四、正式1000次的低算力执行策略

不要求一次完成。

应通过 checkpoint/resume 分批运行，例如：

```text
200
+200
+200
+200
+200
=1000
```

只要每个 bootstrap index 与 seed 固定，结果与一次性完成1000次应一致。

因此解决算力不足的正确方法是：

> **分批 + 断点续跑**

而不是：

> **把正式1000次降低为200次。**

如果未来经过纯技术运行时间评估后确认1000次不可实现，才考虑在**不查看结局、不查看B结果的情况下**提前做 protocol amendment，将正式次数改为500等折中值。

不应在看到200次结果后，根据“结果好不好”决定把正式次数从1000改成200或500。

---

# 十五、最终代码验收

所有修改完成后运行：

```powershell
conda run -n t2_radiomics --no-capture-output python -m compileall -q feature_extract/scripts habitat_analysis/scripts prognosis_analysis/scripts tests
```

然后：

```powershell
conda run -n t2_radiomics --no-capture-output python -m unittest discover -s tests -p "test_*.py"
```

要求：

```text
0 failure
0 error
```

然后依次执行：

```text
1. technical cohort manifest rebuild
2. A393 identity audit
3. A137 identity/subset audit
4. 20 bootstrap smoke
5. 200 bootstrap preflight
```

此时仍不得读取结局。

只有：

```text
A393 identity audit = PASS
A137 subset = PASS
all code tests = PASS
200 preflight 无明显技术失败
```

以后，才启动：

```text
1000 formal bootstrap
```

正式1000次完成后：

```text
stage7 freeze
→ freeze_lock.json
```

最后才允许：

```text
A clinical + DFS
```

B 集仍保持锁定，直到 A 内方法、特征和模型全部冻结后再进行一次性外部验证。

---

# 十六、智能体完成本任务时必须提交的报告

维护智能体不能只回复“已修复”。

必须提交：

```text
1. 修改文件清单
2. 每个修改函数
3. 新增测试清单
4. unittest 总测试数及结果
5. A393 identity audit 结果
6. A137 subset audit 结果
7. smoke bootstrap 是否成功
8. preflight 200 bootstrap 是否成功
9. preflight关键稳定性指标
10. 是否仍保持 outcome_columns_read=false
11. 是否仍保持 B_data_read=false
12. 是否允许进入 formal 1000 bootstrap
```

如果 A393 identity audit 的 symmetric difference 非0：

必须明确停止，不能继续 bootstrap，并报告需要重算的 post-SLIC 阶段。
