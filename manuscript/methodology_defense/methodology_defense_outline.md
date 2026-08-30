# `manuscript/methodology_defense` 建议报告目录及大纲

建议采用带编号的文件名，使方法学证据链按研究流程排列：

```text
manuscript/
└── methodology_defense/
    ├── 00_methodology_defense_index.md
    ├── 01_high_signal_eligibility_threshold_defense.md
    ├── 02_cohort_definition_and_data_blinding_defense.md
    ├── 03_peritumoral_reference_and_muscle_normalization_defense.md
    ├── 04_slic_physical_scale_and_supervoxel_design_defense.md
    ├── 05_patient_balanced_cross_case_clustering_defense.md
    ├── 06_structural_single_habitat_handling_defense.md
    ├── 07_bootstrap_stability_and_formal_freeze_defense.md
    ├── 08_strict_A137_sensitivity_cohort_defense.md
    ├── 09_habitat_feature_dictionary_and_volume_confounding_defense.md
    ├── 10_reader_reproducibility_and_primary_reader_defense.md
    ├── 11_nested_validation_and_information_leakage_defense.md
    ├── 12_device_split_and_external_validation_defense.md
    ├── 13_reproducibility_provenance_and_freeze_lock_defense.md
    └── 14_raw_high_signal_vs_habitat_construct_defense.md
```

---

# 00_methodology_defense_index.md

## 目的

作为整个文件夹的导航页。

## 建议内容

### 1. 项目核心科学问题

- T2WI高信号表型；
- 跨病例habitat；
- DFS预后价值。

### 2. 方法学争议地图

列出：

|问题|对应报告|冻结状态|
|---|---|---|
|为什么是0.1%？|01|frozen|
|为什么A393？|02|frozen|
|为什么肌肉归一化？|03|frozen|
|为什么4 mm SLIC？|04|frozen|
|为什么患者等权K=2？|05|frozen|
|空habitat怎么处理？|06|frozen|
|bootstrap为什么1000次？|07|pending/formal|
|为什么A137？|08|frozen|
|体积混杂怎么办？|09|prespecified sensitivity|
|为什么R1主读者？|10|frozen|
|如何避免CV leakage？|11|frozen protocol|
|为什么A/B这样分？|12|frozen|
|如何保证可复现？|13|freeze-dependent|

### 3. 方法学时间线

从：

> threshold定义 → 方法选择 → SLIC修复 → A393 → preflight → formal → outcome unlock → B validation

标注每个阶段是否已经读取结局/B。

### 4. 一句话原则

> All technical choices were finalized using outcome-blind A-set information before prognostic modeling, while B remained unavailable for method selection.

---

# 02_cohort_definition_and_data_blinding_defense.md

## 核心问题

为什么主分析是A393/B107，严格分析A137/B23？技术流程是否偷看结局或B？

## 大纲

### 1. 原始队列到筛选母队列的流程

- manifest；
- scanner map；
- exclusion；
- high-signal screening。

### 2. A/B定义

- GE MEDICAL SYSTEMS；
- DISCOVERY MR750；
- 3.0 T；
- keyed merge，而不是行位置对齐。

### 3. 技术A队列独立于prognosis dataset

- `technical_cohort_manifest`；
- 禁止从clinical/outcome表推导技术队列。

### 4. A393 identity audit

- old A393；
- new A393；
- symmetric difference=0。

### 5. A137 subset assertion

- exactly 137；
- strict⊂lenient。

### 6. 数据访问边界

- outcome_columns_read=false；
- B_data_read=false。

### 7. 为什么不在技术阶段读取B

- 防止external validation set contamination；
- 不用于ICC、阈值选择、参数调优。

### 8. 可用于论文/审稿回复的简短表述

---

# 03_peritumoral_reference_and_muscle_normalization_defense.md

## 核心问题

为什么原始筛选用瘤周脂肪，高阶分析又使用肌肉均值归一化？

## 大纲

### 1. 两种reference承担不同角色

**Peritumoral fat**

- 原始高T2信号的病例内影像学参照。

**Muscle mean**

- 跨病例信号标准化参照。

### 2. 为什么MRI不能直接比较绝对灰度值

- scanner gain；
- coil；
- sequence；
- acquisition scaling。

### 3. R1/R2肌肉标签规则

- R1固定标签；
- R2标签2/3判别；
- lower raw mean=muscle；
- manifest显式保存结果；
- 禁止猜测或z-score fallback。

### 4. muscle normalization公式

### 5. 为什么N4不是主方案

### 6. normalization QC

- reference mean；
- CV；
- gradient；
- failure handling。

### 7. fat reference与muscle normalization为什么不矛盾

这是非常值得单独解释的一节。

---

# 04_slic_physical_scale_and_supervoxel_design_defense.md

## 核心问题

为什么使用4 mm 3D SLIC？为什么是`[4,4,2]` voxel supergrid？

## 大纲

### 1. SLIC目的

不是精确重建黏液边界，而是得到具有局部空间支持的信号单元。

### 2. 输入spacing

`[1,1,2] mm`

### 3. 物理尺度定义

`round(4 mm / spacing_xyz)`

得到：

`[4,4,2] voxels`

对应：

`[4,4,4] mm`

### 4. 为什么不能根据FOV计算SuperGridSize

记录此前bug及其修复，但不要在manuscript正文暴露无关的软件历史；作为内部defense记录。

### 5. FOV independence regression test

不同FOV、同spacing → 相同physical SLIC scale。

### 6. 为什么3D而不是逐层2D

### 7. connectivity

6-connectivity相关决定。

### 8. 为什么4 mm而不是更小/更大尺度

- 空间平滑；
- noise suppression；
- 保留局部异质性；
- 方法选择阶段依据。

### 9. limitation

4 mm会稀释极低负荷raw-high signal，这不是算法失败。

---

# 05_patient_balanced_cross_case_clustering_defense.md

## 核心问题

为什么不是病例内K-means？为什么不是所有supervoxels简单等权？

## 大纲

### 1. 目标

建立跨患者共享的H-low/H-high定义。

### 2. 为什么采用cross-case K=2

- 可比较；
- 每个患者使用相同中心和boundary；
- 避免patient-specific labels无法跨人解释。

### 3. 为什么K=2

- 低维；
- 预设高/低表型；
- 避免小样本过度聚类；
- 方法选择结果。

### 4. patient-balanced weighting

每例：

`w_ij = 1 / n_i`

从而：

`Σ_j w_ij = 1`

### 5. 为什么必要

否则：

> 大肿瘤 / 超体素多的患者

会主导全局中心。

### 6. 为什么保留全部有效supervoxels

不再设2000 cap。

### 7. KMeans参数

- K=2；
- k-means++；
- n_init=100；
- seed=12345；
- max_iter=300；
- tol=1e-4。

### 8. local K=2的定位

只用于机制诊断，不参与主habitat生成。

---

# 06_structural_single_habitat_handling_defense.md

## 核心问题

如果一个患者只有H-low或只有H-high，是失败病例还是合理表型？

## 大纲

### 1. 历史问题

最初可能将单habitat误视为technical failure。

### 2. 最终定义

`single-H-low`
`single-H-high`
`dual-habitat`

均属于合法结构状态。

### 3. 为什么单habitat不是算法失败

在共享global boundary下，某病例所有supervoxels位于一侧完全可能。

### 4. 25/393结构性单habitat

### 5. feature structural-zero规则

可取0：

- H-high fraction；
- entropy；
- interface；
- H-high connected components descriptors。

不能填0：

> 不存在habitat内部的纹理特征。

### 6. hard technical failure定义

与structural state彻底区分。

### 7. 为什么这一处理避免selection bias

不能因为表型“不够异质”就排除患者。

---

# 07_bootstrap_stability_and_formal_freeze_defense.md

## 核心问题

为什么需要20/200/1000三级bootstrap？为什么200次不能直接freeze？

## 大纲

### 1. bootstrap目标

患者层面method stability，不是预后置信区间。

### 2. 三层设计

- smoke=20；
- preflight=200；
- formal=1000。

### 3. 为什么患者层面重采样

患者才是独立统计单位。

### 4. 每个replicate患者等权

### 5. deterministic seed和checkpoint/resume

### 6. preflight累计收敛结果

50/100/150/200完整表。

突出：

- nondegenerate=1；
- boundary ~2.8104；
- assignment median ~0.986；
- P5 ~0.959；
- structural state=1。

### 7. CLEAR PASS依据

不是贴门槛。

### 8. 为什么还需要formal 1000

尾部分位数精度与正式冻结。

### 9. smoke/preflight不能unlock

### 10. freeze gate

- formal=1000；
- baseline；
- center reproducibility；
- robustness；
- A393/A137；
- feature QC。

---

# 08_strict_A137_sensitivity_cohort_defense.md

## 核心问题

为什么需要第二套严格队列？为什么不是直接用A137做主分析？

## 大纲

### 1. 主A393与A137承担不同estimand

### 2. A137定义

- high_fraction ≥1%；
- LCC ≥128 mm³；
- 2-mm internal core ≥32 mm³。

### 3. 三个条件分别控制什么

- burden；
- spatial connectivity；
- boundary/partial-volume contamination。

### 4. 为什么A137不重新聚类

必须沿用全A中心，避免sensitivity cohort重新定义表型。

### 5. 为什么它不是threshold-selection结果

### 6. 未来如何比较A393与A137

- effect direction；
- effect magnitude；
- calibration/performance；
- 不以显著/不显著作为一致性唯一依据。

---

# 09_habitat_feature_dictionary_and_volume_confounding_defense.md

## 核心问题

为什么选择当前低维feature block？如何处理肿瘤体积混杂？

## 大纲

### 1. 主feature block

- `H_high_fraction`
- `sv_median_minus_boundary`
- `sv_IQR`
- `interface_density`
- `H_high_largest_component_tumor_fraction`
- `H_high_radial_burden`

### 2. descriptive-only

- habitat entropy；
- H-high component density。

### 3. 为什么不同时使用H-low fraction

`H_low = 1-H_high`

避免确定性共线。

### 4. 特征分别代表的生物/空间含义

- burden；
- intensity position；
- heterogeneity；
- interface；
- connectivity；
- radial localization。

### 5. volume dependency

整合0.1% technical confounding结果。

### 6. 为什么不直接删除所有volume-correlated feature

影像表型可以同时包含真实生物学与测量学volume information。

### 7. 预设volume-adjusted sensitivity analysis

建议现在写入，DFS解盲前冻结。

### 8. feature number控制

避免高维过拟合。

---

# 10_reader_reproducibility_and_primary_reader_defense.md

## 核心问题

为什么主分析使用R1？R2如何参与？

## 大纲

### 1. R1作为primary reader的预设定位

### 2. R2不定义主队列

### 3. R1/R2用于什么

- segmentation reliability；
- feature reproducibility；
- threshold reproducibility。

### 4. 21例high_fraction结果

- rho=0.891；
- ICC=0.885；
- binary κ限制。

### 5. κ为什么受prevalence影响

### 6. 为什么连续ICC比21例binary κ更重要

### 7. ICC feature selection只能在A完成

B ICC预冻结不可见。

---

# 11_nested_validation_and_information_leakage_defense.md

## 核心问题

生境中心、缺失值、标准化和特征选择如何防止CV信息泄漏？

## 大纲

这是后续建模阶段最重要的报告之一。

### 1. 基本原则

外层验证折不能参与任何参数估计。

### 2. 每个outer training fold内必须重新拟合

- habitat KMeans centers；
- boundary；
- imputation；
- scaling；
- feature processing；
- hyperparameter tuning。

### 3. validation fold只应用training-fitted parameters

### 4. 为什么不能使用full-A centers计算CV性能

会产生unsupervised leakage。

### 5. full-A frozen centers可以用于什么

- descriptive final-A map；
- 最终A训练模型；
- 冻结后B的一次性应用。

### 6. nested CV workflow图

### 7. B validation

最终模型、A-fitted参数一次性应用。

---

# 12_device_split_and_external_validation_defense.md

## 核心问题

为什么A/B按设备划分而不是随机划分？

## 大纲

### 1. A/B设备定义

### 2. 为什么设备留出比随机split更严格

测试：

> acquisition-domain transportability。

### 3. 为什么B不能参与任何开发

### 4. B107及strict B23

### 5. B只执行一次

### 6. 外部/设备验证应报告什么

- coverage；
- C-index；
- calibration；
- time-dependent AUC；
- feature distribution shift。

### 7. 如果B性能下降如何解释

不能回头修改A模型。

---

# 13_reproducibility_provenance_and_freeze_lock_defense.md

## 核心问题

如何证明分析不是在看到结果以后悄悄改变参数？

## 大纲

### 1. Git commit provenance

### 2. input SHA-256

### 3. preprocessing config hash

### 4. SLIC config hash

### 5. A393/A137 ID hash

### 6. bootstrap summary hash

### 7. threshold audit provenance

建议新增：

- `eligibility_threshold_fraction=0.001`
- `eligibility_threshold_role=minimum_imaging_presence`
- threshold audit hash；
- technical confounding audit hash。

### 8. freeze_lock

只有formal 1000和全部gate通过才生成。

### 9. atomic staging/promotion

### 10. outcome unlock规则

### 11. B unlock与model freeze应区分

建议明确：

- habitat freeze；
- model freeze；
- B validation unlock。

---

# 14_raw_high_signal_vs_habitat_construct_defense.md

## 核心问题

这是我特别建议单独写的一份。

未来审稿人很可能问：

> “既然你用high signal筛人，为什么SLIC后很多病例没有H-high？”

## 大纲

### 1. 两个construct的定义

**Raw supra-reference high signal**

病例eligibility phenotype。

**H-high habitat**

跨病例4 mm spatial phenotype。

### 2. 为什么二者不应一一对应

- smoothing；
- partial volume；
- supervoxel averaging；
- global K=2；
- patient-balanced centers。

### 3. post-SLIC retention结果

完整分层表。

### 4. single-H-low为何合理

患者可具有raw-high证据，但在4 mm共享尺度上仍整体落入H-low。

### 5. bootstrap证明这种状态稳定

### 6. 为什么不能要求raw-high必须变成H-high

否则是circular construct definition。

### 7. 对生物学解释的限制

H-high不能简单等同于“黏液”。

### 8. 最终论文措辞

> The screening phenotype and the derived habitat phenotype represent related but non-identical spatial scales of T2 signal heterogeneity.

---

# 建议优先级

在正式1000次bootstrap之前，最值得立即完成全文的报告：

**第一优先级**

1. `01_high_signal_eligibility_threshold_defense.md`
2. `04_slic_physical_scale_and_supervoxel_design_defense.md`
3. `05_patient_balanced_cross_case_clustering_defense.md`
4. `06_structural_single_habitat_handling_defense.md`
5. `07_bootstrap_stability_and_formal_freeze_defense.md`
6. `14_raw_high_signal_vs_habitat_construct_defense.md`

这些全部建立在当前结局盲态技术结果之上，可以现在冻结。

**第二优先级**

7. `02_cohort_definition_and_data_blinding_defense.md`
8. `03_peritumoral_reference_and_muscle_normalization_defense.md`
9. `08_strict_A137_sensitivity_cohort_defense.md`
10. `10_reader_reproducibility_and_primary_reader_defense.md`
11. `13_reproducibility_provenance_and_freeze_lock_defense.md`

这些主要用于Methods和审稿回复。

**第三优先级，在首次正式预后建模前完成**

12. `09_habitat_feature_dictionary_and_volume_confounding_defense.md`
13. `11_nested_validation_and_information_leakage_defense.md`
14. `12_device_split_and_external_validation_defense.md`

其中第11份尤其必须在真正计算A集内部模型性能之前写清楚，因为fold-specific KMeans fitting属于防止信息泄漏的核心原则。