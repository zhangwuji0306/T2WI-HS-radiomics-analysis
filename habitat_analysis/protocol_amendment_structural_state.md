# 生境分析协议修订：结构性单生境状态

## 主方法

主方法为肌肉均值归一化、`[1,1,2] mm`重采样、4 mm三维SLIC和跨病例K-means K=2。全部与肿瘤ROI相交的有效超体素进入拟合；病例 (i) 的 (n_i) 个超体素分别赋予 (1/n_i) 权重，使每例总权重固定为1。聚类中心按低到高固定为`H-low`和`H-high`。

主方法仅使用R1。R2按逐病例肌肉标签解析结果用于重复性描述；无法无猜测解析肌肉标签的R2不进入配对评价，R1不受影响。

## 技术失败定义

硬技术失败包括图像读取、几何、肌肉归一化、SLIC、非有限特征、聚类数值和未分配肿瘤体素错误。按唯一病例合并计算联合硬技术失败率：

```text
硬技术失败率 = 硬技术失败唯一病例数 / 本批次全部目标病例数
```

失败率严格小于5%时记录并剔除硬技术失败病例后继续；达到或超过5%时停止当前阶段。空生境不属于硬技术失败。

## 结构状态

每例按H-low/H-high体素分配标记为：

- `single-H-low`：H-high体素数为0；
- `single-H-high`：H-low体素数为0；
- `dual-habitat`：两类均有肿瘤体素。

结构性单生境保留在主分析队列。缺失表型的存在指示、体积分数、`habitat_entropy`、`interface_density`及H-high连通成分描述可按预先定义的结构零规则取0；相应表型内纹理在表型不存在时保持未定义，不填0，也不作普通缺失插补。

病例内K-means仅用于local-global机制诊断，不生成主生境图、不进入预后模型，也不用于B集重新聚类。

## 主低维特征字典

全队列主要特征候选为：

1. `H_high_fraction`；
2. `habitat_entropy`；
3. `interface_density`；
4. `H_high_largest_component_tumor_fraction`；
5. `H_high_component_density`；
6. `H_high_radial_burden`；
7. `sv_median_minus_boundary`；
8. `sv_IQR`。

`H_low_fraction=1-H_high_fraction`不与`H_high_fraction`同时进入模型。全A中心只能用于技术描述和最终全A拟合准备；嵌套内部验证必须在每个外层训练折内重新拟合中心并生成验证折特征。

## 盲法与停止

本修订及阶段0至阶段7技术核验均不读取DFS、临床变量或B集。只有协议、结构状态、local-global诊断、bootstrap、技术因素核验、严格A=137敏感性和主特征字典全部通过后，才可进入A集临床与DFS一对一合并；合并完成后立即停止，不在该阶段拟合预后模型或评价模型性能。
