# T2WI-HS-radiomics-analysis 已完成技术决策与冻结前验证归档

**建议文件名：**  
`archive/protocol_history/T2WI-HS-radiomics-analysis 已完成技术决策与冻结前验证归档.md`

**用途：**

本文档汇总截至A集formal bootstrap完成后，已经完成验证并原则上不再参与后续方法选择的技术事项。

这些内容从后续任务书中移出，避免已经关闭的问题反复进入方法开发流程。

---

# 一、当前研究队列定义

## 主高信号队列

预设最低影像学存在标准：

`high_fraction ≥0.1%`

A：

> 393例。

B：

> 107例。

该阈值定义为：

> `minimum imaging-presence criterion`

不定义为：

- biological cutoff；
- mucinous adenocarcinoma cutoff；
- prognostic cutoff；
- optimal cutoff；
- minimum habitat volume。

---

# 二、严格高信号敏感性队列

固定标准：

- high_fraction ≥1%；
- 26邻域最大LCC ≥128 mm³；
- 距肿瘤边界≥2 mm的高信号核心≥32 mm³。

A：

> 137例。

B：

> 23例。

A137保持为A393真子集。

该队列只承担：

> high-specificity sensitivity analysis。

不参与主阈值竞争。

---

# 三、0.1%阈值技术审计

结局盲态A筛选母队列：

> 530例。

0.1%通过：

> 393例。

与现有A393：

> identity difference=0。

---

# 四、0.1%的离散体素合理性

A筛选母队列中：

- 1个体素即可达到0.1%：0例；
- 2个：1例；
- 3–5个：5例；
- 6–10个：19例；
- >10个：505例。

因此：

> 95.3%的病例理论上需要超过10个等效高信号体素才能通过0.1%。

A393中：

- ≤2个高信号等效体素：1例；
- LCC≤2：0例。

因此0.1%不是由单像素噪声主导的入组规则。

---

# 五、threshold sweep结论

预设测试：

- >0；
- 0.05%；
- 0.10%；
- 0.25%；
- 0.50%；
- 1.00%。

通过例数：

- >0：498；
- 0.05%：438；
- 0.10%：393；
- 0.25%：313；
- 0.50%：251；
- 1.00%：200。

未发现：

> 0.25%或0.50%的自然数据断点。

因此：

`threshold_selection_performed=false`

0.1%保持不变。

---

# 六、0.1%技术混杂分解

结论：

> `NEUTRAL_WITH_TECHNICAL_CAUTION`

主要发现：

- high_fraction与tumor volume存在关系；
- sequence name原始关联较明显；
- 但加入sequence并未改善binary model的CV AUC；
- continuous模型CV R²仅增加约0.01；
- 主要sequence未出现决定性0%/100%通过模式；
- spacing存在一定影响，但小于tumor-volume association。

因此：

> 未发现足以推翻0.1%标准的纯技术证据。

---

# 七、影像预处理已固定

主分析：

> muscle-mean normalization。

重采样：

> `[1,1,2] mm`。

N4：

> 不启用。

PyRadiomics内部：

- 不重新normalize；
- 不重新resample。

---

# 八、SLIC参数已固定

主方法：

> 3D SLIC。

目标物理尺度：

> 4 mm。

在`[1,1,2] mm`图像上的SuperGridSize：

> `[4,4,2] voxels`

对应：

> `[4,4,4] mm`。

该尺度：

> 与FOV无关。

不再比较：

- 2D SLIC；
- 其他SLIC尺度；
- M2/M3。

---

# 九、跨病例聚类方法已固定

聚类：

> cross-case K-means。

K：

> 2。

初始化：

> k-means++。

`n_init`：

> 100。

`max_iter`：

> 300。

`tol`：

> 1e-4。

中心低→高固定：

- H-low；
- H-high。

---

# 十、患者等权策略已固定

对于患者i：

若其具有`n_i`个supervoxels，则每个supervoxel：

`w_ij = 1/n_i`

因此每患者：

`Σw_ij = 1`

避免：

> 大肿瘤或supervoxel较多病例主导global centers。

---

# 十一、全部有效supervoxels策略已固定

不再设置每病例：

> 2000 supervoxel cap。

主方法使用：

> all valid supervoxels。

---

# 十二、single-habitat定义已固定

合法状态：

- single-H-low；
- single-H-high；
- dual-habitat。

single habitat：

> 不是technical failure。

当前A393：

- dual=368；
- single-H-low=24；
- single-H-high=1。

---

# 十三、结构零与结构缺失规则已固定

可以结构性取0的变量包括：

- H-high fraction；
- interface density；
- H-high connected-component descriptors；
- radial burden等。

对应habitat不存在时：

> habitat-internal radiomics/texture保持undefined。

不得填0。

---

# 十四、低维global habitat descriptor已固定

主预测候选块固定6项：

1. `H_high_fraction`
2. `sv_median_minus_boundary`
3. `sv_IQR`
4. `interface_density`
5. `H_high_largest_component_tumor_fraction`
6. `H_high_radial_burden`

描述性/次要：

- `habitat_entropy`
- `H_high_component_density`

---

# 十五、formal bootstrap设计已固定

模式：

- smoke=20；
- preflight=200；
- formal=1000。

患者层面resampling。

每replicate：

`seed = 12345 + bootstrap_index`

支持：

- checkpoint；
- resume；
- mode-specific output directories。

只有：

> formal=1000

允许进入freeze gate。

---

# 十六、preflight 200结果

结果：

> CLEAR PASS。

主要数值：

- nondegenerate=1.000；
- boundary median≈2.81047；
- assignment median≈0.9862；
- assignment P5≈0.9591；
- structural stability≈1.000。

该结果仅作为正式运行前技术预审。

---

# 十七、formal 1000结果

最终：

> **FORMAL PASS**

1000/1000成功。

参考中心：

- H-low=2.101717；
- H-high=3.519630。

参考boundary：

> 2.810674。

bootstrap boundary：

- P2.5=2.708194；
- median=2.811491；
- P97.5=2.924580。

reference center distance：

> 1.417913。

95% interval width / center distance：

> 0.152609。

---

# 十八、formal病例层稳定性

assignment stability：

- median=0.986711；
- P5=0.960980。

structural-state stability：

- median=1.000；
- P5=0.997。

H-high fraction：

- median bootstrap change=0；
- bootstrap SD median=0.022371。

因此：

> global habitat definition对患者组成扰动高度稳定。

---

# 十九、preflight与formal一致

preflight 200：

> boundary median=2.810473。

formal 1000：

> 2.811491。

assignment median：

> 0.986223 → 0.986711。

P5：

> 0.959091 → 0.960980。

没有发现：

> repeat增加后的系统性漂移。

---

# 二十、technical bootstrap结论的解释边界

formal bootstrap证明：

> habitat construction具有技术稳定性。

它不证明：

- habitat一定预测DFS；
- H-low优于H-high；
- H-high优于H-low；
- B集泛化一定成功。

上述问题留给：

> outcome analysis和external validation。

---

# 二十一、whole-tumor radiomics既往经验

此前在一个更宽泛的直肠癌队列中已经完成whole-tumor radiomics分析。

结果提示：

> whole-tumor radiomics预测性能低于clinical model。

但该历史队列：

> 未按照当前0.1%高信号eligibility限制。

因此该结果在当前项目中的正式解释为：

> **prior motivating evidence**

而不是：

> current A393 definitive negative result。

它支持开展habitat decomposition，但不允许直接跳过当前A393中的whole-tumor comparator。

---

# 二十二、当前不能归档为已确定的事项

以下问题仍然开放，不能列入“固定结论”。

## 未确定1

H-low是否携带主要预后信息。

## 未确定2

H-high是否携带主要预后信息。

## 未确定3

H-low/H-high内部Original radiomics是否具有增量价值。

## 未确定4

global habitat descriptors是否预测DFS。

## 未确定5

当前A393中的whole-tumor radiomics是否再次低于clinical model。

## 未确定6

最终预测模型组成。

## 未确定7

B外部验证性能。

这些均属于后续任务书范围。

---

# 二十三、数据隔离原则已固定

technical phase：

> outcome blind。

第一阶段：

`freeze_lock.json`

只允许：

> A outcome unlock。

仍禁止：

> B data access。

第二阶段：

`model_freeze_lock.json`

生成后：

> B首次解锁。

B只能：

> 单次外部验证。

---

# 二十四、A内部验证的防泄漏原则已固定

任何outer validation patient不得参与：

- global centers；
- boundary；
- imputation；
- scaling；
- variance filtering；
- correlation reduction；
- radiomics selection；
- penalty tuning。

A内部CV使用：

> fold-specific global centers与habitat masks。

---

# 二十五、归档结论

截至formal bootstrap完成，本项目已经完成：

> 队列定义  
> → eligibility技术审计  
> → normalization选择  
> → 4 mm SLIC  
> → patient-balanced K=2  
> → structural state规则  
> → global habitat descriptors  
> → formal 1000稳定性验证。

这些技术问题：

> **原则上关闭，不再因后续DFS结果重新开启。**

项目正式进入下一阶段：

> **探索H-low、H-high及其空间/纹理表型的预后信息。**

后续研究可以改变的：

> 是“我们发现什么”。

不能因为结果不理想重新改变的：

> 是“我们如何定义habitat”。