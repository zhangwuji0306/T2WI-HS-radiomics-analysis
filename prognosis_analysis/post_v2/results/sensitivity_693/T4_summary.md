# T4 Primary v2 vs 693例无准入门槛 DFS 敏感性分析

- 目标队列：A=530、B=163，总计693例；仅移除高信号准入门槛。
- Primary v2 A393 的既有折叠与冻结资产保持不变；A 扩展病例使用 seed=12345 按 DFS_event 分层确定性补充分折。
- A 侧使用 expanded-A 5-fold validation 和 full-A refit；B 侧仅使用 A 冻结模型进行预测后评价。

## A 侧结果

- M0; harrell_c_index_pooled=0.6096 (Δ-0.0064); uno_c_index=0.5862 (Δ-0.0777); 3_year_auc=0.6520 (Δ-0.0041); 3_year_brier=0.1217 (Δ-0.0194); 5_year_auc=0.6687 (Δ-0.0137); 5_year_brier=0.1523 (Δ-0.0280)
- M1; harrell_c_index_pooled=0.6126 (Δ-0.0038); uno_c_index=0.5986 (Δ-0.0634); 3_year_auc=0.6515 (Δ-0.0032); 3_year_brier=0.1214 (Δ-0.0199); 5_year_auc=0.6656 (Δ-0.0120); 5_year_brier=0.1520 (Δ-0.0285)
- M2; harrell_c_index_pooled=0.6033 (Δ-0.0058); uno_c_index=0.5767 (Δ-0.0630); 3_year_auc=0.6519 (Δ0.0040); 3_year_brier=0.1234 (Δ-0.0223); 5_year_auc=0.6481 (Δ-0.0089); 5_year_brier=0.1542 (Δ-0.0300)
- M3L; harrell_c_index_pooled=0.5978 (Δ-0.0341); uno_c_index=0.5467 (Δ-0.1018); 3_year_auc=0.6448 (Δ-0.0041); 3_year_brier=0.1227 (Δ-0.0152); 5_year_auc=0.6303 (Δ-0.0443); 5_year_brier=0.1542 (Δ-0.0211)
- M3H; harrell_c_index_pooled=0.6154 (Δ-0.0051); uno_c_index=0.6003 (Δ-0.0565); 3_year_auc=0.6562 (Δ-0.0039); 3_year_brier=0.1229 (Δ-0.0195); 5_year_auc=0.6563 (Δ-0.0347); 5_year_brier=0.1536 (Δ-0.0264)
- M4; harrell_c_index_pooled=0.5733 (Δ-0.0432); uno_c_index=0.5293 (Δ-0.1102); 3_year_auc=0.6161 (Δ-0.0362); 3_year_brier=0.1241 (Δ-0.0216); 5_year_auc=0.6303 (Δ-0.0323); 5_year_brier=0.1570 (Δ-0.0287)
- M5; harrell_c_index_pooled=0.6275 (Δ-0.0186); uno_c_index=0.5421 (Δ-0.1176); 3_year_auc=0.6756 (Δ0.0147); 3_year_brier=0.1179 (Δ-0.0184); 5_year_auc=0.6663 (Δ-0.0189); 5_year_brier=0.1496 (Δ-0.0251)

## B 侧结果

- M0; harrell_c_index_pooled=0.6678 (Δ0.0155); uno_c_index=0.6836 (Δ0.0139); 3_year_auc=0.6428 (Δ0.0254); 3_year_brier=0.1288 (Δ-0.0104); 5_year_auc=0.6836 (Δ0.0162); 5_year_brier=0.1647 (Δ-0.0215)
- M1; harrell_c_index_pooled=0.6680 (Δ0.0143); uno_c_index=0.6851 (Δ0.0132); 3_year_auc=0.6434 (Δ0.0238); 3_year_brier=0.1289 (Δ-0.0105); 5_year_auc=0.6827 (Δ0.0151); 5_year_brier=0.1638 (Δ-0.0220)
- M2; harrell_c_index_pooled=0.6515 (Δ0.0002); uno_c_index=0.6692 (Δ-0.0041); 3_year_auc=0.6200 (Δ0.0094); 3_year_brier=0.1306 (Δ-0.0090); 5_year_auc=0.6712 (Δ0.0069); 5_year_brier=0.1660 (Δ-0.0221)
- M3L; harrell_c_index_pooled=0.6401 (Δ0.0356); uno_c_index=0.6558 (Δ0.0388); 3_year_auc=0.6155 (Δ0.0433); 3_year_brier=0.1277 (Δ-0.0160); 5_year_auc=0.6603 (Δ0.0244); 5_year_brier=0.1723 (Δ-0.0302)
- M3H; harrell_c_index_pooled=0.6889 (Δ0.0082); uno_c_index=0.6808 (Δ0.0102); 3_year_auc=0.6572 (Δ0.0088); 3_year_brier=0.1262 (Δ-0.0087); 5_year_auc=0.7158 (Δ0.0077); 5_year_brier=0.1566 (Δ-0.0222)
- M4; harrell_c_index_pooled=0.6652 (Δ0.0207); uno_c_index=0.6624 (Δ0.0069); 3_year_auc=0.6466 (Δ0.0054); 3_year_brier=0.1258 (Δ-0.0116); 5_year_auc=0.6687 (Δ0.0056); 5_year_brier=0.1676 (Δ-0.0253)
- M5; harrell_c_index_pooled=0.6469 (Δ0.0236); uno_c_index=0.6551 (Δ0.0186); 3_year_auc=0.6658 (Δ0.0276); 3_year_brier=0.1287 (Δ-0.0089); 5_year_auc=0.6691 (Δ0.0256); 5_year_brier=0.1716 (Δ-0.0220)

## 覆盖度

详见 `T4_coverage.csv`；每个模型均同时报告 eligible_n、总目标数、覆盖率、事件数和事件覆盖率。

## 共同人群模型比较

已完成任务书第十节规定的12组模型比较；每组均使用共同可分析人群。逐指标Δ均附带患者级配对bootstrap（200次重抽样）的percentile 95%置信区间。详见 `T4_model_comparison_summary.md`、`T4_common_population_comparisons.csv` 和 `T4_common_population_eligibility.csv`。

