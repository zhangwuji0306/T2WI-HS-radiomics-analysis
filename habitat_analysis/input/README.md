# 输入索引

本目录不复制上游数据，权威输入保留在其生成位置：

|输入|权威路径|用途|
|---|---|---|
|病例清单|`../../feature_extract/output/manifest.csv`|图像、ROI和读者追溯|
|设备映射|`../../feature_extract/output/scanner_map.csv`|A/B设备定义与分层描述|
|主预处理图像|`../../feature_extract/output/preprocessed/`|生境生成|
|高信号筛选结果|`../output/high_signal_eligibility_audit/`|宽松主分析集及严格敏感性集定义|
|建模主清单|`../../prognosis_analysis/output/modeling_v2/`|A/B病例、临床变量及终点|
|整块肿瘤候选|`../../feature_extract/output/features_v2/`|H5次要探索模型|
|整块肿瘤候选QC|`../../prognosis_analysis/output/qc/stage6_v2/`|H5候选池审计|

分析脚本不得在本目录生成输入副本；每次运行应在相应输出目录保存实际读取文件的路径、大小、修改时间及哈希。
