# M1主特征字典

## 冻结状态

- 当前冻结判定：通过。
- 主方法：肌肉均值归一化、`[1,1,2] mm`、4 mm三维SLIC、全部有效超体素、每例总权重1、跨病例K-means K=2。
- 全A技术中心：H-low=2.101717，H-high=3.519630，边界b=2.810674。
- 结构性单生境保留；不计入硬技术失败。

## 主预测特征块

|特征|公式|结构性规则|
|---|---|---|
|`H_high_fraction`|H-high体素数/肿瘤总体素数|H-high缺失时为0|
|`sv_median_minus_boundary`|病例超体素Mean中位数−b|始终定义|
|`sv_IQR`|病例超体素Mean的P75−P25|始终定义|
|`interface_density`|H-low/H-high三维6邻接界面面积/肿瘤体积|单生境为0|
|`H_high_largest_component_tumor_fraction`|最大H-high 6连通成分体积/肿瘤体积|H-high缺失时为0|
|`H_high_radial_burden`|H-high归一化径向深度之和/肿瘤总体素数|H-high缺失时为0|

`habitat_entropy`与`H_high_component_density`保留为描述性候选，不纳入当前主预测块。表型内纹理在相应表型不存在时保持未定义，不填0。嵌套内部验证必须在每个外层训练折内重新拟合中心并生成验证折特征。
