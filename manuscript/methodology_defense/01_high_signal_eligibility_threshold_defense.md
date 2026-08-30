# 0.1%高信号入组阈值的方法学论证与冻结依据

**建议文件名：** `01_high_signal_eligibility_threshold_defense.md`  
**适用研究：** T2WI-HS-radiomics-analysis  
**状态：** outcome-blind methodology defense / pre-outcome freeze  
**最终决定：** 保留预设的`high_fraction ≥0.1%`作为最低影像学存在阈值，不提高至0.25%、0.5%或1%，也不取消阈值。  
**解释边界：** 0.1%不是组织学黏液比例阈值、不是预后cutoff，也不要求原始高信号在4 mm SLIC尺度上形成独立H-high生境。

---

# 1. 需要解决的方法学问题

本研究拟在治疗前T2WI上具有可识别瘤内高信号成分的直肠癌患者中开展跨病例生境分析。因此，在进行任何结局分析之前，需要预先回答：

1. 如何定义“存在可识别T2高信号成分”；
2. 为什么主分析采用`high_fraction ≥0.1%`；
3. 该阈值是否只是由单个或少量异常亮体素驱动；
4. 是否存在更合理的0.25%、0.5%或1%自然分界；
5. 0.1%是否受到肿瘤大小、空间分辨率或序列差异的严重技术驱动；
6. 接近0.1%的病例是否会造成后续4 mm SLIC/K-means生境分析不稳定；
7. 是否应取消二元入组阈值，将所有技术合格直肠癌直接纳入；
8. 在不查看DFS、OS、CSS及B集数据的条件下，现有技术证据是否足以冻结该定义。

本报告汇总结局盲态下完成的阈值审计、技术混杂分解、患者层面bootstrap以及双读者技术评价，并据此记录最终冻结理由。

---

# 2. 阈值首先是“研究对象定义”，而不是预后cutoff

本研究中的0.1%应定义为：

> **minimum imaging-presence criterion，即最低影像学存在标准。**

它回答的是：

> 肿瘤内是否存在足够数量、达到病例内高信号参照水平的T2高信号体素，使患者可以被合理归入“具有可识别瘤内T2高信号成分”的研究人群。

它不回答：

- 多少黏液才能诊断黏液性腺癌；
- 多少高信号代表侵袭性生物学；
- 什么比例可以最佳预测DFS；
- 多少原始高信号一定能在4 mm尺度形成独立生境。

因此，0.1%不是一个需要通过ROC、C-index、HR或P值寻找的“最佳cutoff”。

从方法学上，本研究故意避免依据结局优化eligibility threshold，以防止：

> 入组阈值选择 → 同一数据集预后分析

形成数据驱动的循环选择和乐观偏倚。

---

# 3. 文献支持“检测什么”，而不是直接规定“0.1%”

## 3.1 T2高信号具有合理的影像生物学基础

普通直肠腺癌在T2WI上通常表现为中等信号，其信号一般低于高信号的直肠系膜/瘤周脂肪；当肿瘤含有较多富水或黏液成分时，T2信号明显升高。

关于黏液性直肠癌的MRI文献通常将高信号描述为：

> 与mesorectal fat相似或更高的T2信号。

因此，以同一患者的瘤周脂肪作为病例内参照具有明确的影像学依据。

该构造的优势在于避免把MRI原始灰度值视为跨患者、跨扫描条件可直接比较的绝对量。

## 3.2 影像上的“存在黏液”不等同于病理上的“黏液性腺癌”

病理学上，经典黏液性腺癌通常要求超过50%的细胞外黏液。

但本研究并不试图通过MRI重建这一组织学分类。

近期SAR直肠癌MRI术语共识也指出，影像上很难精确量化组织学意义上的黏液百分比，因此更适合描述为：

- no mucin；
- some mucin；
- mostly mucin。

既往研究亦分别使用：

- `<50% vs ≥50% mucin`；
- `no mucin vs any mucin`

评价MRI上的黏液性成分。

因此，研究“任何可检测的高T2成分”本身是合理的影像研究问题，并不要求患者首先达到经典黏液性腺癌的50%标准。

## 3.3 文献不能证明0.1%是天然生物学分界

现有文献可以支持：

- T2高信号与黏液/富水成分的关系；
- 使用瘤周脂肪作为高信号参照；
- 研究低于50%的黏液性成分；
- 将“有无黏液”和“黏液负荷”分开处理。

但并不存在公认证据证明：

> `0.1%`是组织学黏液存在、真实病灶与噪声之间的天然生物学临界点。

因此，本研究不声称0.1%是“literature-established biological cutoff”。

它的合理性必须由：

> 文献构造依据 + 预设研究目的 + 本队列outcome-blind技术验证

共同建立。

---

# 4. A集结局盲态筛选母队列

技术审计在不读取任何结局、不访问B集的条件下进行。

A集筛选母队列：

> **530例R1病例**

预设0.1%标准通过：

> **393/530，74.2%**

重新计算得到的A393与此前post-SLIC分析使用的A393：

> **symmetric difference = 0**

因此后续阈值审计没有改变已经完成的A集技术分析患者身份。

严格高信号空间敏感性队列：

> **A137**

保持为A393真子集，并且不参与主阈值竞争。

---

# 5. 0.1%并非“一个亮体素即可入组”

这是最直接的测量学质疑之一。

对于每个患者，达到0.1%需要的最低等效高信号体素数定义为：

`ceil(0.001 × tumor_voxels)`

在530例A筛选母队列中：

|达到0.1%所需的最低等效高信号体素数|病例数|比例|
|---:|---:|---:|
|1|0|0.0%|
|2|1|0.2%|
|3–5|5|0.9%|
|6–10|19|3.6%|
|>10|505|95.3%|

因此：

> **95.3%的患者理论上需要超过10个等效高信号体素才能达到0.1%。**

没有病例能够仅依靠1个等效体素达到阈值。

在实际通过0.1%的A393中：

- 等效高信号体素≤2：1例（0.3%）；
- ≤5：13例（3.3%）；
- LCC=1：0例；
- LCC≤2：0例。

因此，现有数据基本排除了：

> “0.1%主要由随机单像素高信号驱动”

这一解释。

---

# 6. 预设threshold sweep没有发现新的自然分界

在不进行阈值优化的前提下，预先固定考察：

- >0；
- 0.05%；
- 0.10%；
- 0.25%；
- 0.50%；
- 1.00%。

结果：

|阈值|A通过例数|保留率|
|---:|---:|---:|
|>0|498|94.0%|
|0.05%|438|82.6%|
|**0.10%**|**393**|**74.2%**|
|0.25%|313|59.1%|
|0.50%|251|47.4%|
|1.00%|200|37.7%|

病例数随阈值上升呈连续、单调下降。

未观察到：

> 0.25%、0.5%或其他预设位置存在明显自然断点。

因此，数据不支持将0.1%事后替换为0.25%或0.5%。

如果在看到这些结果以后选择一个“看起来更漂亮”的新阈值，反而会产生新的数据驱动threshold-selection问题。

---

# 7. 近0.1%病例具有真实的多体素信号，但空间负荷较小

最需要审查的区间为：

> **0.10–<0.25%**

共80例。

其典型特征为：

- 高信号等效体素中位数：13.29；
- 高信号体积中位数：26.59 mm³；
- 最大LCC体素中位数：15.5；
- LCC体积中位数：5.48 mm³；
- 2 mm内部核心体积中位数：3.33 mm³。

在这80例中：

- 等效高信号体素≤2：1例；
- ≤5：12例；
- LCC=1：0例；
- LCC≤2：0例。

因此，接近0.1%的患者总体并不是由单体素或双体素异常点组成。

另一方面：

- LCC比例中位数较低；
- 连通成分较分散；
- 内部核心体积较小。

这提示0.1–0.25%的病例更适合被解释为：

> **低负荷、空间较分散的高T2信号表型**

而不是：

> 已经形成大体积、高连通性的独立影像亚区。

这一发现与0.1%“最低存在阈值”的定位一致。

---

# 8. 原始高信号筛选与4 mm SLIC生境属于不同空间尺度

近阈值病例在4 mm SLIC后的高信号保留明显降低：

|原始筛选区间|post-SLIC高信号比例中位数|原始高信号保留召回率中位数|
|---|---:|---:|
|0.10–<0.25%|0.0000|0.0000|
|0.25–<0.50%|0.0000|0.0142|
|0.50–<1.00%|0.0007|0.0538|
|≥1.00%|0.0174|0.2617|

这一结果最初被视为潜在警示，但进一步分析后应解释为：

> **screening scale与habitat scale不同。**

筛选阶段回答：

> 原始肿瘤体素中是否存在达到瘤周参照强度的高T2信号。

生境阶段回答：

> 在`[1,1,2] mm`重采样和4 mm三维SLIC空间聚合后，哪些局部区域在全A跨病例K=2框架下属于H-high表型。

4 mm超体素平均会降低微小、分散高信号的局部极值，这是空间聚合本身预期产生的行为。

因此：

> `post-SLIC retention = 0`

不能直接解释为：

> “原始0.1%信号是错误的”或“病例不应入组”。

如果要求0.1%的信号必须在4 mm SLIC后保持独立H-high，则实际上是在用下游生境定义反向规定上游eligibility，造成研究构造循环。

---

# 9. 提高到0.25%或0.5%并不能解决post-SLIC稀释

如果近0.1%的低保留是提高阈值的充分理由，则提高阈值后应明显改善该现象。

实际并非如此。

0.25–0.50%病例：

> post/pre中位比例仍仅0.0181。

0.50–1.00%病例：

> 中位保留召回率仍仅约5%。

明显增加主要发生在≥1%病例。

因此：

> 将主阈值从0.1%提高到0.25%或0.5%，并不能实质解决空间尺度差异。

直接改成≥1%则会把A主分析集从393例降低到200例，并实质改变研究对象，使主分析从“任何可检测高T2成分”转变为“较高负荷高T2成分”。

而本研究已经预设A137承担更高特异性的空间敏感性评价，没有必要用提高主阈值重复完成同一任务。

---

# 10. 患者层面preflight证明近阈值病例没有破坏生境稳定性

200次患者层面bootstrap preflight已经完成。

全A393：

- 非退化率：1.000；
- assignment stability median约0.986；
- assignment stability P5约0.959；
- structural-state stability median=1.000；
- structural-state stability P5=1.000。

更重要的是，按原始high_fraction分层后：

|筛选区间|assignment stability median|assignment stability P5|structural-state stability|
|---|---:|---:|---:|
|0.10–<0.25%|0.986|0.957|1.000|
|0.25–<0.50%|0.985|0.952|1.000|
|0.50–<1.00%|0.985|0.963|1.000|
|≥1.00%|0.986|0.959|1.000|
|A393总体|0.986|0.959|1.000|

因此：

> **最低负荷的0.10–<0.25%患者，其下游生境分配稳定性与≥1%患者几乎相同。**

这直接证明：

> 原始高信号在4 mm尺度被部分平均掉，并不等于这些患者造成K-means或病例生境表型不稳定。

这是保留0.1%的重要内部技术证据。

---

# 11. 肿瘤体积依赖确实存在

技术审计发现：

- high_fraction vs tumor volume：Spearman rho=0.396；
- 0.1% pass/fail的tumor-volume SMD=0.601。

按肿瘤体积四分位数：

- Q1：57.9%通过；
- Q2：65.9%；
- Q3：81.1%；
- Q4：91.7%。

进一步技术混杂模型在同时调整spacing和sequence之后仍显示：

### 二分类0.1%通过模型

- standardized coefficient of `log(tumor_volume)` = **0.921**；
- spacing_x = −0.243；
- spacing_z = −0.204。

### 连续high_fraction模型

`log(tumor_volume)`标准化系数：

> **1.433**

因此，high_fraction与肿瘤体积之间存在明确关系。

这一点不应被忽略。

---

# 12. 但体积依赖不能等同于“0.1%阈值错误”

至少存在两种可能机制：

## 12.1 生物学机制

较大的肿瘤可能具有：

- 更复杂的空间异质性；
- 更多富水区域；
- 黏液成分；
- 坏死或液化；
- 更复杂的组织成分。

既往MRI文献也报道黏液池可与较大的直肠肿瘤相关。

## 12.2 测量学机制

MRI量化和radiomics本身可能受到：

- ROI大小；
- voxel number；
- image resolution；
- partial-volume effect

影响。

已有MRI/radiomics研究明确表明，部分影像特征具有tumor-volume dependence，因此体积混杂应被评价和报告。

现有outcome-blind技术数据无法、也不应该强行判断上述两类机制各占多少。

本次技术审计需要回答的只是：

> 是否存在证据表明0.1%主要是由明显的技术伪影决定。

目前没有这种证据。

---

# 13. “小肿瘤更容易因为少数体素越过0.1%”的解释与实际数据相反

如果0.1%主要受到小ROI离散效应驱动，则预期：

> 小肿瘤因为所需绝对体素较少，更容易达到阈值。

实际观察相反：

> 肿瘤越大，通过0.1%的比例越高。

同时95.3%的病例理论上需要>10个等效高信号体素才能达到0.1%。

因此：

> 肿瘤体积依赖不能简单归因于“小肿瘤只需要1–2个噪声体素即可通过”。

这一最直接的数学伪影解释已被现有数据基本排除。

---

# 14. 原始序列差异不构成决定性技术驱动

初始描述性分析中：

> sequence name与0.1%通过状态存在较明显的Cramér's V。

因此进一步建立结局盲态技术模型：

### 模型1

`log(tumor_volume) + spacing_x + spacing_z`

### 模型2

`log(tumor_volume) + spacing_x + spacing_z + sequence_name`

结果：

## 二分类0.1%通过状态

- 不加sequence：CV AUC=0.742；
- 加sequence：CV AUC=0.738；
- ΔAUC=−0.004。

## 连续high_fraction

- 不加sequence：CV R²=0.194；
- 加sequence：CV R²=0.204；
- ΔR²=+0.010。

因此：

> **原始sequence name没有提供稳定的额外交叉验证解释能力。**

74个序列水平中存在许多小样本类别。

限制在：

### n≥10

18个序列，覆盖359例；

### n≥20

8个主要序列，覆盖233例。

n≥20的主要序列：

- 没有0%通过水平；
- 没有100%通过水平；
- 调整后的通过概率范围为0.762–0.943。

因此没有证据显示：

> 某一主要sequence几乎决定患者能否通过0.1%。

需要保留的限定是：

> sequence影响并非被证明完全不存在，只是没有形成稳定、决定性的独立解释能力。

---

# 15. spacing因素存在，但效应明显低于肿瘤体积

在控制肿瘤体积和sequence后：

### Binary main-pass模型

- spacing_x coefficient = −0.243；
- spacing_z = −0.204。

### 连续high_fraction模型

- spacing_x = −0.083；
- spacing_z = −0.356。

因此spacing仍可能贡献一定测量差异，但其效应：

- 明显小于tumor volume；
- 随sequence调整发生变化；
- 不能单独解释为0.1%阈值的系统性偏倚。

这类残余技术依赖应在研究限制中报告，而不是通过不断调整eligibility cutoff试图消除。

---

# 16. R1/R2一致性不支持取消或修改0.1%

现有A集21例R1/R2成对数据中：

0.1%：

- overall agreement = 85.7%；
- Cohen κ = 0.351。

κ较低。

但病例类别高度不平衡，并且样本量只有21，因此κ估计本身不稳定。

连续high_fraction的一致性则为：

- Spearman rho = **0.891**；
- ICC(2,1) = **0.885**。

说明high_fraction作为连续影像表型具有较高的读者间一致性。

因此目前最合理的结论是：

> 双读者样本不足以精确证明0.1%二分类阈值具有高度一致性，但也不存在足够证据据此推翻阈值；连续high_fraction本身具有良好的重复性。

不能因为0.25%或0.5%的κ在21例中略高，就事后把主标准修改为对应阈值。

---

# 17. 为什么不取消阈值、直接纳入A530

取消0.1%并不是简单的统计改进，而是研究estimand的改变。

当前研究目标人群是：

> **治疗前MRI上具有可识别瘤内T2高信号成分的直肠癌患者。**

A530中：

- 32例完全不存在supra-reference高信号；
- 另外105例存在>0但<0.1%的极低负荷信号。

如果全部纳入，研究问题将从：

> “具有可识别高T2成分的直肠癌中的生境异质性”

改变为：

> “所有符合其他影像条件的直肠癌中的T2异质性”。

这不是eligibility阈值的小修正，而是目标人群的重新定义。

由于当前技术证据未发现足以推翻0.1%的严重测量缺陷，因此没有理由在结局解盲前改变研究estimand。

---

# 18. A137承担不同而互补的方法学角色

严格高信号敏感性队列预设为：

- high_fraction ≥1%；
- 最大26邻域高信号连通成分体积≥128 mm³；
- 距肿瘤边界至少2 mm的高信号体积≥32 mm³。

A集共137例。

这一队列的作用不是与0.1%竞争“哪个阈值最好”。

两者回答不同问题：

## A393

**High-sensitivity / minimum-presence cohort**

回答：

> 具有足够可检测T2高信号证据的患者中，生境表型是否具有临床意义？

## A137

**High-specificity / spatially substantive cohort**

回答：

> 当高信号具有更明确的负荷、空间连通性和内部核心时，主要结论是否仍然成立？

因此A137是针对0.1%宽松定义最重要的预设敏感性分析。

如果未来A393和A137中的主要结论方向一致，将显著增强结果并非由近0.1%低负荷患者驱动的可信度。

---

# 19. 为什么最终不提高阈值

提高到0.25%或0.5%缺少三个必要条件：

## 19.1 无文献公认分界

没有证据证明0.25%或0.5%具有特殊的组织学意义。

## 19.2 无数据自然断点

threshold sweep呈平滑、连续下降。

## 19.3 无明确技术优势

0.25–0.5%的raw-high signal经过4 mm SLIC后仍然大多被稀释。

因此提高主阈值：

> 会减少样本、改变研究对象，却不能解决最初所担心的空间尺度问题。

在查看A集技术结果以后再选择更高cutoff，还会引入新的data-dependent threshold selection。

---

# 20. 为什么最终不取消阈值

取消阈值同样缺少充分理由：

1. 当前研究目标本来就限定于“具有可识别瘤内T2高信号成分”的病例；
2. 0.1%不是单像素噪声阈值；
3. near-threshold患者并未降低下游K-means/bootstrap稳定性；
4. sequence没有形成决定性技术驱动；
5. 体积依赖存在，但无法被证明是纯技术伪影；
6. A137已经提供更严格定义下的敏感性框架。

因此取消阈值带来的estimand改变大于其能够解决的技术问题。

---

# 21. 最终技术判断

本研究将0.1%阈值的结局盲态技术审计最终定为：

> **NEUTRAL_WITH_TECHNICAL_CAUTION**

含义为：

> 总体可接受，可以冻结；但存在需要在论文中透明报告并在后续敏感性分析中处理的技术依赖。

该结论不是：

> 0.1%已经被证明是最佳阈值。

而是：

> 在不读取结局和B集的前提下，没有发现足以推翻预设0.1%最低影像存在标准的技术证据，也没有发现足以支持替换为其他阈值的自然分界或明确测量学优势。

---

# 22. 冻结决定

正式结局分析前冻结如下：

## 主eligibility标准

`high_fraction ≥0.001`

即：

> `≥0.1%`

## 方法学角色

`minimum_imaging_presence`

## 明确不宣称

- biological mucin cutoff；
- histopathologic MAC threshold；
- prognostic cutoff；
- optimal threshold；
- minimum independent habitat volume；
- guarantee of post-SLIC H-high preservation。

## 严格敏感性队列

A137保持原定义，不重新优化。

## 阈值选择状态

`threshold_selection_performed=false`

## 数据边界

`outcome_columns_read=false`

`B_data_read=false`

---

# 23. 对后续预后分析的预设影响

由于技术审计发现high_fraction与肿瘤体积存在明显相关性，因此后续正式预后分析必须区分：

> habitat是否提供独立于tumor burden的信息。

建议在首次读取DFS之前预先记录：

### 主模型

保持原有预设临床模型不变。

### 次要volume-adjusted sensitivity analysis

在主模型框架基础上增加：

> MRI tumor volume

用于评价主要habitat指标的效应量、方向和模型增益在控制肿瘤体积以后是否保持。

该分析仅作为敏感性评价，不用于重新选择habitat feature或改变主模型定义。

---

# 24. 论文中推荐的核心表述

## Methods

建议表述：

> The 0.1% threshold was prespecified as a minimum imaging-presence criterion rather than a biological, histopathologic, or prognostic cutoff. Its purpose was to exclude tumors with absent or only negligible supra-reference T2 signal while preserving the continuum of high-signal burden for subsequent quantitative habitat analysis.

并进一步说明：

> Before outcome analysis, the threshold underwent an outcome-blind technical audit including voxel-count discretization, prespecified threshold perturbation, spatial connectivity assessment, acquisition-factor assessment, reader reproducibility, and linkage with patient-level habitat bootstrap stability. No outcome or validation-set information was used to modify the threshold.

## Discussion

建议表述：

> Outcome-blind technical auditing did not identify a natural alternative cutoff or evidence that the prespecified 0.1% criterion was predominantly driven by isolated supra-reference voxels. Although low-burden supra-reference signal was frequently attenuated after 4-mm supervoxel averaging, these cases showed habitat assignment stability comparable with tumors containing larger high-signal fractions. This distinction reflects the different roles of the screening and habitat scales: the former identifies minimal imaging evidence of the phenotype, whereas the latter captures spatially supported cross-patient signal patterns.

关于体积依赖：

> High-signal fraction was associated with tumor volume even after adjustment for image spacing and sequence category. Because this association may reflect both true biological heterogeneity and known size-related effects in quantitative imaging, it was treated as a methodological consideration rather than as evidence for post hoc threshold modification.

关于严格敏感性队列：

> A separately prespecified, spatially constrained high-signal cohort was therefore retained as a high-specificity sensitivity analysis rather than used to redefine the primary eligibility threshold.

---

# 25. 审稿人潜在质疑与简明回答

## Q1. Why 0.1%?

**回答：**

0.1%不是生物学最佳cutoff，而是预设的minimum-presence threshold。技术审计显示其并非由单体素异常驱动，且不存在支持0.25%或0.5%替代它的自然数据分界。

## Q2. Isn't 0.1% too low?

**回答：**

95.3%的筛选母队列患者达到该阈值理论上需要超过10个等效高信号体素；A393中没有LCC≤2体素的病例，因此该阈值并不等价于“一个亮点即入组”。

## Q3. Most low-burden signal disappears after SLIC. Does this invalidate inclusion?

**回答：**

不。原始信号筛选和4 mm SLIC承担不同角色。前者检测最低影像存在证据，后者提取具有4 mm空间支持的跨病例habitat。更重要的是，0.10–<0.25%患者的患者层面bootstrap分配稳定性与≥1%病例基本相同。

## Q4. Why not use 0.25% or 0.5%?

**回答：**

没有文献金标准、没有自然数据断点，而且提高到这些水平仍不能消除post-SLIC信号稀释。事后选择其中一个反而会引入data-driven threshold selection。

## Q5. Why not simply include all tumors?

**回答：**

因为这会改变研究目标人群。当前研究明确研究具有可识别瘤内高T2信号成分的患者，而不是所有直肠癌。

## Q6. Doesn't tumor-volume dependency indicate confounding?

**回答：**

它提示需要谨慎解释和volume-adjusted sensitivity analysis，但不能证明是纯技术偏倚。该关系在调整sequence和spacing后仍存在，并可能同时包含真实肿瘤异质性和已知的影像体积依赖。

## Q7. What protects against an arbitrary liberal threshold?

**回答：**

除了outcome-blind阈值审计外，本研究另有预设A137高特异性空间敏感性队列，通过负荷、连通性和内部核心要求评价主要结论对更严格高信号定义的稳健性。

---

# 26. 建议引用的文献方向

最终论文参考文献中建议至少覆盖以下几类：

1. **SAR Rectal Cancer Lexicon 2023**
   - 支持影像上难以精确复制组织学黏液百分比；
   - 支持no/some/mostly mucin的影像描述框架。

2. **Mucinous Rectal Cancer: Concepts and Imaging Challenges**
   - 支持黏液在T2WI上的高信号；
   - 支持高信号与mesorectal fat相似或更亮的定义；
   - 讨论MRI黏液检测及潜在假阳性来源。

3. **MRI of rectal cancer—relevant anatomy and staging key points**
   - 支持普通直肠癌、黏液性直肠癌及mesorectal-fat signal关系。

4. **Mucin Quantity on MRI and Outcomes Following Total Neoadjuvant Therapy**
   - 支持MRI研究中`no vs any mucin`与`<50% vs ≥50%`可以作为不同分类问题。

5. **ROI size / tumor-volume dependency radiomics literature**
   - 支持肿瘤体积、图像分辨率和ROI大小可以影响定量影像特征；
   - 支持在后续预后模型中对volume dependency进行敏感性评价，而不是简单删除所有与体积相关的影像表型。

---

# 27. 最终结论

在正式读取结局及B集之前完成的全部技术证据共同支持以下决定：

> **继续保留`high_fraction ≥0.1%`作为主分析队列的最低影像学存在标准。**

理由不是0.1%被证明为“最佳阈值”，而是：

1. 其影像构造具有明确文献基础；
2. 它没有被单体素或极少量孤立信号主导；
3. 预设threshold sweep没有发现新的自然分界；
4. 提高到0.25%或0.5%不能解决4 mm尺度信号稀释；
5. near-threshold病例没有降低患者层面生境稳定性；
6. 原始sequence name没有形成稳定的独立交叉验证解释增益；
7. 肿瘤体积依赖虽存在，但不能被归结为阈值错误，应通过透明报告和volume-adjusted sensitivity analysis处理；
8. 取消阈值会改变研究目标人群；
9. A137已经为更严格的空间高信号定义提供独立、预设的敏感性评价框架；
10. 整个阈值论证过程均保持`threshold_selection_performed=false`、`outcome_columns_read=false`及`B_data_read=false`。

因此，0.1%阈值的冻结状态应记录为：

> **Methodologically acceptable with technical caution; frozen as a minimum imaging-presence criterion before outcome analysis.**