# 患者内相对生境技术试点报告

> 本报告仅使用A集同序列R1/R2的技术重复性数据，不读取生存结局，不生成B集结果。

## 执行摘要

- A集同序列双读者病例：18例；指标行：324；运行时间：887.6秒。
- 主方法：肌肉均值归一化、[1,1,2] mm、三维SLIC、患者内K=2；按患者内聚类中心低/高标记H-low/H-high。
- 敏感性：患者内Otsu、[2,2,2] mm、N4、ROI侵蚀/膨胀。
- 空生境、方法失败和无法分配均按技术失败计入，不从Dice中删除。

## 主方法技术指标

|尺度|H-low Dice中位数|H-high Dice中位数|空/失败比例|H-high分数ICC(2,1)|零失败门槛|
|---:|---:|---:|---:|---:|:---|
| 4 mm | 0.773 | 0.844 | 0.0% | 0.455 | 通过 |
| 6 mm | 0.777 | 0.868 | 0.0% | 0.596 | 通过 |
| 8 mm | 0.800 | 0.827 | 0.0% | 0.623 | 通过 |

## 描述符与纹理可计算性

- 描述符ICC、低维描述符和生境内纹理可计算比例见`descriptor_icc.csv`及`summary.csv`，均作为后续技术描述，不作为当前停止门槛。

## 敏感性分支

|变体|尺度|H-low Dice中位数|H-high Dice中位数|空/失败比例|
|:---|---:|---:|---:|---:|
| patient_k2_isotropic_2x2x2 | 4 mm | 0.885 | 0.830 | 0.0% |
| patient_k2_isotropic_2x2x2 | 6 mm | 0.839 | 0.818 | 0.0% |
| patient_k2_isotropic_2x2x2 | 8 mm | 0.707 | 0.820 | 0.0% |
| patient_k2_n4_1x1x2 | 4 mm | 0.778 | 0.730 | 0.0% |
| patient_k2_n4_1x1x2 | 6 mm | 0.841 | 0.916 | 0.0% |
| patient_k2_n4_1x1x2 | 8 mm | 0.826 | 0.819 | 0.0% |
| patient_k2_roi_dilate1 | 4 mm | 0.834 | 0.459 | 0.0% |
| patient_k2_roi_dilate1 | 6 mm | 0.948 | 0.697 | 0.0% |
| patient_k2_roi_dilate1 | 8 mm | 0.941 | 0.692 | 0.0% |
| patient_k2_roi_erode1 | 4 mm | 0.666 | 0.702 | 0.0% |
| patient_k2_roi_erode1 | 6 mm | 0.846 | 0.894 | 0.0% |
| patient_k2_roi_erode1 | 8 mm | 0.870 | 0.898 | 0.0% |
| patient_otsu_1x1x2 | 4 mm | 0.773 | 0.844 | 0.0% |
| patient_otsu_1x1x2 | 6 mm | 0.777 | 0.868 | 0.0% |
| patient_otsu_1x1x2 | 8 mm | 0.800 | 0.827 | 0.0% |

## QC与门槛状态

- 6 mm主方法叠加图输出于 `../qc_amended/overlays/patient_k2_1x1x2/`；每例包含R1和R2，供逐例核对ROI边界、层面方向和标签方向。
- 当前人工叠加图复核状态：not_evaluated。
- 当前零失败门槛以空生境、算法失败和未分配体素为准；人工QC、Dice、ICC及纹理准入率后续报告。

## 文件索引

- `case_selection.csv`：入选病例及原始文件；
- `pair_metrics.csv`：逐病例、逐尺度技术指标；
- `summary.csv`：分支汇总；
- `descriptor_icc.csv`：低维描述符ICC；
- `run_manifest.csv`：运行边界与结局/B集隔离声明。
