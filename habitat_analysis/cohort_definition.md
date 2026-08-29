# 生境分析队列定义

## 主分析集

病例使用R1原始T2WI和同图瘤周脂肪ROI进行筛选。高信号体素定义为肿瘤ROI内信号强度不低于该病例脂肪ROI均值的体素。每例必须同时满足：

1. 高信号体素数不少于1；
2. 高信号体素占肿瘤总体素的比例不低于0.1%。

宽松主分析集共500例：开发集A 393例，设备留出验证集B 107例。A/B归属沿用原设备划分，不因筛选改变。

上述病例数为技术评估目标集。生境生成后，空生境、算法失败、未分配体素或几何/标签错误病例按预设技术规则处理：联合失败率＜5%时逐例记录并剔除，技术成功病例构成最终生境主分析队列；联合失败率≥5%时停止相应阶段。原始筛选状态和A/B归属保持不变。

## 严格敏感性集

每例同时满足：

1. 高信号体素占比不低于1%；
2. 最大26邻域高信号连通成分体积不低于128 mm³；
3. 距肿瘤边界至少2 mm的高信号体积不低于32 mm³。

严格敏感性集共160例：A 137例，B 23例。该队列仅用于预设敏感性分析，不替代宽松主分析集。

## 数据边界

- 入组判定仅使用R1，不读取DFS、OS、治疗、病理或模型结果。
- 原始693例记录保留，筛选仅生成状态和分析子集，不删除病例。
- B不参与筛选阈值、生境参数、特征处理、模型参数或判定阈值的确定。
- R2仅用于后续双读者技术评价，不定义主分析入组。

## 权威文件

- 逐病例测量：`output/high_signal_eligibility_audit/patient_features.csv`
- 宽松判定：`output/high_signal_eligibility_audit/lenient_screening_decisions.csv`
- 宽松病例：`output/high_signal_eligibility_audit/lenient_selected_cases.csv`
- 严格判定：`output/high_signal_eligibility_audit/recommended_screening_decisions.csv`
- 严格病例：`output/high_signal_eligibility_audit/recommended_selected_cases.csv`
- 主建模清单：`../prognosis_analysis/output/modeling_v2/dataset_primary_raw*.csv`
- 严格建模清单：`../prognosis_analysis/output/modeling_v2/dataset_primary_raw*_strict*.csv`
