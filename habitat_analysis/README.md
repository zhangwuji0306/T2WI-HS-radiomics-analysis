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

当前主方法候选为三维 SLIC 4 mm 加跨病例 K-means K=2。流程首先在 A=393 的全部 R1 病例上执行无结局技术干跑；空生境、算法失败、未分配肿瘤体素及几何/标签错误按唯一病例合并计算，联合失败率＜5%时记录并剔除失败病例后进入生境特征与预后建模，达到或超过5%时停止。B=107 在全 A 参数与模型冻结前保持不可见。

`scripts/`仅存放当前方案脚本；`output/`各目录的用途见`output/README.md`；参数冻结及执行状态见`analysis_freeze.md`。
