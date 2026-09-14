# T4 模型比较框架：共同可分析人群

按任务书第十、十一节完成12组预设模型比较；每组均在共同可分析人群中计算。
A侧对比较所需的模型在人群限定后重新进行5-fold validation；B侧保持A冻结模型，仅在共同B人群中进行外部评价。

## A侧

- M0_vs_M3L [R_low, n=528, events=120]: harrell_c_index_pooled 0.6094→0.5978 (Δ-0.0116); uno_c_index 0.5820→0.5467 (Δ-0.0353); 3_year_auc 0.6553→0.6448 (Δ-0.0104); 3_year_brier 0.1222→0.1227 (Δ+0.0004); 5_year_auc 0.6676→0.6303 (Δ-0.0373); 5_year_brier 0.1520→0.1542 (Δ+0.0023)
- M0_vs_M3H [R_high, n=443, events=100]: harrell_c_index_pooled 0.6186→0.6154 (Δ-0.0032); uno_c_index 0.6119→0.6003 (Δ-0.0116); 3_year_auc 0.6549→0.6562 (Δ+0.0012); 3_year_brier 0.1218→0.1229 (Δ+0.0010); 5_year_auc 0.6756→0.6563 (Δ-0.0193); 5_year_brier 0.1530→0.1536 (Δ+0.0006)
- M0_vs_M1 [main, n=530, events=121]: harrell_c_index_pooled 0.6096→0.6126 (Δ+0.0030); uno_c_index 0.5862→0.5986 (Δ+0.0124); 3_year_auc 0.6520→0.6515 (Δ-0.0005); 3_year_brier 0.1217→0.1214 (Δ-0.0003); 5_year_auc 0.6687→0.6656 (Δ-0.0031); 5_year_brier 0.1523→0.1520 (Δ-0.0003)
- M0_vs_M2 [main, n=530, events=121]: harrell_c_index_pooled 0.6096→0.6033 (Δ-0.0063); uno_c_index 0.5862→0.5767 (Δ-0.0095); 3_year_auc 0.6520→0.6519 (Δ-0.0001); 3_year_brier 0.1217→0.1234 (Δ+0.0018); 5_year_auc 0.6687→0.6481 (Δ-0.0206); 5_year_brier 0.1523→0.1542 (Δ+0.0018)
- M0_vs_M4 [dual_radiomics, n=441, events=99]: harrell_c_index_pooled 0.6178→0.5733 (Δ-0.0445); uno_c_index 0.6135→0.5293 (Δ-0.0842); 3_year_auc 0.6582→0.6161 (Δ-0.0421); 3_year_brier 0.1226→0.1241 (Δ+0.0016); 5_year_auc 0.6753→0.6303 (Δ-0.0450); 5_year_brier 0.1526→0.1570 (Δ+0.0044)
- M0_vs_M5 [W_Original_available, n=530, events=121]: harrell_c_index_pooled 0.6096→0.6275 (Δ+0.0179); uno_c_index 0.5862→0.5421 (Δ-0.0441); 3_year_auc 0.6520→0.6756 (Δ+0.0236); 3_year_brier 0.1217→0.1179 (Δ-0.0038); 5_year_auc 0.6687→0.6663 (Δ-0.0024); 5_year_brier 0.1523→0.1496 (Δ-0.0028)
- M2_vs_M3L [R_low, n=528, events=120]: harrell_c_index_pooled 0.6072→0.5978 (Δ-0.0094); uno_c_index 0.5765→0.5467 (Δ-0.0298); 3_year_auc 0.6560→0.6448 (Δ-0.0111); 3_year_brier 0.1239→0.1227 (Δ-0.0013); 5_year_auc 0.6532→0.6303 (Δ-0.0229); 5_year_brier 0.1532→0.1542 (Δ+0.0011)
- M2_vs_M3H [R_high, n=443, events=100]: harrell_c_index_pooled 0.6089→0.6154 (Δ+0.0065); uno_c_index 0.6049→0.6003 (Δ-0.0046); 3_year_auc 0.6548→0.6562 (Δ+0.0014); 3_year_brier 0.1249→0.1229 (Δ-0.0020); 5_year_auc 0.6569→0.6563 (Δ-0.0006); 5_year_brier 0.1561→0.1536 (Δ-0.0025)
- M1_vs_M2 [main, n=530, events=121]: harrell_c_index_pooled 0.6126→0.6033 (Δ-0.0093); uno_c_index 0.5986→0.5767 (Δ-0.0219); 3_year_auc 0.6515→0.6519 (Δ+0.0004); 3_year_brier 0.1214→0.1234 (Δ+0.0020); 5_year_auc 0.6656→0.6481 (Δ-0.0175); 5_year_brier 0.1520→0.1542 (Δ+0.0022)
- M2_vs_M4 [dual_radiomics, n=441, events=99]: harrell_c_index_pooled 0.6145→0.5733 (Δ-0.0412); uno_c_index 0.6095→0.5293 (Δ-0.0802); 3_year_auc 0.6574→0.6161 (Δ-0.0413); 3_year_brier 0.1257→0.1241 (Δ-0.0016); 5_year_auc 0.6609→0.6303 (Δ-0.0307); 5_year_brier 0.1549→0.1570 (Δ+0.0021)
- M3L_vs_M3H [dual_radiomics, n=441, events=99]: harrell_c_index_pooled 0.5892→0.5984 (Δ+0.0092); uno_c_index 0.5352→0.5944 (Δ+0.0592); 3_year_auc 0.6274→0.6482 (Δ+0.0207); 3_year_brier 0.1224→0.1238 (Δ+0.0014); 5_year_auc 0.6361→0.6553 (Δ+0.0192); 5_year_brier 0.1549→0.1528 (Δ-0.0021)
- M4_vs_M5 [dual_radiomics, n=441, events=99]: harrell_c_index_pooled 0.5733→0.5904 (Δ+0.0171); uno_c_index 0.5293→0.5105 (Δ-0.0188); 3_year_auc 0.6161→0.6271 (Δ+0.0110); 3_year_brier 0.1241→0.1239 (Δ-0.0002); 5_year_auc 0.6303→0.6359 (Δ+0.0056); 5_year_brier 0.1570→0.1563 (Δ-0.0008)

## B侧

- M0_vs_M3L [R_low, n=162, events=42]: harrell_c_index_pooled 0.6665→0.6401 (Δ-0.0265); uno_c_index 0.6824→0.6558 (Δ-0.0266); 3_year_auc 0.6417→0.6155 (Δ-0.0262); 3_year_brier 0.1296→0.1277 (Δ-0.0019); 5_year_auc 0.6825→0.6603 (Δ-0.0222); 5_year_brier 0.1658→0.1723 (Δ+0.0065)
- M0_vs_M3H [R_high, n=131, events=35]: harrell_c_index_pooled 0.6867→0.6889 (Δ+0.0023); uno_c_index 0.7015→0.6808 (Δ-0.0207); 3_year_auc 0.6575→0.6572 (Δ-0.0003); 3_year_brier 0.1312→0.1262 (Δ-0.0050); 5_year_auc 0.7110→0.7158 (Δ+0.0048); 5_year_brier 0.1643→0.1566 (Δ-0.0077)
- M0_vs_M1 [main, n=163, events=42]: harrell_c_index_pooled 0.6678→0.6680 (Δ+0.0002); uno_c_index 0.6836→0.6851 (Δ+0.0014); 3_year_auc 0.6428→0.6434 (Δ+0.0007); 3_year_brier 0.1288→0.1289 (Δ+0.0000); 5_year_auc 0.6836→0.6827 (Δ-0.0009); 5_year_brier 0.1647→0.1638 (Δ-0.0009)
- M0_vs_M2 [main, n=163, events=42]: harrell_c_index_pooled 0.6678→0.6515 (Δ-0.0162); uno_c_index 0.6836→0.6692 (Δ-0.0145); 3_year_auc 0.6428→0.6200 (Δ-0.0228); 3_year_brier 0.1288→0.1306 (Δ+0.0018); 5_year_auc 0.6836→0.6712 (Δ-0.0124); 5_year_brier 0.1647→0.1660 (Δ+0.0013)
- M0_vs_M4 [dual_radiomics, n=130, events=35]: harrell_c_index_pooled 0.6850→0.6652 (Δ-0.0198); uno_c_index 0.6998→0.6624 (Δ-0.0373); 3_year_auc 0.6558→0.6466 (Δ-0.0091); 3_year_brier 0.1322→0.1258 (Δ-0.0063); 5_year_auc 0.7096→0.6687 (Δ-0.0410); 5_year_brier 0.1656→0.1676 (Δ+0.0020)
- M0_vs_M5 [W_Original_available, n=163, events=42]: harrell_c_index_pooled 0.6678→0.6469 (Δ-0.0209); uno_c_index 0.6836→0.6551 (Δ-0.0286); 3_year_auc 0.6428→0.6658 (Δ+0.0230); 3_year_brier 0.1288→0.1287 (Δ-0.0001); 5_year_auc 0.6836→0.6691 (Δ-0.0145); 5_year_brier 0.1647→0.1716 (Δ+0.0068)
- M2_vs_M3L [R_low, n=162, events=42]: harrell_c_index_pooled 0.6482→0.6401 (Δ-0.0082); uno_c_index 0.6658→0.6558 (Δ-0.0100); 3_year_auc 0.6147→0.6155 (Δ+0.0008); 3_year_brier 0.1316→0.1277 (Δ-0.0040); 5_year_auc 0.6689→0.6603 (Δ-0.0086); 5_year_brier 0.1675→0.1723 (Δ+0.0048)
- M2_vs_M3H [R_high, n=131, events=35]: harrell_c_index_pooled 0.6548→0.6889 (Δ+0.0341); uno_c_index 0.6748→0.6808 (Δ+0.0060); 3_year_auc 0.6047→0.6572 (Δ+0.0525); 3_year_brier 0.1375→0.1262 (Δ-0.0113); 5_year_auc 0.6811→0.7158 (Δ+0.0347); 5_year_brier 0.1694→0.1566 (Δ-0.0128)
- M1_vs_M2 [main, n=163, events=42]: harrell_c_index_pooled 0.6680→0.6515 (Δ-0.0164); uno_c_index 0.6851→0.6692 (Δ-0.0159); 3_year_auc 0.6434→0.6200 (Δ-0.0234); 3_year_brier 0.1289→0.1306 (Δ+0.0018); 5_year_auc 0.6827→0.6712 (Δ-0.0115); 5_year_brier 0.1638→0.1660 (Δ+0.0022)
- M2_vs_M4 [dual_radiomics, n=130, events=35]: harrell_c_index_pooled 0.6497→0.6652 (Δ+0.0155); uno_c_index 0.6701→0.6624 (Δ-0.0077); 3_year_auc 0.5974→0.6466 (Δ+0.0492); 3_year_brier 0.1390→0.1258 (Δ-0.0132); 5_year_auc 0.6754→0.6687 (Δ-0.0067); 5_year_brier 0.1718→0.1676 (Δ-0.0042)
- M3L_vs_M3H [dual_radiomics, n=130, events=35]: harrell_c_index_pooled 0.6382→0.6833 (Δ+0.0451); uno_c_index 0.6589→0.6765 (Δ+0.0176); 3_year_auc 0.6214→0.6473 (Δ+0.0259); 3_year_brier 0.1311→0.1294 (Δ-0.0018); 5_year_auc 0.6368→0.7131 (Δ+0.0763); 5_year_brier 0.1754→0.1596 (Δ-0.0158)
- M4_vs_M5 [dual_radiomics, n=130, events=35]: harrell_c_index_pooled 0.6652→0.6733 (Δ+0.0080); uno_c_index 0.6624→0.6939 (Δ+0.0314); 3_year_auc 0.6466→0.6371 (Δ-0.0095); 3_year_brier 0.1258→0.1333 (Δ+0.0075); 5_year_auc 0.6687→0.6883 (Δ+0.0196); 5_year_brier 0.1676→0.1720 (Δ+0.0044)

## 解释规则

Harrell C、Uno C和AUC的正Δ表示右侧模型数值更高；Brier的负Δ表示右侧模型数值更优。
共同人群的样本数、事件数和覆盖度详见 `T4_common_population_eligibility.csv`；逐指标结果详见 `T4_common_population_comparisons.csv`。

