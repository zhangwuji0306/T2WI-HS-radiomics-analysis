# 探索阶段归档清单

归档日期：2026-08-28

归档规模：5399个文件，约499.31 MB。

本目录保存当前生境主方案不直接复用的既往探索材料。归档内容不作为当前分析输入，也不从归档路径直接运行。

## Previous radiomics

- `feature_outputs/features_invalidated/`：失效的早期影像组学特征。
- `zscore_preprocessing/preprocessed_zscore/`：不属于当前生境方案的既往Z-score预处理产物。
- `n4_pilot/`：既往N4试点图像、特征、判定和报告。
- `modeling/modeling_invalidated/`：失效的早期建模表。
- `modeling/model_runs/`：既往影像组学嵌套验证与快速检查结果。
- `modeling/stage6_invalidated/`：失效的早期阶段六QC。
- `modeling/分析计划.md`：既往整块肿瘤影像组学建模计划。
- `scripts/`：既往整块肿瘤插补、嵌套验证、快速检查和A集AUC脚本。
- `configs/`：既往整块肿瘤主分析与敏感性配置。

## Previous habitat

- `configs/`：既往跨病例/病例内多尺度技术试点配置。
- `scripts/`：既往技术试点、方法比较和筛选探索脚本及字节码缓存。
- `outputs/`：既往4/6/8 mm、多方法、多读者生境图、QC、日志和技术报告。
- `outputs/high_signal_screening_exploration/`：阈值情景比较及依赖既往生境试点的筛选后技术子集结果。
- `documents/技术门槛判定与后续工作流.md`：既往生境判定与工作流文档。
- `documents/高信号病例自动化筛选计划.md`：包含阈值探索和既往病例内K-means路径的筛选阶段文档。

## Other exploratory files

- `documents/研究简报.md`：探索阶段研究简报。
- `temporary/`：环境核验与临时特征验证文件。

## 保留在当前项目中的可复用资产

- 原始图像、ROI、主清单、设备映射及肌肉归一化主预处理产物。
- 当前高信号筛选审计、宽松/严格病例清单和临床数据。
- `features_v2`与`stage6_v2`中的整块肿瘤候选，供H5次要探索模型使用。
- 预处理、N4/各向同性敏感性、特征提取、主清单和建模数据构建脚本。
- 已冻结的`roi_review_cases`目录。
