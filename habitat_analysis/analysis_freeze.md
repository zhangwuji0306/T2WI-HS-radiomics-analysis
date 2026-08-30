# Analysis Freeze

## 当前主方法

- 主方法为M1：肌肉均值归一化、`[1,1,2] mm`重采样、4 mm三维SLIC、保留全部与肿瘤ROI相交的有效超体素、每例总权重固定为1的跨病例K-means K=2。
- 不设置每例超体素拟合上限；不使用病例内K-means、Z-score或M2/M3作为主方法。
- 聚类中心按低到高固定为`H-low`和`H-high`；病例内K-means仅用于local-global机制诊断。

## 队列与终点

- 宽松主分析集：A=393，B=107。
- 严格高信号敏感性集：A=137，B=23。
- 主终点：DFS；主要评价时点：3年和5年。
- 建模读者：R1。
- 临床模型固定9个变量；性别、length和distance不进入任何模型。

## 图像与生境参数

- 肌肉均值归一化；重采样间距`[1,1,2] mm`；不启用N4。
- 三维SLIC目标尺度4 mm，最大迭代5，空间权重10，连通性约束开启，单工作线程。
- `SuperGridSize`按`round(target_scale_mm / spacing_mm_xyz)`从物理尺度换算为体素数；当前固定为体素网格`[4,4,2]`，对应实际物理尺度`[4,4,4] mm`，与视野大小无关。
- 跨病例K-means，K=2，k-means++，`n_init=100`，`max_iter=300`，`tol=1e-4`，随机种子12345。
- `fit_supervoxels=all`；病例 (i) 的超体素权重为 (w_{ij}=1/n_i)，`case_weighting=1/n_i`，每例权重和为1。
- 聚类中心只在对应训练数据中拟合；标签按中心从低到高固定为`H-low`和`H-high`。
- bootstrap为患者层面、结局盲态技术稳定性评估，模式固定为`smoke=20`、`preflight=200`、`formal=1000`；三种模式分别写入`output/bootstrap_stability_A_post_slic_fix/smoke/`、`preflight/`和`formal/`，每个重复使用`12345+bootstrap_index`作为种子并支持断点续跑。
- `smoke`仅用于流程核验，`preflight`仅用于正式运行前估时和稳定性预审；二者均不得解锁冻结。只有完整的`formal=1000`结果及其余门禁全部通过后，才可生成`freeze_lock.json`。
- 当前状态：A集`preflight=200`已完成，全部拟合成功，操作性判定为`CLEAR PASS`；尚未执行`formal=1000`，未生成`freeze_lock.json`。
- 结局盲态0.1%阈值技术合理性审计及补充技术混杂分解已完成：A筛选母队列530例，重算A393身份一致，A137为A393真子集；阈值扫描、近阈值形态、post-SLIC保留、技术因素、R1/R2一致性、既有200次preflight及体积/spacing/序列分解均已核验。补充分解显示原始序列名没有稳定的交叉验证增益，主要序列不存在近乎决定通过/失败的水平，但肿瘤体积依赖仍存在；综合判断为`NEUTRAL_WITH_TECHNICAL_CAUTION`。该分析不改变0.1%主标准、不执行阈值优化，formal及结局分析仍未执行。
- 生境Original特征固定箱宽`0.248808`；关闭PyRadiomics内部重采样和归一化。

## 技术失败与结构状态

空生境是结构性全局表型状态，不是技术失败。每例必须标记为`single-H-low`、`single-H-high`或`dual-habitat`。缺失表型的存在指示、体积分数、生境熵、界面密度及H-high连通成分描述可按结构规则取0；相应表型内纹理在不存在时保持未定义，不填0。

硬技术失败按唯一病例合并计数，包括图像读取、几何、归一化、SLIC、非有限值、聚类数值和未分配体素错误。病例内K<2或病例内唯一均值<2仅标记为local-global诊断不可用，不作为主方法失败。联合技术失败率定义为失败病例数除以本批次全部目标病例数。

- 联合失败率＜5%：通过；逐例记录失败类型和原因，将失败病例从该阶段主分析队列剔除后继续。
- 联合失败率≥5%：停止该阶段并提交失败清单。
- A=393最多允许19例失败；B=107最多允许5例失败。
- 结构性单生境不作为病例排除条件；硬技术失败不填补，且不根据结局决定排除。
- H1–H5的主要比较使用同一技术成功病例集，并报告目标数、成功数、排除数及预测覆盖率。
- 技术排除清单在结局不可见的条件下冻结；只有冻结条件全部满足后，才可纳入A集临床与DFS。

## 主特征字典候选

- `H_high_fraction`、`habitat_entropy`、`interface_density`、`H_high_largest_component_tumor_fraction`、`H_high_component_density`、`H_high_radial_burden`、`sv_median_minus_boundary`和`sv_IQR`构成全队列主要低维候选。
- `H_low_fraction=1-H_high_fraction`不与`H_high_fraction`同时进入模型；状态、体素数、P05/P95及中心距离作为描述和质控字段。
- H-low/H-high内影像组学为条件性次要分析，仅在相应表型存在且特征有限时定义。

## 数据隔离

- 技术干跑不得读取结局或临床变量。
- A集技术队列由影像清单、设备映射和高信号筛选审计独立生成；严禁使用预后或临床表确定技术队列。
- B集在`freeze_lock.json`生成前保持不可见；冻结前不生成B集特征、QC或模型比较结果。
- 快速检查及重复内部验证中，聚类、插补、特征处理、标准化和调参均在外层训练折内拟合。
- B在全A参数、特征和模型冻结前不得用于方法选择；冻结后仅验证一次。
