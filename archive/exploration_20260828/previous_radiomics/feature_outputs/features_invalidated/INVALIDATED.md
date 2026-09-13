# 旧版特征产物失效说明

本目录下特征由旧版“整幅图像预离散化后再交给 PyRadiomics”的流程生成，导致多数
first-order 特征描述 bin 编号而非连续归一化强度；Wavelet/LoG 分支还重复提取了 Shape。

自 2026-08-27 起，本目录仅供审计，不得用于建模或论文结果。修正版脚本默认写入
`feature_extract/output/features_v2/`。完成 v2 全量重提取并通过质控前，项目建模暂停。
