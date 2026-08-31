# 三十二、具体执行工作流：从formal PASS至A-only model freeze

本节替代此前仅列出步骤名称的“近期执行顺序”。

整个流程分为三个阶段：

```text
阶段 I：技术冻结前最后准备
    ↓
阶段 II：A-only outcome analysis + nested internal validation
    ↓
阶段 III：A-only final refit + model freeze
```

在第三阶段完成并生成`model_freeze_lock.json`之前：

> **B集始终不可读取。**

---

# Workflow总览

```text
W00  formal结果归档与仓库状态同步
 ↓
W01  technical freeze / freeze_lock.json
 ↓
W02  H-low/H-high Original radiomics结局盲态提取框架
 ↓
W03  habitat radiomics ICC与技术候选池冻结
 ↓
W04  建模协议 modeling_protocol 冻结
 ↓
W05  A-only数据访问改造
 ↓
W06  首次读取A结局 + endpoint QC
 ↓
W07  冻结A建模人口及CV splits
 ↓
W08  repeated nested CV：
      fold-specific habitat → G → R_low/R_high → models
 ↓
W09  A集模型比较与稳定性评价
 ↓
W10  A137及tumor-volume等预设敏感性分析
 ↓
W11  根据预设层级确定final A model architecture
 ↓
W12  full-A refit
 ↓
W13  A-only model freeze / model_freeze_lock.json
```

只有W13完成之后：

> 才进入后续B集一次性验证阶段。

---

# W00 — formal结果归档与仓库状态同步

## 目标

正式关闭technical bootstrap阶段。

## 已确认formal结果

- requested=1000；
- completed=1000；
- success=1000；
- nondegenerate rate=1.000；
- reference H-low center=2.101717；
- reference H-high center=3.519630；
- reference boundary=2.810674；
- bootstrap boundary median=2.811491；
- boundary 95% interval=[2.708194, 2.924580]；
- width/center distance=0.152609；
- assignment stability median=0.986711；
- assignment stability P5=0.960980；
- structural-state stability median=1.000；
- structural-state stability P5=0.997；
- formal_eligible=1。

最终判定：

> **FORMAL PASS**

---

## 必须更新

### `PROJECT_STATUS.md`

标记：

> formal完成，进入technical freeze。

### `habitat_analysis/analysis_freeze.md`

将可能存在的旧状态：

> formal未运行

修改为：

> formal=1000 complete / FORMAL PASS。

---

## 禁止

此阶段不得：

- 再运行额外bootstrap寻找更漂亮结果；
- 调整0.1%；
- 调整SLIC；
- 调整K；
- 调整normalization；
- 重新比较M1/M2/M3。

---

# W01 — 执行正式technical freeze

## 输入

必须核验：

- A393 technical cohort；
- A137 strict cohort；
- manifest；
- scanner map；
- preprocessing config；
- SLIC config；
- formal bootstrap summary；
- baseline integrity；
- center reproducibility；
- technical robustness；
- threshold audit；
- threshold confounding audit。

---

## 运行

执行：

> `stage7_freeze`

生成正式：

- habitat maps；
- global descriptors；
- feature QC；
- feature dictionary；
- freeze lock。

---

## 主低维global habitat block G

固定为：

1. `H_high_fraction`
2. `sv_median_minus_boundary`
3. `sv_IQR`
4. `interface_density`
5. `H_high_largest_component_tumor_fraction`
6. `H_high_radial_burden`

---

## technical freeze必须核验

A393：

- exact n=393；
- unique ID=393；
- hard technical failures=0；
- 六个G特征全部finite；
- H-low + H-high voxel conservation成立。

A137：

- exact n=137；
- strict⊂lenient。

---

## `freeze_lock.json`

至少记录：

```text
habitat_technical_freeze = true

A_outcome_unlock = true

B_unlock = false

eligibility_threshold_fraction = 0.001

eligibility_threshold_role =
minimum_imaging_presence

threshold_selection_performed = false

threshold_audit_conclusion =
NEUTRAL_WITH_TECHNICAL_CAUTION
```

以及所有关键：

- patient ID hashes；
- config hashes；
- formal bootstrap hash；
- feature dictionary hash；
- audit provenance hashes；
- centers；
- boundary。

---

## 原子性要求

正式目录必须采用：

```text
staging
↓
全部QC
↓
lock材料全部准备
↓
atomic promotion
```

避免形成：

> maps/features已经晋升，但freeze lock写入失败

的半冻结状态。

---

# W02 — 建立H-low/H-high Original radiomics提取工作流

该步骤仍然：

> **outcome blind。**

目的是在首次读取DFS之前，把habitat-specific radiomics的方法定义冻结。

---

# W02.1 输入影像

使用与主habitat完全一致的：

- muscle-normalized T2WI；
- `[1,1,2] mm`；
- 无N4；
- tumor ROI；
- SLIC supervoxel labels。

不重新：

- normalize；
- resample；
- 计算新的binWidth。

---

# W02.2 habitat Original参数

固定：

```text
imageType = Original
binWidth = 0.248808 approximately
PyRadiomics normalize = false
PyRadiomics resample = false
```

不得为：

- H-low；
- H-high

分别计算不同binWidth。

两种habitat必须使用同一灰度标尺。

---

# W02.3 提取完整Original特征

每种habitat提取：

- firstorder；
- shape；
- GLCM；
- GLRLM；
- GLSZM；
- GLDM；
- NGTDM。

保存完整特征用于：

- QC；
-重复性；
-探索性分析。

---

# W02.4 主habitat-radiomics候选范围

正式预测候选优先限定为：

> **Original texture features**

即：

- GLCM；
- GLRLM；
- GLSZM；
- GLDM；
- NGTDM。

原因：

H-low/H-high本身通过信号强度聚类定义。

因此：

- Mean；
- Median；
- Percentile等first-order指标

与habitat定义具有部分数学耦合。

Shape又与：

- H-high fraction；
- largest component；
- interface；
- radial burden

存在明显概念重叠。

因此：

### Main habitat-radiomics pool

> texture。

### Secondary

> first-order。

### Exploratory

> shape。

---

# W02.5 生成两个完全对称的特征块

```text
R_low =
H-low Original texture radiomics

R_high =
H-high Original texture radiomics
```

H-low和H-high：

> 方法地位完全相同。

不得预先认定：

> 哪个更重要。

---

# W02.6 结构性不存在

如果患者为：

### single-H-low

则：

> R_high = structurally undefined。

### single-H-high

则：

> R_low = structurally undefined。

不能填：

> 0。

---

# W02.7 habitat-radiomics分析人口定义

由于habitat-internal radiomics只有habitat真实存在时才有物理含义，因此不把结构性不存在通过人工插补强行变成“纹理正常值”。

分别定义：

## Low-radiomics eligible cohort

存在H-low并满足PyRadiomics最低ROI要求。

## High-radiomics eligible cohort

存在H-high并满足最低ROI要求。

## Dual-radiomics eligible cohort

同时满足：

- H-low radiomics available；
- H-high radiomics available。

---

# W02.8 保存技术availability状态

每例至少记录：

```text
H_low_present
H_high_present

R_low_extractable
R_high_extractable

R_low_failure_reason
R_high_failure_reason
```

明确区分：

### Structural absence

habitat不存在。

### Technical failure

habitat存在，但特征提取失败。

两者不得混合。

---

# W03 — habitat-specific radiomics结局盲态QC

该步骤必须在读取DFS前完成。

---

# W03.1 R1/R2重复性

使用已有A集双读者病例。

对R1和R2：

分别使用相同：

- preprocessing；
- SLIC规则；
- frozen technical boundary；
- Original radiomics parameters。

然后分别生成：

- H-low；
- H-high；

并提取radiomics。

---

# W03.2 ICC

分别计算：

```text
R_low ICC(2,1)
R_high ICC(2,1)
```

候选要求：

```text
ICC > 0.75
```

另外要求：

> 有效成对病例数必须达到预设最低样本要求。

建议：

```text
n_valid_pairs >= 10
```

否则标记：

> insufficient reproducibility sample

而不是判定为稳定。

---

# W03.3 availability

在A/R1中对habitat存在病例计算：

```text
finite feature rate
```

建议结局盲态技术候选要求：

```text
finite rate >= 95%
```

低于该值的特征：

> 不进入正式R_low/R_high预测池。

---

# W03.4 不能在这里进行

- near-zero variance prediction filtering；
- outcome correlation；
- univariate Cox；
- LASSO；
- DFS association；
- feature importance。

这些全部属于后续nested training fold。

---

# W03.5 输出

建议：

```text
prognosis_analysis/output/qc/habitat_radiomics/
    H_low_original_icc.csv
    H_high_original_icc.csv

    H_low_candidate_features.csv
    H_high_candidate_features.csv

    availability_summary.csv
    extraction_failures.csv
    report.md
    provenance.json
```

---

# W03.6 候选池冻结

最终保存：

```text
R_low_candidate_hash
R_high_candidate_hash
```

从此以后：

> 不根据DFS重新修改ICC阈值或候选池定义。

---

# W04 — 冻结正式modeling protocol

在首次读取A DFS之前生成：

```text
prognosis_analysis/modeling_protocol.json
```

以及可读版：

```text
prognosis_analysis/modeling_protocol.md
```

---

# W04.1 固定科学问题

明确记录：

> 不预设H-low或H-high哪个更重要。

核心问题：

> whole-tumor averaging是否掩盖了habitat-specific prognostic information？

---

# W04.2 固定模型

## M0

```text
Clinical
C
```

---

## M1

```text
Clinical + H_high_fraction
C + F
```

其中：

```text
F = H_high_fraction
```

---

## M2

```text
Clinical + Global Habitat
C + G
```

---

## M3L

```text
Clinical + Global Habitat + H-low Radiomics
C + G + R_low
```

---

## M3H

```text
Clinical + Global Habitat + H-high Radiomics
C + G + R_high
```

---

## M4

```text
Clinical + Global Habitat
+ H-low Radiomics
+ H-high Radiomics

C + G + R_low + R_high
```

仅在dual-radiomics eligible cohort中评价。

---

## M5

```text
Clinical + Whole-tumor Radiomics
C + W
```

定位：

> reference comparator。

不作为主要方法开发目标。

---

# W04.3 模型比较层级

正式固定：

```text
M0 → M1
```

回答：

> high-signal burden。

---

```text
M1 → M2
```

回答：

> macro-habitat spatial organization。

---

```text
M2 → M3L
```

回答：

> H-low texture。

---

```text
M2 → M3H
```

回答：

> H-high texture。

---

```text
M3L vs M3H
```

回答：

> 哪个habitat表现出更稳定的prognostic information。

---

```text
M2 → M4
```

回答：

> 双habitat纹理联合。

---

```text
M0 → M5
```

回答：

> whole-tumor radiomics在当前A393中的增量价值。

---

# W04.4 不允许增加大量排列组合

在DFS解锁后不得临时新增：

```text
C + W + R_low
C + W + R_high
C + W + G + R_low
C + W + G + R_high
C + W + G + R_low + R_high
```

除非明确作为：

> post-hoc exploratory analysis。

它们不能用于final model选择。

---

# W04.5 主结局

固定：

> DFS。

主要时间点：

- 3年；
- 5年。

---

# W04.6 内部验证结构

建议固定为：

```text
Outer CV:
5-fold × 10 repeats

Inner CV:
5-fold
```

即：

> 50个outer validation folds。

seed规则：

```text
outer_repeat_seed =
12345 + repeat_index
```

---

# W04.7 fold stratification

根据：

> DFS event status

分层。

要求：

- 每个outer validation fold必须有event；
- 每个outer training fold必须有event。

如果固定seed产生无event fold：

> 使用预设seed序列继续生成下一个合法split。

不得改变：

> 5-fold本身。

---

# W04.8 inner tuning

Radiomics模型采用：

> penalized Cox。

优先：

> Elastic Net Cox。

预设alpha候选：

```text
0.1
0.5
0.9
1.0
```

lambda：

> 由训练折inner CV确定。

inner selection metric：

> partial-likelihood deviance。

不得用outer validation performance调参。

---

# W05 — 修改为真正A-only数据访问

在读取临床表前必须先修改：

```text
build_model_dataset.py
```

---

# W05.1 A模式

要求：

```text
--split A
```

只允许：

- A393；
- A137；
- A临床变量；
- A结局。

merge clinical表之前：

> 先根据technical cohort限制patient IDs。

---

# W05.2 A-mode不得产生

```text
dataset_*_B.csv
```

也不得：

- 统计B数量；
- 输出B missingness；
- 读取B outcome；
- 加载B habitat；
- 查看B radiomics。

---

# W05.3 A raw dataset

输出：

```text
dataset_primary_raw_A.csv
```

包括：

- patient ID；
- DFS；
- C；
- full-A descriptive G；
- whole-tumor W candidate fields；
- descriptive variables。

注意：

> full-A G只用于描述和final refit。

nested CV性能必须重新计算：

> fold-specific G。

---

# W05.4 habitat-radiomics不要直接并入静态wide table用于CV

原因：

R_low/R_high依赖：

> fold-specific clustering boundary。

因此nested modeling必须通过：

> fold-specific feature cache

读取。

不能把full-A frozen masks提取出的R_low/R_high直接用于内部CV性能估计。

---

# W06 — 正式首次读取A DFS

只有：

- W01 technical freeze；
- W03 habitat-radiomics candidate freeze；
- W04 modeling protocol freeze；
- W05 A/B访问隔离

全部通过后执行。

---

# W06.1 endpoint QC

报告：

- A393总人数；
- DFS event count；
- censor count；
- follow-up；
- median follow-up；
- reverse-KM follow-up；
- 3-year evaluable；
- 5-year evaluable；
- DFS_time≤0；
- duplicated ID；
- event/time conflict；
- missing outcome。

---

# W06.2 此阶段允许修改什么

只允许修正：

> 可追溯的原始数据错误。

不得根据影像结果改变：

- DFS definition；
- censor date；
- follow-up cutoff；
- eligibility。

---

# W06.3 冻结最终A modeling population

生成：

```text
A_modeling_population.csv
```

患者排除原因只能是：

- 已冻结technical exclusion；
- outcome不可用；
- 明确数据错误且无法修复。

不得：

> 因模型表现不好排除病例。

---

# W07 — 建立并冻结CV split plan

正式建模前生成：

```text
outer_splits_A.csv
```

字段至少：

```text
影像号
repeat
fold
role
seed
```

---

# W07.1 Main A split plan

用于：

- M0；
- M1；
- M2；
- M5。

目标人群：

> A393中具有有效DFS的人群。

---

# W07.2 R_low split plan

对：

> R_low-eligible cohort

建立固定splits。

在这些完全相同splits中比较：

```text
M2
vs
M3L
```

因此增量比较是paired。

---

# W07.3 R_high split plan

对：

> R_high-eligible cohort

建立固定splits。

比较：

```text
M2
vs
M3H
```

---

# W07.4 dual split plan

对：

> dual-radiomics eligible cohort

建立固定splits。

用于：

```text
M2
M3L
M3H
M4
```

进行真正的：

> H-low vs H-high head-to-head comparison。

---

# W08 — 正式repeated nested CV

这是整个A-only分析的核心。

每一个：

```text
repeat × outer fold
```

都完整执行以下流程。

---

# W08.1 划分outer training / validation

取得：

```text
Train_outer
Validation_outer
```

从这一刻开始：

> Validation_outer不得参与任何参数估计。

---

# W08.2 只用Train_outer重新拟合global habitat centers

读取预缓存：

- SLIC labels；
- supervoxel Means。

只使用：

> Train_outer patients。

患者等权：

```text
sum of supervoxel weights per patient = 1
```

重新拟合：

```text
K=2
```

得到：

```text
C_low_train
C_high_train
b_train
```

---

# W08.3 应用train boundary

分别应用于：

### Train_outer

生成training habitat masks。

### Validation_outer

使用完全相同的：

```text
b_train
```

生成validation masks。

Validation_outer：

> 不参与boundary估计。

---

# W08.4 生成fold-specific G

根据：

> fold-specific habitat masks

重新计算六个G变量。

因此：

> CV中的G不能直接使用full-A frozen G。

---

# W08.5 提取fold-specific R_low/R_high

对training和validation分别：

- H-low mask；
- H-high mask；

提取：

> Original radiomics。

只保留W03预先冻结的：

- R_low candidate pool；
- R_high candidate pool。

---

# W08.6 缓存fold-specific特征

建议：

```text
prognosis_analysis/output/nested_cv/fold_assets/
    repeat_00/
        fold_0/
            centers.json
            train_global_habitat.csv
            validation_global_habitat.csv
            train_R_low.csv
            validation_R_low.csv
            train_R_high.csv
            validation_R_high.csv
            provenance.json
```

每个fold必须记录：

- training IDs hash；
- validation IDs hash；
- centers；
- boundary；
- feature candidate hashes。

---

# W08.7 Clinical preprocessing

所有缺失处理只在：

> Train_outer

拟合。

例如：

### Continuous

training median imputation。

### Categorical

training mode或预设category imputation。

然后应用：

> Validation_outer。

---

# W08.8 G preprocessing

G原则上应完整finite。

标准化参数：

> 只用Train_outer。

---

# W08.9 Whole-tumor W preprocessing

W已经通过outcome-blind ICC候选筛选。

在Train_outer内部继续：

### Step 1

near-zero variance filtering。

### Step 2

高相关去重。

建议：

```text
|rho| > 0.90
```

相关组代表变量选择不得看validation outcome。

可根据：

- training ICC；
- feature ordering

预设选择。

### Step 3

training-only standardization。

### Step 4

Elastic Net feature selection/tuning。

---

# W08.10 R_low/R_high preprocessing

采用与W一致的规则：

- near-zero variance；
- correlation filtering；
- scaling；
- Elastic Net。

全部：

> Train_outer only。

---

# W08.11 M0

```text
C
```

9个clinical/MRI变量全部固定。

不进行univariate P screening。

---

# W08.12 M1

```text
C + H_high_fraction
```

全部固定进入。

---

# W08.13 M2

```text
C + six G features
```

不根据univariable P筛选G。

---

# W08.14 M3L

```text
C + G
```

强制保留。

```text
R_low
```

进入penalized selection。

---

# W08.15 M3H

```text
C + G
```

强制保留。

```text
R_high
```

进入penalized selection。

---

# W08.16 M4

```text
C + G
```

固定。

```text
R_low + R_high
```

联合进入penalized selection。

只在：

> dual-radiomics eligible cohort

运行。

---

# W08.17 M5

```text
C
```

固定。

```text
W
```

进入penalized selection。

M5用于：

> whole-tumor comparator。

---

# W08.18 outer validation prediction

inner CV完成后：

使用最佳训练参数：

> refit完整Train_outer。

然后对：

> Validation_outer

仅执行transform和prediction。

不得重新：

- scaling；
- feature selection；
- lambda tuning；
- boundary fitting。

---

# W09 — A集内部验证结果汇总

所有结果均来自：

> held-out outer validation predictions。

---

# W09.1 Primary discrimination

报告：

- Harrell C-index；
- Uno C-index。

其中预先指定一个作为：

> primary discrimination metric。

建议：

> Harrell C-index作为主报告；

Uno作为censoring-robust补充。

---

# W09.2 Time-dependent discrimination

报告：

- 3-year AUC；
- 5-year AUC。

---

# W09.3 Calibration

报告：

- 3-year calibration；
- 5-year calibration；
- calibration slope；
- calibration-in-the-large。

---

# W09.4 Prediction error

报告：

- 3-year Brier；
- 5-year Brier；
- integrated Brier score，如实现稳定。

---

# W09.5 模型比较必须paired

例如：

```text
M2 vs M3L
```

必须：

> 来自同一R_low eligible patients + 同一outer splits。

---

```text
M2 vs M3H
```

同理。

---

# W09.6 H-low vs H-high

正式head-to-head：

> dual-radiomics cohort。

比较：

```text
M3L vs M3H
```

重点报告：

- paired ΔC-index；
- paired ΔAUC；
- calibration；
- selected-feature stability。

---

# W09.7 不能仅根据P值决定

不使用：

> 某模型P<0.05所以有效。

重点看：

- effect size；
- prediction improvement；
- consistency；
- calibration；
- fold/repeat stability。

---

# W09.8 radiomics selection stability

对每个R_low/R_high/W feature报告：

```text
selection frequency
```

即：

> 在多少outer folds中进入最终模型。

这是判断：

> H-low/H-high哪个habitat携带稳定信号

的重要证据。

---

# W10 — 预设敏感性分析

---

# W10.1 A137 strict sensitivity

A137：

> 不单独作为新的方法开发集。

最优方式是：

在原A393 outer splits中：

- centers仍只由outer training A患者估计；
- validation中的A137患者完全held-out。

然后：

> 只提取A137 validation patients的预测结果。

这样评价：

> 主A方法在strict phenotype中的表现。

避免：

> A137重新聚类并开发另一套方法。

---

# W10.2 A137重点评价

优先：

- M0；
- M1；
- M2；
- M3L；
- M3H。

M4因样本量更小：

> 作为补充。

---

# W10.3 Tumor-volume sensitivity

预设增加：

```text
log(tumor_volume)
```

对以下模型：

```text
M2
M3L
M3H
```

分别形成：

```text
M2-V
M3L-V
M3H-V
```

全部在相同outer splits重新拟合。

---

## 目的

回答：

> habitat signal是否主要为tumor burden proxy。

---

# W10.4 dual-habitat-only sensitivity

只使用：

> dual-radiomics eligible cohort。

比较：

- M2；
- M3L；
- M3H；
- M4。

排除：

> structural single-habitat对结果的影响。

---

# W10.5 Whole-tumor comparator interpretation

M5如果再次低于：

> M0 Clinical

应解释为：

> 当前high-signal-selected cohort中仍未观察到whole-tumor radiomics明显增量价值。

如果M5此次优于M0：

> 同样接受。

不得因为和既往研究不同而修改当前队列或radiomics pipeline。

---

# W11 — A-only final model architecture决定

在B仍然完全不可见的情况下完成。

---

# W11.1 Final model不是一定包含radiomics

可能最终是：

- M0；
- M1；
- M2；
- M3L；
- M3H；
- M4。

任何一种都允许。

---

# W11.2 决策原则

采用：

> hierarchy + incremental evidence + parsimony + stability。

而不是：

> 最高一次C-index。

---

# W11.3 层级逻辑

### Step A

首先评价：

```text
M0 → M1 → M2
```

判断macro-habitat是否具有增量价值。

---

### Step B

如果M2具有合理预测基础，则评价：

```text
M2 → M3L
M2 → M3H
```

---

### Step C

如果只有一个habitat表现出稳定增量：

例如：

> M3L明显更稳定，

则优先选择：

> M3L

而不是为了完整性强行加入R_high。

---

### Step D

如果H-low和H-high均表现出稳定信号：

进一步评价：

> M4。

只有M4提供进一步、稳定的增量时：

> 才采用双habitat radiomics模型。

否则：

> 优先更简洁的单habitat模型。

---

# W11.4 如果所有habitat模型均不改善Clinical

允许最终：

> M0 Clinical

成为final model。

这不是分析失败。

它意味着：

> technical habitat reproducibility并未转化为prognostic utility。

不得因此：

- 改0.1%；
- 改SLIC；
- 改K；
- 增加Wavelet/LoG寻找阳性结果。

---

# W11.5 Whole-tumor W不主导final selection

M5主要是：

> reference comparator。

除非M5在当前A393中出现明确、稳定、可重复的优势，

否则不因为：

> feature数量更多

优先选择M5。

---

# W12 — Full-A final refit

完成模型architecture决定之后执行。

此步骤使用：

> 全部A modeling patients。

---

# W12.1 Final habitat centers

正式deployment model使用：

> full-A frozen technical centers。

即：

```text
H-low = 2.101717
H-high = 3.519630
boundary = 2.810674
```

无需再寻找新的centers。

---

# W12.2 Final habitat masks

使用full-A frozen boundary重新确认：

- H-low；
- H-high。

生成deployment habitat representation。

---

# W12.3 Final G

使用正式冻结：

> `global_descriptors_full_A.csv`

或重新校验相同结果。

---

# W12.4 Final R_low/R_high

如果final model使用habitat radiomics：

使用：

- full-A frozen masks；
- fixed Original parameters；
- fixed candidate pool。

提取最终：

> R_low / R_high。

---

# W12.5 Final W

如果final model使用whole-tumor W：

使用：

> 既有main `muscle_f0.25` candidate pool。

---

# W12.6 Final preprocessing

最终：

- imputation；
- scaling；
- correlation reduction；
- Elastic Net alpha；
- lambda；

只使用：

> full A。

这一步得到：

> deployment parameters。

---

# W12.7 Hyperparameter确定

按照与nested CV相同的：

> inner CV tuning rule

在full A内部确定。

不得：

> 根据B结果调整。

---

# W12.8 最终radiomics feature list

保存：

```text
final_selected_features.csv
```

记录：

- feature name；
- source；
- habitat；
- coefficient；
- selection class。

---

# W12.9 最终模型参数

保存：

- Cox coefficients；
- baseline cumulative hazard / survival；
- scaling parameters；
- imputation parameters；
- selected radiomics；
- alpha；
- lambda；
- 3-year prediction mapping；
- 5-year prediction mapping。

---

# W12.10 A internal performance的正确引用

必须明确：

> full-A refit的训练性能不能作为A内部验证性能。

论文报告的A performance：

> 必须来自W08/W09 nested outer validation。

Full-A fit只用于：

> deployment / B prediction。

---

# W13 — A-only model freeze

完成全部A分析后生成：

```text
prognosis_analysis/model_freeze_lock.json
```

---

# W13.1 必须记录cohort

- A modeling population hash；
- A393 hash；
- A137 hash。

---

# W13.2 technical dependency

- `freeze_lock.json` hash；
- habitat center；
- boundary；
- SLIC config hash；
- preprocessing config hash。

---

# W13.3 modeling protocol

保存：

- `modeling_protocol.json` hash；
- outer split hash；
- inner CV policy；
- outcome definition；
- endpoint cutoff；
- model hierarchy。

---

# W13.4 feature definitions

保存：

```text
Clinical variables
G feature list
R_low candidate hash
R_high candidate hash
W candidate hash
```

---

# W13.5 final model

保存：

```text
final_model_id
final_model_family
final_model_feature_list
final_model_coefficients_hash
preprocessing_parameter_hash
baseline_survival_hash
```

---

# W13.6 必须声明

```text
A_model_development_complete = true

A_model_frozen = true

B_data_read = false

B_validation_unlocked = true
```

生成lock时：

> `B_data_read`必须仍为false。

---

# W13.7 Freeze后禁止修改

一旦`model_freeze_lock.json`生成：

不得根据B：

- 改final model；
- 改H-low/H-high选择；
- 改radiomics features；
- 改lambda；
- 改clinical variables；
- 改habitat；
- 改0.1%；
- 重新校准primary model。

---

# 三十三、每阶段硬门禁

## Gate A — technical freeze

必须：

- formal PASS；
- A393 exact；
- A137 exact；
- feature QC pass；
- `freeze_lock.json`有效。

---

## Gate B — outcome unlock

必须：

- habitat radiomics方法冻结；
- R_low/R_high候选池冻结；
- modeling protocol冻结；
- A/B代码隔离完成。

否则：

> 不读取DFS。

---

## Gate C — nested validation

必须：

- A outcome QC完成；
- modeling population冻结；
- split files冻结。

---

## Gate D — final model selection

必须：

- 所有预设M0–M5分析完成；
- 所有主要paired comparisons完成；
- strict sensitivity完成；
- volume sensitivity完成。

---

## Gate E — A-only model freeze

必须：

- final architecture确定；
- full-A refit完成；
- final model artifacts完整；
- hashes一致；
- B仍未读取。

---

# 三十四、建议输出目录

```text
prognosis_analysis/output/

├── pre_outcome/
│   ├── habitat_radiomics_qc/
│   └── modeling_protocol/

├── A_endpoint_qc/

├── A_modeling/
│   ├── population/
│   └── splits/

├── nested_cv/
│   ├── fold_assets/
│   ├── M0_clinical/
│   ├── M1_burden/
│   ├── M2_global_habitat/
│   ├── M3L_Hlow/
│   ├── M3H_Hhigh/
│   ├── M4_dual_habitat/
│   └── M5_whole_tumor/

├── sensitivity/
│   ├── strict_A137/
│   ├── tumor_volume/
│   └── dual_habitat_only/

├── A_model_comparison/

└── final_model_A/
    ├── final_selected_features.csv
    ├── preprocessing.json
    ├── model_parameters.json
    ├── baseline_survival.csv
    ├── final_model_report.md
    └── model_freeze_lock.json
```

---

# 三十五、建议关键回归测试

在正式A modeling前增加：

## 1. Test validation-patient exclusion

验证：

> outer validation ID绝不进入K-means center fitting。

---

## 2. Test fold-specific habitat

同一患者在不同outer fold中：

> 允许因training boundary不同产生不同habitat assignment。

证明代码没有错误使用：

> full-A boundary。

---

## 3. Test R_low/R_high symmetry

相同：

- extraction；
- ICC；
- preprocessing；
- model selection

规则同时适用于H-low和H-high。

---

## 4. Test structural absence

single-H-low：

> R_high必须NA/undefined。

single-H-high：

> R_low必须NA/undefined。

不能自动填0。

---

## 5. Test training-only scaler

validation feature scaling：

> 只能使用training mean/SD。

---

## 6. Test training-only correlation filter

validation数据：

> 不参与相关性矩阵。

---

## 7. Test training-only Elastic Net tuning

outer validation：

> 不参与alpha/lambda选择。

---

## 8. Test B lock

在`model_freeze_lock.json`不存在时：

> 任意B builder hard fail。

---

# 三十六、A-only阶段完成标志

在进入B验证前，必须同时存在：

```text
habitat_analysis/freeze_lock.json

prognosis_analysis/modeling_protocol.json

prognosis_analysis/output/A_endpoint_qc/

prognosis_analysis/output/nested_cv/

prognosis_analysis/output/A_model_comparison/

prognosis_analysis/output/final_model_A/

prognosis_analysis/model_freeze_lock.json
```

并且能够回答：

- H-high burden是否增加clinical模型信息？
- macro-habitat是否增加信息？
- H-low内部texture是否增加信息？
- H-high内部texture是否增加信息？
- H-low与H-high哪个更稳定？
- 双habitat联合是否进一步改善？
- whole-tumor radiomics在当前A393是否仍缺乏增量价值？
- 这些发现是否对A137稳健？
- 是否主要由tumor volume解释？
- final A model由哪些变量组成？
- final model的全部参数是否已冻结？
- B是否从未参与上述任何决定？

全部满足后：

> **A-only model development complete。**

此时才允许：

> `B_validation_unlocked=true`。
