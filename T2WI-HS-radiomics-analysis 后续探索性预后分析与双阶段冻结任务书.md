# T2WI-HS-radiomics-analysis 后续探索性预后分析与双阶段冻结任务书

**当前分析性质：**

> 探索性影像生境预后研究。

当前尚未确定H-low或H-high哪一类生境携带主要预后信息，因此不得预设“H-low一定更重要”或“H-high一定更重要”。

本阶段的核心科学假说为：

> **在具有可识别瘤内T2高信号成分的直肠癌中，将整个肿瘤视为单一ROI可能混合具有不同信号表型和生物学属性的组织区域，从而稀释影像组学中的预后信息。基于冻结的H-low/H-high生境分割后，预后信息可能存在于H-low、H-high、两者的空间组织方式，或其组合之中。**

---

# 一、既往证据及其在本研究中的定位

## 1.1 既往整瘤radiomics结果

此前已经完成过整瘤T2WI radiomics分析。

结果提示：

> 整瘤radiomics模型的预测性能低于临床模型。

这一结果是本研究提出habitat分析的重要背景证据。

但必须保留一个重要限制：

此前分析使用的是：

> 未按照当前“存在T2高信号成分”标准筛选的更宽泛患者队列，

因此与目前的：

> A393主队列

并不完全相同。

所以当前不能直接写成：

> “整瘤radiomics已被证明在A393中无预测价值。”

更准确的表述是：

> **既往不同但相关队列中的结果降低了整瘤radiomics具有较强增量预测价值的先验可能性，并为进一步研究肿瘤内部生境分解提供了方法学动机。**

---

# 二、当前核心研究问题

本阶段不再以：

> “寻找性能最高的任意radiomics模型”

为目标。

而是围绕以下递进问题展开。

## Q1

在当前A393中，冻结的低维habitat descriptors是否在临床模型基础上提供增量预测信息？

## Q2

如果存在增量信息，它主要来自：

- 高信号负荷本身；
- H-low/H-high空间组织；
- H-low内部纹理；
- H-high内部纹理；
- 还是H-low与H-high的组合？

## Q3

传统whole-tumor radiomics在当前A393中是否再次表现出有限的增量价值？

## Q4

habitat-specific radiomics是否能够提取出整瘤radiomics中因不同组织成分混合而被稀释的信息？

---

# 三、不设置H-low与H-high的方向性先验

虽然此前经验提出过：

> “H-low可能才是主要预后区域”

这一假说，

但目前证据不足以将其作为正式方向性假设。

因此冻结前必须规定：

> **H-low和H-high具有对称的分析地位。**

不得：

- 先只分析H-low；
- 看到H-low结果好后才分析H-high；
- 或反之。

两种habitat-specific radiomics必须采用：

- 相同预处理；
- 相同Original特征定义；
- 相同ICC规则；
- 相同nested-CV；
- 相同模型家族；
- 相同评价指标。

H-low和H-high谁更具有预测信息：

> 由A集探索性分析结果回答。

不能在结果出来前预设。

---

# 四、第一阶段：完成technical freeze

formal patient-level bootstrap已经完成：

- 1000/1000；
- nondegenerate rate=1.000；
- reference boundary=2.810674；
- bootstrap boundary median=2.811491；
- 95% CI=[2.708194, 2.924580]；
- CI width / center distance=0.152609；
- assignment stability median=0.986711；
- assignment stability P5=0.960980；
- structural-state stability median=1.000；
- structural-state P5=0.997；
- `formal_eligible=1`。

结论：

> **FORMAL PASS。**

因此不再：

- 修改0.1%；
- 修改4 mm SLIC；
- 修改K；
- 修改患者等权策略；
- 修改normalization；
- 增加bootstrap重复用于方法选择。

下一步执行technical freeze并生成第一阶段：

`freeze_lock.json`

该锁仅：

> 解锁A outcome。

仍然：

> B locked。

---

# 五、A集正式建模队列

## 5.1 主队列

A393。

## 5.2 严格敏感性队列

A137。

A137不得重新：

- 选阈值；
- 重新聚类；
- 重新定义habitat。

---

# 六、主终点

主终点：

> DFS。

主要时间点：

- 3年；
- 5年。

OS/CSS为次要结局，在主DFS分析方案冻结后再分析。

---

# 七、固定临床基线变量块 C

Clinical block固定为9项：

1. 年龄；
2. `CEA_log`；
3. `mrT_4级`；
4. `mrN_3级`；
5. MRF；
6. mrEMVI；
7. thickness；
8. EID；
9. 活检病理非腺癌。

以下变量不进入主预测模型：

- 性别；
- length；
- distance。

术后病理变量不进入治疗前prediction model。

---

# 八、低维全局habitat特征块 G

固定6项：

1. `H_high_fraction`
2. `sv_median_minus_boundary`
3. `sv_IQR`
4. `interface_density`
5. `H_high_largest_component_tumor_fraction`
6. `H_high_radial_burden`

这些描述的是：

- H-high burden；
- 全局信号位置；
- supervoxel级异质性；
- habitat interface；
- H-high connectivity；
- radial localization。

`habitat_entropy`和`H_high_component_density`继续作为描述性/次要变量。

---

# 九、新增habitat-specific Original radiomics

本阶段正式增加两个对称特征块：

## R_low

> H-low ROI内提取的Original PyRadiomics特征。

## R_high

> H-high ROI内提取的Original PyRadiomics特征。

---

# 十、为什么当前只提Original

不在本阶段扩展：

- Wavelet；
- LoG。

理由：

1. habitat ROI比whole-tumor ROI更小；
2. 高阶滤波会大幅增加维度；
3. 小H-high区域可能产生较高纹理不稳定性；
4. 当前科学问题首先是验证：
   > 分区本身是否恢复预后信息，
   而不是最大化特征空间。

Wavelet/LoG habitat radiomics如以后开展：

> 明确标记为post-hoc exploratory analysis。

---

# 十一、habitat Original特征类别

提取完整Original：

- first-order；
- shape；
- GLCM；
- GLRLM；
- GLSZM；
- GLDM；
- NGTDM。

但预测建模层级不同。

## 11.1 主要habitat-radiomics候选

优先：

> texture features。

原因：

H-low/H-high本身由signal-based clustering定义。

因此first-order Mean、Median、Percentiles等与habitat定义存在一定数学耦合。

而texture特征回答的是：

> 在已经定义为H-low/H-high之后，该区域内部的空间灰度组织是否仍携带信息？

这是当前低维G block未直接描述的内容。

---

## 11.2 First-order

提取、QC并保留。

主要作为：

> secondary habitat-radiomics candidate。

---

## 11.3 Shape

完整提取用于QC和探索。

但不作为主要habitat-radiomics signature的优先候选。

因为很多shape信息与：

- H-high fraction；
- largest component；
- interface；
- radial burden

高度重叠。

---

# 十二、灰度离散化

habitat Original使用已冻结的主影像参数：

- muscle normalization；
- `[1,1,2] mm`；
- fixed binWidth约`0.248808`；
- PyRadiomics内部不重新normalize；
- 不重新resample。

不得根据H-low/H-high自身强度分布重新计算binWidth。

否则H-low与H-high特征无法处在同一离散化标尺。

---

# 十三、habitat-specific radiomics的ICC

必须使用A集双读者数据进行。

关键要求：

每一读者均根据自身ROI/影像经过相同的完整生境流程：

> reader-specific image/ROI
> → fixed technical pipeline
> → habitat assignment
> → habitat-specific radiomics。

对R_low与R_high分别计算ICC(2,1)。

预筛选标准沿用：

> ICC >0.75。

不得使用B ICC筛选。

---

# 十四、结构性单habitat病例

A393：

- dual-habitat：368；
- single-H-low：24；
- single-H-high：1。

因此：

- 24例不存在H-high；
- 1例不存在H-low。

对应habitat内部radiomics属于：

> structurally undefined。

不能填0。

---

# 十五、habitat-specific radiomics的结构性缺失处理

原始数据层：

```text
H_high_feature = NA
```

代表：

> H-high不存在。

不是：

> H-high纹理等于0。

主模型建议使用two-part strategy。

例如对H-high：

1. `H_high_fraction`等global habitat变量明确记录其存在和负荷；
2. H-high radiomics仅在H-high存在病例中定义；
3. training fold内部拟合imputation/scaling；
4. 对结构性缺失必须使用预设处理规则；
5. 不允许把结构性缺失和随机missing混为一类。

---

# 十六、dual-habitat sensitivity analysis

针对368例dual-habitat病例，额外进行：

> R_low和R_high均完整存在

的敏感性分析。

作用：

> 检验结构性缺失处理是否影响主要结论。

该分析只作为sensitivity，不替代A393主分析。

---

# 十七、whole-tumor radiomics W的重新定位

现有整瘤radiomics包含：

- Original；
- Wavelet；
- LoG。

既往相关队列中已经观察到：

> radiomics model < clinical model。

因此本研究不再把W作为主要方法开发方向。

但由于当前A393与既往队列不同：

> W仍需作为reference comparator重新评价。

其作用是回答：

> habitat decomposition是否提供了传统whole-tumor radiomics没有捕获的信息。

---

# 十八、Whole-tumor radiomics的处理原则

继续使用已有outcome-blind ICC候选池。

在nested CV训练折内部进行：

- near-zero variance filtering；
- correlation reduction；
- scaling；
- LASSO/Elastic Net Cox；
- hyperparameter tuning。

不得重新大规模探索预处理方案。

---

# 十九、正式模型层级

建议冻结以下模型体系。

---

## M0 — Clinical baseline

变量：

> C

回答：

> 标准治疗前临床/MRI预测能力是多少？

---

## M1 — Clinical + high-signal burden

变量：

> C + `H_high_fraction`

回答：

> 单纯知道高信号“多少”，是否增加预后信息？

---

## M2 — Clinical + global habitat

变量：

> C + G

回答：

> habitat空间组织是否超出单纯高信号负荷？

主要比较：

> M1 vs M2。

---

## M3L — Clinical + global habitat + H-low radiomics

变量：

> C + G + R_low

回答：

> H-low内部纹理是否在macro-habitat结构之外提供信息？

---

## M3H — Clinical + global habitat + H-high radiomics

变量：

> C + G + R_high

回答：

> H-high内部纹理是否在macro-habitat结构之外提供信息？

---

## M4 — Clinical + global habitat + dual-habitat radiomics

变量：

> C + G + R_low + R_high

回答：

> 两种habitat内部纹理联合是否提供最大增量信息？

---

## M5 — Clinical + whole-tumor radiomics

变量：

> C + W

定位：

> conventional whole-tumor radiomics comparator。

不是本研究重点开发模型。

---

# 二十、最重要的模型比较

本研究不要强调：

> 哪个模型AUC最高。

而应强调以下问题导向比较。

## Comparison A

`M0 → M1`

回答：

> high-signal burden本身有没有信息？

## Comparison B

`M1 → M2`

回答：

> 空间组织信息是否超出单纯burden？

## Comparison C

`M2 → M3L`

回答：

> H-low内部纹理是否增加信息？

## Comparison D

`M2 → M3H`

回答：

> H-high内部纹理是否增加信息？

## Comparison E

`M3L vs M3H`

探索：

> 哪一种habitat具有更稳定的增量价值？

该比较必须明确标记为：

> exploratory comparative analysis。

不能因为其中一个胜出就把另一个称为“无生物学意义”。

## Comparison F

`M2 → M4`

回答：

> 同时加入两种habitat纹理是否优于单纯macro-habitat？

## Comparison G

`M0 → M5`

回答：

> 既往whole-tumor radiomics表现有限的结论，在当前A393是否得到重复？

---

# 二十一、不建议把whole-tumor radiomics与所有新模型继续无限组合

目前不建议增加：

- C+W+R_low；
- C+W+R_high；
- C+W+G+R_low；
- C+W+G+R_high；
- C+W+G+R_low+R_high；

等大量组合。

原因：

> 会把一个清晰的habitat研究重新变成模型穷举。

如果W再次不能改善clinical model，则没有科学必要把其强制叠加到habitat模型。

因此whole-tumor W主要承担：

> comparator。

---

# 二十二、H-low vs H-high比较方式

不能直接比较：

> 两个模型表面C-index谁大一点。

必须在完全相同的outer CV splits中进行paired evaluation。

比较：

- ΔC-index；
- ΔUno C-index；
- Δ3-year AUC；
- Δ5-year AUC；
- Brier；
- calibration；
- feature-selection stability。

重点关注：

> H-low或H-high信号是否在不同repeat/fold中持续出现。

而不是一次性某折表现最好。

---

# 二十三、高维模型使用penalized Cox

对：

- R_low；
- R_high；
- W；

使用：

> Elastic Net Cox / LASSO Cox。

所有数据驱动步骤进入inner CV。

包括：

- imputation；
- scaling；
- variance filtering；
- correlation filtering；
- penalty selection；
- feature selection。

Clinical和固定低维G变量原则上：

> 强制保留或使用较低/零penalty。

Radiomics变量接受penalty。

---

# 二十四、fold-specific habitat是硬门禁

A集cross-validation中：

不能使用full-A global centers生成全部患者habitat后直接做CV。

每个outer fold必须：

```text
outer training
↓
training patients拟合K=2 centers/boundary
↓
training/validation分别使用training boundary生成habitat mask
↓
提取该fold对应R_low / R_high
↓
training fold内radiomics preprocessing/selection
↓
模型拟合
↓
validation prediction
```

因此：

> H-low/H-high radiomics也必须是fold-specific。

---

# 二十五、可以预缓存什么

以下属于patient-internal operation，可提前缓存：

- muscle-normalized image；
- tumor ROI；
- SLIC labels；
- 每个supervoxel mean。

不需要每个outer fold重新运行SLIC。

每fold仅重新：

> boundary assignment → H-low/H-high masks → habitat radiomics。

---

# 二十六、tumor volume sensitivity

此前outcome-blind分析已经发现：

> high_fraction与tumor volume存在相关。

因此预设：

`M2 + tumor_volume`

`M3L + tumor_volume`

`M3H + tumor_volume`

作为敏感性分析。

目的：

> 判断habitat及habitat-specific radiomics是否主要代理tumor burden。

不得根据该结果修改habitat定义。

---

# 二十七、A137严格敏感性分析

A137全部沿用主分析方法。

重点重复：

- M0；
- M1；
- M2；
- M3L；
- M3H。

由于A137样本减少：

M4高维双habitat模型可以仅作为补充，不作为必须稳定估计的主敏感性终点。

---

# 二十八、whole-tumor radiomics既往结果如何写入论文

不得写：

> “Whole-tumor radiomics had no prognostic value.”

建议写：

> Previous analyses in a broader rectal-cancer cohort suggested limited incremental predictive value of whole-tumor T2WI radiomics relative to clinical variables. Because that cohort was not restricted using the current high-signal eligibility definition, whole-tumor radiomics was retained as a reference comparator rather than treated as a definitive negative control.

---

# 二十九、核心生物学假说的最终表述

建议冻结为：

> **We hypothesized that whole-tumor radiomic averaging may obscure prognostically relevant heterogeneity by mixing spatially distinct T2 signal phenotypes. Accordingly, we evaluated whether prognostic information was preferentially carried by the H-low habitat, the H-high habitat, their macroscopic spatial organization, or combinations thereof, without prespecifying which habitat would be prognostically dominant.**

这一表述优于：

> “我们假设H-low决定预后”。

因为当前证据尚不足以支持方向性假设。

---

# 三十、数据隔离与第二阶段冻结

technical `freeze_lock.json`：

> 只解锁A outcome。

完成：

- nested A validation；
- H-low/H-high比较；
- strict sensitivity；
- volume sensitivity；

以后冻结：

`model_freeze_lock.json`

才允许读取B。

B不得用于决定：

> H-low还是H-high更重要。

---

# 三十一、A阶段结束后的决策原则

如果结果为：

### 情形A：R_low明显提供稳定增量，而R_high没有

结论：

> H-low可能是主要预后信息载体。

但必须报告：

> exploratory finding requiring external validation。

### 情形B：R_high更强

同样接受，不回头修改假说。

### 情形C：二者均有信息

重点讨论：

> 不同habitat可能代表不同风险维度。

### 情形D：单独均有限，但R_low+R_high组合有效

提示：

> prognostic information may reside in inter-habitat complementarity。

### 情形E：habitat radiomics仍无增量，但G有效

说明：

> 宏观空间结构比复杂纹理更稳健。

### 情形F：G、R_low、R_high全部没有增量

同样属于有效研究结果：

> 生境技术稳定性并不自动意味着预后预测价值。

不得因此重新调SLIC/K/0.1%。

---

# 三十二、具体工作流

>见202608组学分析\三十二、具体执行工作流：从formal PASS至A-only model freeze.md

---

# 三十三、最终原则

本阶段不是：

> 寻找哪个影像模型AUC最高。

而是回答：

> **在具有高T2信号成分的直肠癌中，将肿瘤分解为H-low和H-high之后，是否能够发现整瘤分析所掩盖的预后信息，以及这种信息主要位于何种生境层级。**

因此：

- Whole-tumor radiomics = reference comparator；
- Global habitat descriptors = macro-habitat representation；
- H-low radiomics = candidate intra-habitat representation；
- H-high radiomics = equally ranked candidate intra-habitat representation；
- H-low vs H-high = exploratory biological comparison；
- Clinical model = prediction baseline。
