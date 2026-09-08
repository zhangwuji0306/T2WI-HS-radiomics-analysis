# T2WI-HS-radiomics-analysis `n_init`快速等价性验证工作流

## 一、目标与适用状态

本工作流用于判定W08 fold-specific K-means当前实现的`n_init=10`与冻结主配置的`n_init=100`是否产生相同的实际模型输入。

当前formal W08可继续运行，但在本工作流形成结论前，不读取、解释或比较其预测、性能和模型产物。验证不得修改formal W08代码、当前运行目录或已有审计记录。

本工作流应在单次6小时执行窗口内形成下列结论之一：

```text
EXACT_EQUIVALENCE
INPUT_EQUIVALENT_WITH_NUMERICAL_DIFFERENCE
NOT_EQUIVALENT
INCOMPLETE
```

## 二、共同边界

### 2.1 允许读取

```text
habitat_analysis/output/local_global_diagnostic_A_post_slic_fix/supervoxel_mean_A.csv
prognosis_analysis/output/outer_splits_A.csv
prognosis_analysis/configs/w07_outer_splits.json
habitat_analysis/configs/main_cross_case_kmeans_k2_4mm.json
prognosis_analysis/modeling_protocol.json
prognosis_analysis/scripts/w08_formal_run_a.py
prognosis_analysis/scripts/w08_technical_preflight_a.py
feature_extract/scripts/data_split_guard.py
```

验证仅使用A technical数据中的下列字段：

```text
影像号
reader
sv_label
Mean
n_tumor_voxels
outer repeat/fold
train/validation role
```

### 2.2 禁止读取或执行

```text
DFS/event/time
其他结局变量
临床变量
B数据
Cox拟合
风险分数
预测
AUC/C-index/Brier score/校准
模型比较
正式W08结果审阅
```

### 2.3 写入边界

所有执行结果只写入：

```text
prognosis_analysis/output/n_init_equivalence_A/
```

不得写入或修改：

```text
prognosis_analysis/output/w08_formal_A/
prognosis_analysis/model_freeze_lock.json
任何现有freeze、protocol、binding、baseline或正式审计文件
```

患者级差异明细只保存在本地输出目录，不进入Git。仓库只允许保留验证代码、测试和不含患者标识的聚合审阅报告。

## 三、N1：独立验证入口实现

### 3.1 目标

建立不依赖formal W08运行目录、不初始化PyRadiomics、不生成三维影像缓存的独立验证入口。

### 3.2 交付物

```text
prognosis_analysis/scripts/validate_kmeans_n_init_equivalence.py
tests/test_kmeans_n_init_equivalence.py
```

### 3.3 命令行接口

脚本至少支持：

```text
--workers 1|2
--stop-on-first-material-difference
--output-dir <path>
```

默认设置：

```text
workers=2
stop_on_first_material_difference=true
output_dir=prognosis_analysis/output/n_init_equivalence_A
```

不得使用超过2个fold级并行进程。每个进程必须限制为单线程。

### 3.4 输入检查

在任何K-means拟合前完成以下检查：

1. supervoxel表仅包含`reader=R1`。
2. `(影像号, sv_label)`在病例内唯一。
3. `Mean`均为有限数值。
4. `n_tumor_voxels`均为正整数。
5. supervoxel表覆盖完整A technical队列。
6. outer split包含`10 repeats × 5 folds`。
7. 每个fold的training与validation互斥，合并后覆盖完整A队列。
8. validation ID不进入center或boundary拟合。
9. K-means固定为`K=2`、`k-means++`、`max_iter=300`、`tol=1e-4`。
10. fold seed固定为`12345 + 2000 + 10 × (repeat - 1) + outer_fold`。
11. 每例含`n_i`个supervoxels时，每个supervoxel权重为`1/n_i`，每例总权重为1。

任一检查失败时写出不含患者标识的错误摘要，状态设为`INCOMPLETE`并停止。

### 3.5 对照计算

对每个固定outer fold，使用完全相同的training values、sample weights和seed分别执行：

```python
KMeans(n_clusters=2, random_state=seed, n_init=10)
KMeans(n_clusters=2, random_state=seed, n_init=100)
```

两组centers均从低到高排序，boundary均按下式计算：

```text
(H-low center + H-high center) / 2
```

不得通过修改随机种子、初始化方式、容差、最大迭代次数、样本权重或训练人群缩短计算。

### 3.6 差异传播检查

当任一fold的centers或boundary不完全相同时，使用两个boundary分别对该fold全部training和validation病例计算：

```text
Mean < boundary  -> H-low
Mean >= boundary -> H-high
```

根据`n_tumor_voxels`汇总每例：

```text
R_low_voxel_count
R_high_voxel_count
```

支持状态固定为：

```text
0    = structural_absence
1-9  = technical_small_roi
>=10 = extractable
```

必须比较：

- supervoxel habitat标签；
- R_low/R_high体素数；
- R_low/R_high支持状态；
- R_low、R_high及dual eligible populations；
- paired comparator populations；
- `sv_median_minus_boundary`。

验证不重建三维mask，不重新提取影像组学特征。boundary完全相同时，基于相同supervoxel标签和固定下游函数，可直接确认相应mask及派生输入一致；boundary不同时，以本节病例级传播检查判定影响。

### 3.7 提前停止

下列任一情况属于material difference，可立即停止后续fold并输出`NOT_EQUIVALENT`：

- 任一supervoxel标签变化；
- 任一病例R_low或R_high体素数变化；
- 任一支持状态变化；
- 任一eligible population变化；
- 任一paired comparator population变化；
- 任一病例`sv_median_minus_boundary`发生非零变化。

只有完成全部50个fold，才允许输出`EXACT_EQUIVALENCE`或`INPUT_EQUIVALENT_WITH_NUMERICAL_DIFFERENCE`。

### 3.8 测试要求

测试使用合成数据，至少覆盖：

1. 10与100产生完全相同结果时的全量通过路径。
2. 额外初始化产生更优解时的差异路径。
3. boundary变化但标签不变时，`sv_median_minus_boundary`仍触发差异。
4. 标签变化导致体素数、支持状态和eligible population变化。
5. validation ID进入拟合时拒绝。
6. patient-balanced权重错误时拒绝。
7. 缺失fold、train/validation重叠、非法Mean或非法体素数时拒绝。
8. 提前停止后不得错误声明50/50 folds完成。
9. 输出不包含DFS、临床、B、预测或性能字段。

### 3.9 N1验收条件

- 新入口不导入或调用Cox、性能或B reader路径。
- 新入口不实例化完整formal provider，不创建PyRadiomics extractor。
- 所有测试通过。
- `compileall`通过。
- 不修改现有formal W08代码、配置和运行目录。

N1未通过独立复核时不得执行N2。

## 四、N2：A-only 50-fold快速验证

### 4.1 前置条件

- N1已接受用于执行。
- 当前formal W08进程未被本工作流修改或中断。
- 锁定`t2_radiomics`环境可用。
- 独立输出目录不存在未归档的同名运行结果；不得覆盖既有结果。

### 4.2 运行设置

在独立PowerShell中设置：

```powershell
$env:OMP_NUM_THREADS = "1"
$env:MKL_NUM_THREADS = "1"
$env:OPENBLAS_NUM_THREADS = "1"
$env:NUMEXPR_NUM_THREADS = "1"
```

执行：

```powershell
.\tools\run_t2_radiomics.ps1 -PythonArguments @(
    "prognosis_analysis/scripts/validate_kmeans_n_init_equivalence.py",
    "--workers", "2",
    "--stop-on-first-material-difference",
    "--output-dir", "prognosis_analysis/output/n_init_equivalence_A"
)
```

执行监测遵循项目`AGENTS.md`。不得通过启动第二个formal W08、增加到3个以上并行进程或读取当前W08性能结果解决超时。

### 4.3 本地产物

#### `n_init_fold_comparison.csv`

每个已完成fold一行，至少包含：

```text
repeat
outer_fold
seed
training_patient_count
training_supervoxel_count
center_low_10
center_high_10
boundary_10
inertia_10
n_iter_10
center_low_100
center_high_100
boundary_100
inertia_100
n_iter_100
centers_exact_equal
boundary_exact_equal
inertia_exact_equal
material_difference
```

#### `n_init_affected_cases.csv`

仅在发现差异时生成，包含匿名病例号及病例级影响明细，只保存在本地。

#### `n_init_equivalence_summary.json`

至少包含：

```text
status
folds_completed
folds_exact_equal
folds_with_center_difference
folds_with_boundary_difference
affected_supervoxels
affected_cases
support_state_changes
eligibility_changes
paired_population_changes
G_value_changes
stopped_early
outcome_data_read=false
clinical_data_read=false
B_data_read=false
cox_fit_generated=false
prediction_generated=false
performance_generated=false
```

#### `n_init_equivalence_report.md`

只记录聚合结果、执行边界和最终判定，不含患者标识、患者级数据、本机绝对路径或formal W08性能。

### 4.4 N2完成条件

满足以下任一条件即完成：

1. 发现首个material difference，证据足以输出`NOT_EQUIVALENT`；
2. 50/50 folds全部完成，证据足以输出严格或条件等价结论；
3. 输入、环境或执行错误导致无法形成前两类结论，输出`INCOMPLETE`并停止。

## 五、N3：独立结果复核与项目结论

### 5.1 复核对象

```text
prognosis_analysis/scripts/validate_kmeans_n_init_equivalence.py
tests/test_kmeans_n_init_equivalence.py
prognosis_analysis/output/n_init_equivalence_A/n_init_fold_comparison.csv
prognosis_analysis/output/n_init_equivalence_A/n_init_equivalence_summary.json
prognosis_analysis/output/n_init_equivalence_A/n_init_equivalence_report.md
```

患者级明细只用于本地核对，不进入仓库审阅材料。

### 5.2 复核要求

1. 确认两个分析臂除`n_init`外无差异。
2. 确认50个fold、seed、training IDs和sample weights与正式设计一致。
3. 确认validation未参与拟合。
4. 确认未读取结局、临床或B数据。
5. 确认未调用Cox、预测或性能路径。
6. 确认提前停止只用于证明不等价，未用于声明等价。
7. 确认患者级结果未进入Git材料。
8. 确认当前formal W08目录和进程未被验证流程修改。

### 5.3 最终判定规则

#### `EXACT_EQUIVALENCE`

必须满足：

```text
50/50 folds完成
所有ordered centers位级一致
所有boundary位级一致
所有inertia一致
无病例级或模型输入差异
```

#### `INPUT_EQUIVALENT_WITH_NUMERICAL_DIFFERENCE`

仅在50/50 folds完成，且centers存在数值差异但下列各项完全一致时使用：

```text
boundary
supervoxel标签
R_low/R_high体素数
支持状态
eligible populations
paired populations
全部W08模型输入
```

该状态不能自动授权接受当前formal W08，须由protocol owner裁定。

#### `NOT_EQUIVALENT`

任一实际W08模型输入变化即成立，不要求继续完成剩余fold。当前`n_init=10`运行不得作为冻结主分析结果，也不得根据其性能决定参数选择。

#### `INCOMPLETE`

未发现material difference但未完成50/50 folds，或发生输入、环境、运行及证据完整性错误时使用。该状态不支持任何等价性结论。

## 六、结论后的允许动作

### 6.1 `EXACT_EQUIVALENCE`

提交脱敏聚合报告供protocol owner审阅。是否接受当前formal W08由protocol owner决定；未经决定，不修改生产代码或进入W09。

### 6.2 `INPUT_EQUIVALENT_WITH_NUMERICAL_DIFFERENCE`

保持当前formal W08结果待定，提交差异范围和实际输入一致性证据供protocol owner裁定，不以性能辅助裁定。

### 6.3 `NOT_EQUIVALENT`

保持当前formal W08结果隔离，不进入W09。后续`n_init=100`代码修订、技术复核及formal重跑应另行授权，不属于本工作流。

### 6.4 `INCOMPLETE`

停止下游动作，仅报告具体阻断点。不得把部分fold无差异解释为总体等价。
