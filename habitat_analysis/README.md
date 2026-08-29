# 生境分析工作区

本目录承载当前直肠癌 T2WI 生境分析。正式方法、停止规则和统计路径以项目根目录的《生境分析方案与工作流.md》为准；队列规则见`cohort_definition.md`，机器可读主参数见`configs/main_cross_case_kmeans_k2_4mm.json`。

## 当前输入

- 图像清单与设备信息：`../feature_extract/output/manifest.csv`、`../feature_extract/output/scanner_map.csv`
- 肌肉归一化主预处理图像：`../feature_extract/output/preprocessed/`
- 高信号筛选审计：`output/high_signal_eligibility_audit/`
- 宽松主分析集与严格敏感性集：`../prognosis_analysis/output/modeling_v2/`
- 临床、影像、病理及预后原始表：`../prognosis_analysis/data/`
- H5 整块肿瘤候选：`../feature_extract/output/features_v2/`及`../prognosis_analysis/output/qc/stage6_v2/`

## 执行边界

当前主方法为三维 SLIC 4 mm 加全部有效超体素、每例总权重固定为1的跨病例 K-means K=2；在`[1,1,2] mm`图像上使用`[4,4,2]`体素超网格。空生境记录为`single-H-low`、`single-H-high`或`dual-habitat`结构状态，不计入硬技术失败；硬技术失败率＜5%时记录并剔除，达到或超过5%时停止。校正后18例比较、A=393基线、结构诊断、local-global、bootstrap冒烟、技术因素效应量和A=137核验已完成；正式1000次bootstrap及冻结门禁完成前不纳入A集结局。B=107 在全 A 参数、特征和模型冻结前保持不可见。

`scripts/`仅存放当前方案脚本；`output/`各目录的用途见`output/README.md`；参数冻结及执行状态见`analysis_freeze.md`。
