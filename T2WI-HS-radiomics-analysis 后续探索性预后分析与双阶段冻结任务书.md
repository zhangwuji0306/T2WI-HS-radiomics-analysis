# T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书

## 当前分析性质

> **探索性影像生境预后研究。**

当前尚未确定 H-low 或 H-high 哪一类生境携带主要预后信息，因此不得预设：

> “H-low 一定更重要”

或：

> “H-high 一定更重要”。

本研究的核心科学假说为：

> **在具有可识别瘤内 T2 高信号成分的直肠癌中，将整个肿瘤视为单一 ROI 可能混合具有不同信号表型和生物学属性的组织区域，从而稀释影像组学中的预后信息。基于冻结的 H-low/H-high 生境分割后，预后信息可能存在于 H-low、H-high、两者的空间组织方式，或其组合之中。**

---

# 一、研究目的

本阶段不以：

> 寻找任意性能最高的 radiomics 模型

为目标。

正式回答以下递进问题。

## Q1

在当前 A393 中，冻结的低维 habitat descriptors 是否在临床模型基础上提供增量预测信息？

## Q2

若存在增量信息，它主要来自：

- high-signal burden；
- H-low/H-high 宏观空间组织；
- H-low 内部 texture；
- H-high 内部 texture；
- 两类 habitat 的联合信息？

## Q3

传统 whole-tumor radiomics 在当前 high-signal-selected A393 中是否仍表现出有限增量价值？

## Q4

habitat-specific radiomics 是否能够恢复 whole-tumor averaging 可能掩盖的信息？

---

# 二、既往 whole-tumor radiomics 的定位

此前相关但更宽泛的直肠癌队列中：

> whole-tumor T2WI radiomics 模型的预测表现低于临床模型。

但该既往队列：

> 未按照当前 high-signal eligibility 定义进行筛选。

因此不得写成：

> “whole-tumor radiomics 已被证明在 A393 无预测价值。”

正式定位为：

> **既往相关队列中的结果降低了 whole-tumor radiomics 具有较强增量预测价值的先验可能性，并为研究瘤内 habitat decomposition 提供方法学动机。**

Whole-tumor radiomics 在本研究中保留为：

> reference comparator。

---

# 三、H-low 与 H-high 不设方向性先验

正式冻结：

> H-low 和 H-high 具有完全对称的方法学地位。

不得：

- 先只分析 H-low；
- 看到 H-low 阳性后才分析 H-high；
- 看到 H-high 阳性后才分析 H-low；
- 根据 A outcome 调整两者的技术处理规则。

必须采用相同：

- preprocessing；
- SLIC；
- Original radiomics；
- binWidth；
- ICC rule；
- availability rule；
- nested CV；
- model family；
- evaluation metrics。

---

# 四、已完成 technical evidence

formal patient-level bootstrap 已完成：

```text
requested = 1000
completed = 1000
success = 1000
nondegenerate rate = 1.000

reference H-low center = 2.101717
reference H-high center = 3.519630
reference boundary = 2.810674

bootstrap boundary median = 2.811491
95% interval = [2.708194, 2.924580]

width / center distance = 0.152609

assignment stability median = 0.986711
assignment stability P5 = 0.960980

structural-state stability median = 1.000
structural-state stability P5 = 0.997

formal_eligible = 1
```

正式判定：

> **FORMAL PASS**

因此以后不得根据 outcome：

- 修改 high-signal threshold；
- 修改 SLIC scale；
- 修改 K；
- 修改 patient weighting；
- 修改 normalization；
- 增加 bootstrap 用于方法选择；
- 重新比较旧技术候选方案。

---

# 五、双阶段冻结体系

本研究采用两把完全不同的锁。

---

## 5.1 第一阶段：technical freeze

生成：

```text
habitat_analysis/freeze_lock.json
```

其权限只允许：

```text
A_outcome_unlock = true
```

同时必须：

```text
B_unlock = false
```

第一把锁：

> **绝不允许读取 B。**

---

## 5.2 第二阶段：A-only model freeze

完成 A-only：

- endpoint QC；
- nested validation；
- habitat comparison；
- sensitivity analyses；
- final architecture selection；
- full-A refit；

后生成：

```text
prognosis_analysis/model_freeze_lock.json
```

只有该锁有效后：

> 才允许首次读取 B。

---

## 5.3 第二阶段唯一权限来源

正式废弃将：

```text
b_validation_unlock.json
```

作为独立 B 解锁依据的旧设计。

以后：

> **B 解锁只认 `model_freeze_lock.json`。**

任何兼容文件不得具有独立授权能力。

---

# 六、冻结前新增代码整改门禁

本任务书增加一项硬性前置要求：

> **formal PASS 并不自动意味着可以立即执行 technical freeze 或读取 A outcome。**

在 W01 前必须先完成冻结代码整改。

---

## 6.1 已发现的阻断性问题

当前 `revised_workflow_technical.py` 的正式 freeze 路径调用：

```text
validate_freeze_lock()
```

因此必须保证该函数被正确导入，并通过真正执行路径的 integration test。

只通过：

```text
compileall
```

不足以作为证明。

---

## 6.2 第一把锁必须采用严格 schema

必须至少强制：

```text
freeze_schema_version

habitat_technical_freeze = true
A_outcome_unlock = true
B_unlock = false

formal bootstrap fields

outcome_columns_read = false
B_data_read = false

eligibility_threshold_fraction = 0.001
eligibility_threshold_role = minimum_imaging_presence
threshold_selection_performed = false
threshold_audit_conclusion =
NEUTRAL_WITH_TECHNICAL_CAUTION
```

---

## 6.3 freeze lock 必须绑定实际正式产物

第一阶段锁必须绑定：

- A393 ID；
- A137 ID；
- manifest；
- scanner map；
- preprocessing config；
- SLIC config；
- high-signal screening；
- formal bootstrap summary；
- threshold audit；
- threshold confounding audit；
- global descriptors；
- feature QC；
- feature dictionary；
- habitat map manifest。

不能只证明：

> 方法参数没变。

还必须证明：

> **被冻结的数据产物本身没变。**

---

# 七、正式技术主方法

主方法固定：

```text
muscle-mean normalization
→ [1,1,2] mm resampling
→ 4 mm 3D SLIC
→ all effective tumor-intersecting supervoxels
→ patient-balanced cross-case K-means
→ K=2
```

病例 i 有 n_i 个有效 supervoxels：

\[
w_{ij}=1/n_i
\]

因此：

\[
\sum_j w_{ij}=1
\]

每例患者对全局 phenotype center fitting 的总权重相同。

---

# 八、固定 technical centers

full-A technical freeze 使用：

```text
H-low center = 2.101717
H-high center = 3.519630
boundary = 2.810674
```

这些值用于：

- full-A technical frozen representation；
- deployment/final refit；
- technical reporting。

但：

> **不得用于 nested outer validation 的 habitat assignment。**

nested CV 中必须在每个 outer training fold 内重新拟合 centers。

---

# 九、A 集正式研究人口

## 主分析

```text
A393
```

## strict sensitivity

```text
A137
```

A137 不得重新：

- 选 threshold；
- 拟合技术主方法；
- 修改 habitat definition。

---

# 十、主终点

主终点：

> DFS

主要时间点：

- 3 years；
- 5 years。

OS/CSS：

> 次要终点，在主 DFS protocol 固定后再分析。

---

# 十一、固定 clinical block C

固定 9 项：

1. 年龄；
2. `CEA_log`；
3. `mrT_4级`；
4. `mrN_3级`；
5. MRF；
6. mrEMVI；
7. thickness；
8. EID；
9. 活检病理非腺癌。

以下不进入 primary prediction model：

- 性别；
- length；
- distance。

术后变量不进入治疗前主预测模型。

---

# 十二、低维 global habitat block G

固定六项：

1. `H_high_fraction`
2. `sv_median_minus_boundary`
3. `sv_IQR`
4. `interface_density`
5. `H_high_largest_component_tumor_fraction`
6. `H_high_radial_burden`

描述：

- high-signal burden；
- global signal position；
- supervoxel-level heterogeneity；
- inter-habitat interface；
- H-high connectivity；
- radial localization。

以下保留 descriptive/secondary：

```text
habitat_entropy
H_high_component_density
```

---

# 十三、habitat-specific Original radiomics

正式定义两个对称特征块：

```text
R_low
R_high
```

---

## 13.1 PyRadiomics 参数

固定：

```text
imageType = Original
binWidth = 0.248808
normalize = false
resample = false
```

H-low 与 H-high 不分别重新估计 binWidth。

---

## 13.2 提取类别

完整提取：

- first-order；
- shape；
- GLCM；
- GLRLM；
- GLSZM；
- GLDM；
- NGTDM。

---

## 13.3 主预测候选

优先：

> texture。

即：

- GLCM；
- GLRLM；
- GLSZM；
- GLDM；
- NGTDM。

First-order：

> secondary。

Shape：

> exploratory/QC。

---

# 十四、habitat radiomics reproducibility

必须使用 A 内双读者数据。

每个 reader 均独立经过完整流程。

分别计算：

```text
R_low ICC(2,1)
R_high ICC(2,1)
```

预筛选：

```text
ICC > 0.75
```

并预设最低有效 pair：

```text
n_valid_pairs >= 10
```

---

# 十五、structural single habitat

A393 当前技术状态包括：

- dual-habitat；
- single-H-low；
- single-H-high。

单生境：

> 不是 technical failure。

---

## 15.1 structural zero

以下可以按结构规则为 0：

- missing phenotype existence；
- missing phenotype fraction；
- habitat entropy；
- interface density；
- H-high connected component descriptors；
- H-high radial burden 等具有明确“无该 phenotype”语义的全局量。

---

## 15.2 texture 不得填 0

如果 H-high 不存在：

```text
R_high = structurally undefined
```

如果 H-low 不存在：

```text
R_low = structurally undefined
```

不能把结构性不存在与普通随机 missing 混在一起。

---

# 十六、whole-tumor radiomics W

Whole-tumor radiomics 保留：

- Original；
- Wavelet；
- LoG；

但其正式角色为：

> comparator。

不得因为特征更多而优先作为 final model。

---

# 十七、正式模型体系

## M0

```text
Clinical
C
```

## M1

```text
C + H_high_fraction
```

## M2

```text
C + G
```

## M3L

```text
C + G + R_low
```

## M3H

```text
C + G + R_high
```

## M4

```text
C + G + R_low + R_high
```

仅 dual-radiomics eligible population。

## M5

```text
C + W
```

reference comparator。

---

# 十八、正式模型比较层级

固定：

```text
M0 → M1
```

回答：

> high-signal burden。

```text
M1 → M2
```

回答：

> macro-habitat organization。

```text
M2 → M3L
```

回答：

> H-low internal texture。

```text
M2 → M3H
```

回答：

> H-high internal texture。

```text
M3L vs M3H
```

回答：

> 哪类 habitat 表现出更稳定的增量 prognostic information。

```text
M2 → M4
```

回答：

> dual-habitat texture complementarity。

```text
M0 → M5
```

回答：

> whole-tumor radiomics reference value。

---

# 十九、禁止模型穷举

主分析不得临时新增：

```text
C + W + R_low
C + W + R_high
C + W + G + R_low
C + W + G + R_high
C + W + G + R_low + R_high
```

如果以后开展：

> 必须明确标记 post-hoc exploratory。

不得用于 primary final model selection。

---

# 二十、fold-specific habitat 是硬门禁

A 内部验证时：

> 不得使用 full-A center/boundary 为所有患者预生成固定 habitat 后直接 CV。

每个 outer fold 必须：

```text
Train_outer
↓
train-only patient-balanced K-means
↓
C_low_train / C_high_train / b_train
↓
train + validation 都用 b_train assignment
↓
fold-specific G
↓
fold-specific R_low / R_high
↓
train-only preprocessing
↓
inner tuning
↓
outer validation prediction
```

Validation_outer：

> 绝不参与 center fitting。

---

# 二十一、可提前缓存内容

可以预缓存 patient-internal、outcome-independent：

- muscle-normalized image；
- tumor ROI；
- SLIC labels；
- supervoxel means。

无需每个 outer fold 重跑 SLIC。

但每 fold 必须重新：

```text
center fitting
boundary assignment
habitat mask
G
R_low/R_high
```

---

# 二十二、Nested CV

固定：

```text
Outer:
5-fold × 10 repeats

Inner:
5-fold
```

Outer：

> event stratified。

---

## 22.1 High-dimensional models

R_low、R_high、W：

> Elastic Net Cox / LASSO Cox。

所有数据驱动步骤进入 training-only pipeline：

- imputation；
- variance filtering；
- correlation reduction；
- scaling；
- feature selection；
- alpha；
- lambda。

Outer validation 不参与任何拟合。

---

# 二十三、A/B 数据隔离

本节为硬安全规则。

---

## 23.1 技术 A

技术影像与 outcome-blind 数据：

> 第一把锁前可以读取。

---

## 23.2 A clinical/outcome

必须：

```text
freeze_lock.json valid
```

才允许读取。

---

## 23.3 B data

任何 B：

- clinical；
- outcome；
- radiomics；
- habitat；
- QC；
- missingness；
- distribution；
- model performance；

均必须：

```text
model_freeze_lock.json valid
```

之后才允许读取。

---

## 23.4 “不得读取”的定义

禁止以下模式：

```text
read entire A+B file
↓
construct full dataframe
↓
filter A
```

如果该操作已经使 B 内容进入内存：

> 已经违反 B blinding。

必须做到：

> 权限检查位于真实数据读取入口之前。

---

# 二十四、A-only builder 要求

在首次读取 A outcome 前，现有 modeling builder 必须完成重构。

正式支持：

```text
--split A
```

在第二把锁前：

```text
--split B
--split all
```

必须 hard fail。

A 模式不得：

- 输出 B 文件；
- 统计 B 样本量；
- 统计 B missingness；
- 加载 B habitat；
- 查看 B radiomics；
- 读取 B outcome。

---

# 二十五、A/B split 定义统一

全项目必须只保留一个正式 split resolver。

例如：

```text
resolve_cohort_membership()
```

其 A 定义固定为既定 scanner rule。

其他脚本不得自行重新实现 A/B 判定逻辑。

---

# 二十六、Tumor volume sensitivity

由于 outcome-blind technical audit 已发现：

> high-signal phenotype 与 tumor volume 存在依赖。

因此预设：

```text
M2-V
M3L-V
M3H-V
```

加入：

```text
log(tumor_volume)
```

用于检验：

> habitat signal 是否主要为 tumor-burden proxy。

不得据此修改 habitat definition。

---

# 二十七、A137 strict sensitivity

A137 不作为第二个方法开发集。

优先：

> 在 A393 nested CV 框架下评价 strict phenotype patients 的 held-out prediction。

重点：

- M0；
- M1；
- M2；
- M3L；
- M3H。

M4：

> supplemental。

---

# 二十八、dual-habitat sensitivity

针对 R_low 与 R_high 均定义的人群：

比较：

```text
M2
M3L
M3H
M4
```

用于排除：

> structural single-habitat handling 对结论的主要影响。

---

# 二十九、结果解释原则

不能只强调：

> 哪个模型 C-index 最大。

应同时看：

- paired ΔC-index；
- Uno C-index；
- 3-year AUC；
- 5-year AUC；
- Brier；
- calibration；
- selection stability；
- fold/repeat consistency。

---

# 三十、A-only final architecture 决策

允许 final model 为：

```text
M0
M1
M2
M3L
M3H
M4
```

决策采用：

```text
hierarchy
+ incremental evidence
+ parsimony
+ stability
```

不是：

> 最大一次性能值。

---

## 30.1 如果 H-low 明显更稳定

可以最终选择 M3L。

但结论必须描述为：

> exploratory A-set finding requiring external validation。

---

## 30.2 如果 H-high 更稳定

同样接受。

不得回头修改研究假说。

---

## 30.3 两者均有限

如果 G 有价值而 R_low/R_high 无增量：

> 表明 macro-habitat organization 比复杂 texture 更稳健。

---

## 30.4 全部无增量

如果 G、R_low、R_high 均无明显增量：

> 这是有效研究结果。

不得：

- 改 threshold；
- 改 SLIC；
- 改 K；
- 增加高维滤波以寻找阳性结果。

---

# 三十一、Full-A final refit

Final architecture 决定后：

> 使用全部 A modeling patients 拟合 deployment model。

正式 deployment habitat：

```text
H-low = 2.101717
H-high = 3.519630
boundary = 2.810674
```

full-A refit 中的：

- imputation；
- scaling；
- correlation reduction；
- alpha；
- lambda；
- final feature list；
- Cox coefficients；
- baseline survival；

全部形成正式 deployment artifacts。

---

# 三十二、第二阶段 model freeze

正式生成：

```text
prognosis_analysis/model_freeze_lock.json
```

必须绑定：

## Cohort

```text
A modeling population hash
A393 hash
A137 hash
```

## Technical dependency

```text
freeze_lock hash
preprocessing config hash
SLIC config hash
centers
boundary
```

## Modeling protocol

```text
modeling_protocol hash
outer split hash
candidate hashes
outcome definition hash
```

## Final model

```text
final_model_id
final_model_family
final_feature_list_hash
coefficient_hash
preprocessing_parameter_hash
baseline_survival_hash
final_model_artifact_hash
```

并声明：

```text
A_model_development_complete = true
A_model_frozen = true
B_data_read = false
B_validation_unlocked = true
```

---

# 三十三、B validation

只有第二阶段锁：

> 生成且通过严格 schema/hash 校验

后才允许第一次读取 B。

B 只用于：

> **一次性外部验证。**

不得利用 B：

- 改 final model；
- 改 feature list；
- 改 H-low/H-high；
- 改 lambda；
- 改 clinical block；
- 改 threshold；
- 改 habitat method；
- 修改 primary model 后重新验证。

---

# 三十四、关键代码质量门禁

在正式 A outcome analysis 前必须至少存在以下测试：

1. stage7 synthetic integration；
2. freeze lock strict schema；
3. freeze artifact tampering；
4. A outcome pre-lock hard fail；
5. B pre-model-freeze hard fail；
6. B fail occurs before physical read；
7. centralized split resolver；
8. validation patient excluded from K-means；
9. fold-specific habitat；
10. R_low/R_high symmetry；
11. structural absence handling；
12. training-only imputation/scaling；
13. training-only correlation filtering；
14. training-only Elastic Net tuning；
15. final model freeze validation。

---

# 三十五、第一阶段 technical freeze 完成标准

必须：

```text
formal PASS
A393 exact
A137 exact
feature QC PASS
artifact manifest complete
freeze_lock strict validation PASS
```

之后：

> 仅 A clinical/outcome 解锁。

---

# 三十六、A outcome unlock 完成标准

首次读取 DFS 前必须：

- technical freeze 完成；
- habitat radiomics technical framework 冻结；
- R_low candidate pool 冻结；
- R_high candidate pool 冻结；
- modeling protocol 冻结；
- A-only data access 完成；
- B reader hard-fail 测试通过。

任何一项缺失：

> 不读取 DFS。

---

# 三十七、A-only model development complete 标准

进入 B 前必须完成：

- endpoint QC；
- modeling population freeze；
- split freeze；
- repeated nested CV；
- paired model comparisons；
- A137 sensitivity；
- tumor-volume sensitivity；
- dual-habitat sensitivity；
- final architecture；
- full-A refit；
- model artifacts；
- strict `model_freeze_lock.json`。

且必须证明：

> B 从未参与上述任何决策。

---

# 三十八、论文中的核心假说

正式表述：

> **We hypothesized that whole-tumor radiomic averaging may obscure prognostically relevant heterogeneity by mixing spatially distinct T2 signal phenotypes. Accordingly, we evaluated whether prognostic information was preferentially carried by the H-low habitat, the H-high habitat, their macroscopic spatial organization, or combinations thereof, without prespecifying which habitat would be prognostically dominant.**

---

# 三十九、最终研究定位

本阶段不是：

> 寻找哪个影像模型 AUC 最高。

而是回答：

> **在具有 T2 高信号成分的直肠癌中，将肿瘤分解为 H-low 与 H-high 后，是否能够发现 whole-tumor averaging 所掩盖的预后信息，以及该信息主要存在于 high-signal burden、macro-habitat structure、H-low texture、H-high texture 或两类 habitat 的组合之中。**

因此正式定位：

```text
Clinical model
= baseline prediction model

Whole-tumor radiomics
= reference comparator

Global habitat descriptors
= macro-habitat representation

H-low radiomics
= candidate intra-habitat representation

H-high radiomics
= equally ranked candidate intra-habitat representation

H-low vs H-high
= exploratory biological comparison

B cohort
= one-time external validation only
```

并坚持：

> **技术稳定性不等于预后有效性；阴性预测结果同样属于有效研究结论。**
