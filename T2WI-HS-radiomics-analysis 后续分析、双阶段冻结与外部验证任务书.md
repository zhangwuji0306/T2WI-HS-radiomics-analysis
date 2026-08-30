# T2WI-HS-radiomics-analysis 后续分析、双阶段冻结与外部验证任务书

**建议文件名：**  
`T2WI-HS-radiomics-analysis 后续分析与双阶段冻结任务书.md`

**替代文件：**  
`T2WI-HS-radiomics-analysis 冻结前代码修复任务书.md`

**任务书性质：**  
从“代码修复阶段”切换至“正式技术冻结 → A集结局分析 → 最终模型冻结 → B集单次验证”的执行协议。

**当前起点：**

- 主要技术修复已经完成。
- 主方法M1已经确定。
- A=393宽松主技术队列已经确认。
- A=137严格敏感性队列已经确认。
- 0.1%高信号eligibility已经完成结局盲态技术审计和技术混杂分解。
- 0.1%保持为`minimum imaging-presence criterion`，不再进行阈值搜索。
- A集200次bootstrap preflight已完成并达到`CLEAR PASS`。
- formal 1000次bootstrap尚未执行。
- `freeze_lock.json`尚未生成。
- A集DFS尚未正式解锁。
- B集仍保持不可见。
- 后续所有方法选择均不得利用B集。

---

# 一、总目标

后续分析分为两个完全不同的冻结阶段。

## 第一阶段：技术/生境冻结

完成：

> formal 1000 patient-level bootstrap  
> → 技术门禁  
> → habitat feature正式生成  
> → `freeze_lock.json`

其作用仅为：

> **允许开始读取A集临床变量和结局。**

不得因此读取B集。

---

## 第二阶段：最终预测模型冻结

仅使用A集完成：

> endpoint QC  
> → A-only modeling dataset  
> → nested internal validation  
> → 主模型及敏感性分析  
> → final A refit  
> → `model_freeze_lock.json`

只有第二把锁生成后：

> **B集才允许首次读取并执行一次性验证。**

因此：

```text
技术数据
   ↓
formal bootstrap 1000
   ↓
freeze_lock.json
   ↓
仅解锁 A outcomes
   ↓
A nested validation / model development
   ↓
final model freeze
   ↓
model_freeze_lock.json
   ↓
首次解锁 B
   ↓
一次性外部验证
```

---

# 二、不可再改变的技术决策

除非出现明确的软件错误或数据完整性错误，以下事项从本任务书开始视为冻结，不再比较替代方案。

## 2.1 主分析队列

宽松主分析：

- A=393
- B=107

eligibility：

`high_fraction ≥0.001`

定义：

> minimum imaging-presence criterion

不解释为：

- biological mucin cutoff；
- histopathological mucinous carcinoma threshold；
- prognostic cutoff；
- optimal cutoff；
- minimum habitat volume。

---

## 2.2 严格敏感性队列

A=137，B=23。

固定要求：

- `high_fraction ≥1%`
- 最大26邻域LCC ≥128 mm³
- 距肿瘤边界≥2 mm的内部高信号核心≥32 mm³

不得根据DFS重新修改。

---

## 2.3 M1生境方法

固定：

- muscle-mean normalization；
- `[1,1,2] mm`重采样；
- 4 mm 3D SLIC；
- voxel SuperGridSize=`[4,4,2]`；
- 使用所有有效supervoxels；
- 每病例总聚类权重=1；
- cross-case K-means；
- K=2；
- k-means++；
- `n_init=100`；
- `max_iter=300`；
- `tol=1e-4`；
- seed规则保持当前实现；
- centers低→高固定映射为`H-low`和`H-high`。

不得重新比较：

- M2/M3；
- Z-score主方案；
- 2D SLIC；
- 病例内K-means作为主方法；
- 其他K值；
- 其他SLIC尺度。

---

## 2.4 单生境规则

合法状态：

- `single-H-low`
- `single-H-high`
- `dual-habitat`

单生境：

> 不是technical failure，不排除。

结构性不存在的指标按冻结规则处理。

表型内纹理在对应habitat不存在时：

> 保持NA，不填0。

---

## 2.5 主要低维habitat feature block

固定主要候选：

1. `H_high_fraction`
2. `sv_median_minus_boundary`
3. `sv_IQR`
4. `interface_density`
5. `H_high_largest_component_tumor_fraction`
6. `H_high_radial_burden`

`habitat_entropy`、`H_high_component_density`保留描述/次要分析角色。

`H_low_fraction=1-H_high_fraction`不得与`H_high_fraction`共同进入预测模型。

---

# 三、整个后续阶段的硬性禁止事项

在`model_freeze_lock.json`生成之前：

**禁止读取B集的：**

- DFS；
- OS；
- CSS；
- 临床变量；
- B habitat feature分布；
- B radiomics结果；
- B模型性能；
- B calibration；
- B ICC；
- B缺失率；
- B subgroup结果。

不得利用B：

- 选择阈值；
- 选择feature；
- 选择模型；
- 选择penalty；
- 调整参数；
- 决定缺失值策略；
- 重新定义A137；
- 修改habitat boundary；
- 改变结局定义。

---

# 四、任务执行总顺序

本任务书必须严格按：

```text
T01 formal bootstrap 1000
↓
T02 formal稳定性门禁
↓
T03 技术冻结及freeze_lock
↓
T04 A/B解锁代码隔离
↓
T05 A结局解锁与endpoint QC
↓
T06 A-only raw modeling dataset
↓
T07 A描述性分析与建模前QC
↓
T08 A nested prognostic modeling
↓
T09 A137严格敏感性分析
↓
T10 tumor-volume adjusted sensitivity
↓
T11 最终A模型冻结
↓
T12 model_freeze_lock
↓
T13 B一次性验证
↓
T14 最终结果整理与manuscript输出
```

任何前序硬门禁未通过：

> 后序任务不得运行。

---

# T01 — 执行formal 1000次患者层面bootstrap

## 目标

将目前200次`CLEAR PASS` preflight升级为正式稳定性证据。

## 运行前

只允许进行只读检查：

- 当前Git commit；
- working tree；
- A393 ID hash；
- A137 ID hash；
- SLIC config hash；
- preprocessing config hash；
- bootstrap脚本hash；
- formal目录是否为空；
- preflight结果是否仍然完整。

formal bootstrap应成为本任务书开始后第一项产生新分析结果的操作。

---

## 固定运行参数

```text
bootstrap_mode = formal
requested_bootstraps = 1000
```

继续使用当前已验证实现：

- patient-level resampling；
- patient-balanced fitting；
- 每次重采样患者总权重相等；
- deterministic seed；
- checkpoint；
- resume；
- formal独立输出目录。

不得因为preflight结果改变随机数策略。

---

## 输出

```text
bootstrap_stability_A_post_slic_fix/formal/
```

至少包括：

- replicate-level centers；
- boundary；
- completion checkpoint；
- bootstrap summary；
- case assignment stability；
- structural state stability；
- provenance。

---

## formal硬门禁

必须满足：

```text
requested = 1000
completed = 1000
completion_status = complete
formal_eligible = 1
```

以及当前冻结标准：

- nondegenerate rate ≥0.99；
- reference boundary位于bootstrap 95%范围内；
- boundary CI width / center distance ≤0.25；
- assignment stability median ≥0.95；
-病例级assignment stability P5 ≥0.80。

structural-state stability继续完整报告。

---

## 建议正式收敛表

使用：

- 250
- 500
- 750
- 1000

累计结果。

仅作正式结果描述，不增加新的通过阈值。

---

## 停止条件

如formal不通过：

> STOP。

不得：

- 读取DFS；
- 调整0.1%；
- 调整SLIC；
- 改K；
- 换normalization；
- 利用B寻找解决办法。

必须首先形成：

`formal_bootstrap_failure_diagnostic.md`

并明确区分：

- 软件错误；
- 数值错误；
- 真正的方法不稳定。

任何方法修改均属于新的protocol amendment。

---

# T02 — formal结果审核

## 输出

`formal_bootstrap_final_report.md`

必须至少报告：

- 1000/1000 completion；
- nondegenerate rate；
- reference centers；
- reference boundary；
- bootstrap boundary median；
- 95% interval；
- interval width / center distance；
- assignment median；
- assignment P5；
- structural stability；
- H-high fraction变化；
- 与preflight 200结果的一致性。

---

## 验收

若formal满足预设标准：

> `FORMAL PASS`

才进入T03。

---

# T03 — 完成技术冻结并生成第一阶段freeze lock

## 目标

冻结：

- 技术队列；
- eligibility；
- preprocessing；
- SLIC；
- cross-case clustering；
- global centers；
- habitat feature dictionary；
- structural rules。

---

## 必须完成的正式feature输出

A393中：

- 每例均有合法habitat状态；
- hard technical failure按冻结标准统计；
- voxel conservation通过；
- 6个主低维habitat特征均按定义生成；
- 所有应为finite的主特征必须finite；
- structural-zero/NA规则正确。

A137：

- exact n=137；
- A137必须为A393真子集；
- 使用与主A393一致的冻结技术定义。

---

## freeze lock新增内容

除现有字段外，建议加入：

```text
eligibility_threshold_fraction = 0.001

eligibility_threshold_role =
"minimum_imaging_presence"

threshold_selection_performed = false

threshold_audit_conclusion =
"NEUTRAL_WITH_TECHNICAL_CAUTION"
```

同时保存：

- threshold audit provenance hash；
- technical confounding provenance hash；
- `cohort_definition.md` hash；
- A393 ID hash；
- A137 ID hash；
- preprocessing config hash；
- SLIC config hash；
- formal bootstrap summary hash；
- feature dictionary hash。

---

## 第一阶段锁的语义

`freeze_lock.json`只能表示：

```text
habitat_technical_freeze = true
A_outcome_unlock = true
B_unlock = false
```

绝对不能解释为：

> B已经可以读取。

---

## 原子性要求

正式maps、features、feature dictionary、freeze QC和lock应使用：

> staging → validation → atomic promotion

避免出现：

> 正式目录已经覆盖，但lock写入失败

导致半冻结状态。

---

# T04 — 修正A outcome unlock与B validation unlock的代码边界

这是正式读取结局前最后一个代码门禁。

## 当前风险

后续建模程序不得在第一阶段`freeze_lock.json`出现后直接：

- 构建B raw dataset；
- 读取B outcome；
- 写出`dataset_*_B.csv`。

---

## 必须形成两阶段访问逻辑

### A-only模式

例如：

```text
--split A
```

要求：

- 必须存在有效`freeze_lock.json`；
- 只加载A患者；
- 临床/outcome表merge前即限制A ID；
- 不允许B row进入内存建模表；
- 不生成任何B输出。

### B validation模式

例如：

```text
--split B
```

要求：

- `freeze_lock.json`存在；
- `model_freeze_lock.json`存在；
- 最终A模型hash一致；
- final preprocessing parameters已冻结；
- final habitat centers已冻结；
- B unlock flag=true。

否则：

> hard fail。

---

## 回归测试

至少新增：

1. technical freeze后A构建成功；
2. technical freeze后B构建失败；
3. technical freeze后不存在任何`dataset_*_B*`；
4. 无`model_freeze_lock.json`时B hard fail；
5. 有有效model lock后B才允许一次执行；
6. A-only builder在B临床数据不存在时仍能正常工作。

---

# T05 — 正式解锁A结局并进行endpoint QC

只有T03、T04全部完成后执行。

---

## 只允许读取

A393以及A137对应病例的：

- DFS；
- 预设临床变量；
- 描述性变量；
- 已预设次要结局。

B仍然不得读取。

---

## 主终点

```text
DFS
```

主要评价时点：

- 3年；
- 5年。

OS/CSS保持次要或补充分析角色，不得用于修改DFS主模型。

---

## endpoint QC

必须报告：

- A393总人数；
- DFS event数；
- censor数；
- follow-up分布；
- median follow-up；
- 3年可评价人数；
- 5年可评价人数；
- DFS_time≤0异常；
- event/time逻辑冲突；
- duplicated patient ID；
- impossible dates；
- missing outcome。

建议median follow-up采用reverse Kaplan–Meier。

---

## 硬规则

如果发现outcome数据错误：

只能修正：

> 可以追溯到原始数据录入或定义错误的问题。

不得根据影像结果调整：

- event definition；
- censor date；
- follow-up cutoff。

---

# T06 — 构建A-only原始建模数据集

## 原则

建模数据保持raw尺度。

禁止在full A上预先：

- scaling；
- imputation；
- correlation filtering；
- feature selection；
- outcome-guided filtering。

---

## 主临床变量固定9项

1. 年龄
2. CEA_log
3. mrT_4级
4. mrN_3级
5. MRF
6. mrEMVI
7. thickness
8. EID
9. 活检病理非腺癌

以下变量不进入任何主模型：

- 性别
- length
- distance

只能作描述或预设敏感性用途。

---

## 输出

主队列：

```text
dataset_primary_raw_A.csv
```

严格队列：

```text
dataset_primary_raw_A_strict.csv
```

同时生成：

`analysis_schema_A.json`

记录：

- cohort hash；
- outcome definition；
- clinical variables；
- habitat feature block；
- radiomics candidate block；
- missing-data policy；
- CV policy；
- split=A only。

---

# T07 — A集建模前描述与QC

这一阶段可以查看A outcome，但：

> 不能根据描述结果重新定义feature或阈值。

---

## 必须输出

### Cohort flow

从：

A筛选母队列530  
→ A393  
→ technical success  
→ outcome-available  
→ final modeling population。

---

### 描述性统计

- age；
- CEA；
- mrT；
- mrN；
- MRF；
- mrEMVI；
- tumor thickness；
- EID；
- pathology category；
- tumor volume；
- six habitat features。

---

### 结局信息

- DFS event count；
- median follow-up；
- Kaplan–Meier overall A curve。

---

### missingness

逐变量报告：

- missing n；
- missing %。

不使用DFS决定：

> 哪个变量“缺太多所以删除”。

---

### feature dependency

仅作为解释性QC：

- habitat feature–tumor volume correlation；
- habitat feature间correlation；
- feature distribution；
- extreme values。

不得在full A根据这些结果进行预测性feature筛选。

---

# T08 — A集正式nested prognostic modeling

这是后续统计分析的核心。

## 8.1 核心原则

任何会从数据估计参数的步骤都必须在outer training fold内部完成。

尤其包括：

- habitat K-means centers；
- habitat boundary；
- fold-specific habitat assignment；
- imputation；
- scaling；
- near-zero variance filtering；
- radiomics correlation reduction；
- radiomics feature selection；
- penalty tuning；
- hyperparameter tuning。

---

## 8.2 禁止的做法

禁止：

> 使用full-A冻结的K-means centers先计算所有A患者habitat feature，再用这些feature报告cross-validation性能。

因为validation fold已经参与了unsupervised center估计。

这属于：

> unsupervised information leakage。

---

## 8.3 正确outer-fold流程

每个outer split：

```text
Outer training patients
        ↓
只用training patients拟合global K=2
        ↓
得到training centers/boundary
        ↓
重新生成training habitat features
        ↓
把training-fitted centers应用于validation patients
        ↓
生成validation habitat features
        ↓
training-fold内插补/标准化/筛选
        ↓
inner CV调参
        ↓
fit outer-training model
        ↓
predict outer-validation
```

validation outcome只能用于：

> 最终计算outer-fold performance。

---

## 8.4 CV policy

在首次正式建模前锁定：

- outer folds；
- repeats；
- seeds；
- inner folds；
- stratification规则；
- primary metric。

建议至少采用：

> repeated outer 5-fold nested validation

并保证每fold具有合理DFS event分布。

具体repeat数写入：

`modeling_protocol.json`

后不得依据结果修改。

---

# T09 — 预设模型比较

建议把比较设计成“科学问题比较”，而不是寻找性能最高的任意模型。

## Clinical baseline

固定9个临床影像变量。

---

## Habitat model

使用冻结的低维habitat feature block。

不进行基于univariable P值的全A筛选。

---

## Clinical + Habitat

评价：

> habitat是否在预设临床信息基础上提供增量价值。

这是主要模型比较之一。

---

## Whole-tumor radiomics comparator

使用stage6 outcome-blind ICC候选特征。

后续：

- scaling；
- redundancy reduction；
- prediction-driven selection；
- tuning

均必须位于nested training folds内。

---

## Combined model

如项目预设包含：

> clinical + radiomics + habitat

则必须在首次查看正式模型性能前写入`modeling_protocol.json`。

不得看到A结果以后临时新增组合模型。

---

# T10 — 主要性能指标

所有模型使用完全相同的outer validation splits。

至少输出：

## Discrimination

- Harrell C-index；
- 建议补充Uno C-index；
- 3-year time-dependent AUC；
- 5-year time-dependent AUC。

## Overall prediction error

- Brier score；
- integrated Brier score，如实现稳定。

## Calibration

- 3-year calibration；
- 5-year calibration；
- calibration slope；
- calibration-in-the-large。

## Incremental value

重点比较：

```text
Clinical
vs
Clinical + Habitat
```

以及预设radiomics比较。

报告：

- ΔC-index；
- Δtime-dependent AUC；
- calibration变化。

不要只报告P值。

---

# T11 — A137严格敏感性分析

## 原则

A137不是新的方法开发集。

所有：

- eligibility；
- SLIC；
- feature定义；
-模型家族；
- preprocessing规则；
-评价指标

沿用主分析。

---

## 不允许

因为A137样本较少而：

- 换feature；
- 改threshold；
- 改模型；
- 重新挑参数体系；
- 改primary metric。

---

## 重点报告

相对于A393：

- effect direction；
- effect magnitude；
- performance；
- uncertainty。

敏感性的一致性不能只按：

> P<0.05 / P≥0.05

判断。

---

# T12 — tumor-volume adjusted sensitivity analysis

由于阈值技术审计已经发现：

> high_fraction与tumor volume存在明显关系，

因此在首次DFS分析前固定这一敏感性分析。

---

## 目的

回答：

> habitat的预后信息是否主要只是tumor burden的替代指标？

---

## 设计

主模型保持不变。

另外增加：

```text
MRI tumor volume
```

形成volume-adjusted sensitivity model。

---

## 比较

主要habitat效应：

- direction；
- HR/effect magnitude；
- confidence interval；
- prediction performance；

加入tumor volume前后变化。

---

## 禁止

不得：

> 因为volume-adjusted结果不好而删除某个habitat特征或修改0.1%阈值。

---

# T13 — A集最终模型确定与全A refit

nested CV完成后，必须先完成A-only结果审核。

B仍然完全不可见。

---

## 最终模型不是“挑最好看的一个”

最终模型应依据：

1. 预设科学问题；
2. 预设模型家族；
3. nested validation；
4. parsimony；
5. calibration；
6. 稳定性。

而不是：

> 哪个模型在A中偶然C-index最高。

---

## Final A refit

确定最终模型结构后：

使用全部A393重新拟合：

- final habitat centers；
- final preprocessing；
- imputation parameters；
- scaling parameters；
- radiomics selector；
- final coefficients；
- baseline survival function；
- 所有3/5-year prediction parameters。

这是：

> deployment model

不能拿来作为A内部无偏性能估计。

A性能仍引用nested validation结果。

---

# T14 — 生成第二阶段 model freeze lock

建立：

```text
model_freeze_lock.json
```

必须保存：

## Cohort

- A393 hash；
- A137 hash。

## Technical

- `freeze_lock.json` hash；
- final habitat centers；
- boundary；
- SLIC config hash。

## Feature processing

- feature list；
- imputation parameters；
- scaler parameters；
- correlation/filter parameters；
- radiomics selected features。

## Model

- model family；
- hyperparameters；
- coefficients；
- baseline survival；
- 3/5-year prediction specification。

## Validation protocol

- CV split seed；
- outer/inner folds；
- metric definitions。

## Final model artifact hashes

全部记录。

---

## model lock必须声明

```text
A_model_frozen = true
B_data_read = false
B_validation_unlocked = true
```

这一步之后：

> 才允许首次接触B。

---

# T15 — B集一次性验证

B的作用只有：

> evaluation

没有：

> development。

---

## 必须完全冻结后应用

B不得重新：

- fit centers；
- fit scaler；
- fit imputation；
- select features；
- tune lambda；
- change threshold；
- recalibrate primary model；
- change clinical variables。

---

## Habitat

使用：

> final A-fitted centers/boundary

直接映射B。

---

## Radiomics

使用：

> final A-fitted preprocessing和feature selector。

---

## Prediction

使用：

> final A coefficients/model。

---

## B报告

主B=107。

严格B=23为敏感性验证。

至少报告：

- technical coverage；
- valid prediction n；
- C-index；
- 3-year AUC；
- 5-year AUC；
- calibration；
- Brier；
- calibration slope；
- distribution shift。

---

## 重要原则

如果B结果下降：

只能报告：

> transportability/generalization下降。

不得回到A重新：

- 改阈值；
- 改SLIC；
- 改features；
- 调参；
- 改模型。

否则B不再是独立验证。

---

# T16 — OS/CSS及其他次要分析

主DFS模型和主要结果冻结之后才能进行。

OS/CSS：

> 不得反向影响DFS主模型。

其他探索性分析：

- subgroup；
- postoperative pathology；
- mucin；
- pTRG；
- neoadjuvant；

必须明确标记：

> secondary / exploratory。

不得混入主模型开发逻辑。

---

# T17 — manuscript methodology defense同步更新

完成technical freeze后更新：

```text
manuscript/methodology_defense/
```

至少形成：

1. `01_high_signal_eligibility_threshold_defense.md`
2. `02_cohort_definition_and_data_blinding_defense.md`
3. `03_peritumoral_reference_and_muscle_normalization_defense.md`
4. `04_slic_physical_scale_and_supervoxel_design_defense.md`
5. `05_patient_balanced_cross_case_clustering_defense.md`
6. `06_structural_single_habitat_handling_defense.md`
7. `07_bootstrap_stability_and_formal_freeze_defense.md`
8. `08_strict_A137_sensitivity_cohort_defense.md`
9. `09_habitat_feature_dictionary_and_volume_confounding_defense.md`
10. `10_reader_reproducibility_and_primary_reader_defense.md`
11. `11_nested_validation_and_information_leakage_defense.md`
12. `12_device_split_and_external_validation_defense.md`
13. `13_reproducibility_provenance_and_freeze_lock_defense.md`
14. `14_raw_high_signal_vs_habitat_construct_defense.md`

这些文件是：

> methodology evidence archive

而不是新的方法选择入口。

---

# 五、两个freeze lock必须严格区分

## Lock 1 — habitat technical freeze

文件：

```text
habitat_analysis/freeze_lock.json
```

允许：

- A clinical/outcome读取；
- A prognostic modeling。

禁止：

- B访问。

---

## Lock 2 — final predictive model freeze

文件：

```text
prognosis_analysis/model_freeze_lock.json
```

允许：

- B一次性验证。

---

# 六、建议新增的自动化门禁

## test_A_outcome_unlock

验证：

- 无技术lock → A outcome builder失败；
- 有技术lock → A成功。

## test_B_stays_locked_after_habitat_freeze

验证：

> 只有第一把锁时B一定失败。

## test_B_unlock_requires_model_freeze

只有完整`model_freeze_lock.json`才允许B。

## test_nested_habitat_refit

验证：

outer validation patient不得进入training KMeans fit。

## test_fold_scaling

validation scaler只能来自training。

## test_fold_imputation

validation imputation只能来自training。

## test_final_model_hash

B运行前检查最终模型artifact hash。

---

# 七、结果文件分层建议

避免后续输出混杂。

```text
habitat_analysis/output/
    bootstrap_stability_A_post_slic_fix/
        formal/
    frozen_maps_A/
    frozen_features_A/

prognosis_analysis/output/
    A_endpoint_qc/
    A_modeling_raw/
    A_nested_validation/
    A_strict_sensitivity/
    A_volume_sensitivity/
    final_model/
    B_external_validation/
```

B目录：

> 在`model_freeze_lock.json`存在前不得创建患者级结果。

---

# 八、停止规则

出现以下任一情况立即停止后续推进：

### Technical freeze前

- formal 1000不完整；
- formal_eligible≠1；
- A393身份变化；
- A137不是A393子集；
- config hash变化；
- technical failure超过冻结标准。

### A outcome阶段

- freeze lock校验失败；
- B被意外读取；
- endpoint定义存在无法追溯的问题；
- patient ID merge异常。

### Nested modeling

- validation patient参与feature fitting；
- full-A scaler被用于CV；
- full-A KMeans centers被用于CV performance；
- outcome-driven feature filtering发生在outer CV外。

### B验证前

- model lock缺失；
- final model hash变化；
- preprocessing参数未冻结。

任一发生：

> 不得继续并“看看结果再说”。

---

# 九、旧任务书的处理

原：

`T2WI-HS-radiomics-analysis 冻结前代码修复任务书.md`

不建议删除。

改为：

```text
status: COMPLETED / SUPERSEDED
superseded_by:
T2WI-HS-radiomics-analysis 后续分析与双阶段冻结任务书.md
```

其作用转为：

> 保存pre-freeze修复历史和决策轨迹。

不再作为当前执行清单。

---

# 十、近期执行优先级

从当前状态开始只做以下四件事：

## Priority 1

**formal patient-level bootstrap = 1000**

这是下一项正式分析任务。

## Priority 2

**formal gate + technical freeze + `freeze_lock.json`**

并加入0.1%审计/技术混杂provenance。

## Priority 3

**把A outcome unlock与B validation unlock彻底拆开**

特别修正当前建模dataset builder的A/B联合生成行为。

## Priority 4

**在B完全锁定的前提下开始A-only DFS analysis**

进入nested modeling。

---

# 十一、整个项目后续最重要的三条原则

## 原则1：现在停止技术方法选择

0.1%、4 mm SLIC、K=2、患者等权和主habitat features已经经过充分的结局盲态技术论证。

下一阶段任务是：

> 验证预后价值，

不是继续寻找更漂亮的方法。

---

## 原则2：A内部性能必须来自真正的nested procedure

最终full-A模型是：

> deployment fit。

不能把其训练性能当作内部验证性能。

---

## 原则3：B只能使用一次

B一旦解锁：

> 所有可以影响prediction的参数都必须已经冻结。

如果B表现不理想：

> 这是研究结果，而不是再次调参的理由。

---

# 十二、最终里程碑

## Milestone A — Technical Freeze

完成：

- formal 1000；
- formal PASS；
- A393 frozen；
- A137 frozen；
- habitat features frozen；
- `freeze_lock.json`生成。

状态：

> A outcome unlocked / B locked

---

## Milestone B — A Internal Validation Complete

完成：

- DFS QC；
- A raw modeling data；
- nested validation；
- strict sensitivity；
- volume-adjusted sensitivity。

状态：

> A evidence complete / B locked

---

## Milestone C — Final Model Freeze

完成：

- final feature processing；
- final A centers；
- final A model；
- all hashes；
- `model_freeze_lock.json`。

状态：

> B validation unlocked

---

## Milestone D — External Validation Complete

完成：

- B107一次性验证；
- B23严格敏感性验证；
- 不返回A调参。

状态：

> analysis complete

---

# 十三、最终验收标准

整个任务书完成时必须能够回答“是”：

- formal 1000是否完整完成？
- technical freeze是否发生在首次读取DFS之前？
- 0.1%是否始终没有通过outcome重新优化？
- A137是否保持预设定义？
- B是否在最终模型冻结前始终不可见？
- A内部模型性能是否来自nested validation？
- 每个outer fold的habitat centers是否只使用training patients拟合？
- scaling/imputation/feature selection是否均在training folds内完成？
- tumor-volume sensitivity是否在看结果前预设？
- final full-A model是否与internal validation performance严格区分？
- B是否只验证一次？
- B结果是否没有用于回调A模型？
- 所有关键配置、队列、模型和结果是否存在hash/provenance？

全部满足后：

> **T2WI-HS-radiomics-analysis正式完成方法开发、内部验证及设备域外部验证流程。**