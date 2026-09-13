# Primary Prognostic Analysis v2

本目录登记项目当前唯一正式预后分析科学合同：**Primary Prognostic Analysis v2 — Frozen Full-A Habitat Validation**。

这是一次 **post-FT protocol transition**：Formal W08 v1 未成功完成，Formal v1 为 superseded；Primary v2 是方法框架提升与登记，不是重新计算患者级结果。FT03 A 结果和 FT06 B 外部验证结果在换轨决定时已经可见，因此不把本方案追溯描述为 B 验证前的正式预先指定方案。

## 固定研究对象与终点

- 主终点为 DFS，固定评价时点为 3 年和 5 年。
- 主 A 建模队列是 W06 endpoint QC 后的 exact A393 modeling population；已核对为 393 例、89 个 DFS events、304 个删失。
- 上游技术筛选文档另记录 lenient target A393/B107 和 strict sensitivity target A137/B23。它们是技术筛选分母，不与 FT06 外部验证分母静默合并。
- FT06 既有 B external validation 记录授权 163 例、42 个 DFS events；Primary v2 后续 B 输入必须绑定这个 FT06 authorized cohort identity。

## 固定影像表型与预测块

- 使用一次建立的 fixed full-A habitat：3D SLIC，target supervoxel scale 4 mm，cross-case K-means，`K=2`，`n_init=100`。
- 较低和较高聚类中心分别固定为 H-low 和 H-high。CV fold 与 B 中不得重新拟合 centers、boundary 或 habitat radiomics，也不得根据 DFS 调整 boundary。
- `C` 是冻结的治疗时点临床变量块；`G` 是冻结的六个 global habitat descriptors。
- `R_low=49`，candidate hash 为 `a5f6b8e571d222ce442b87b54c7fe295ccfce3201cfc1f75c3859a00fcbc46b0`。
- `R_high=10`，candidate hash 为 `a0bbb4b4ab475fffb725dd2c04c407273cf57c486bd00198e3d77f736e7434ce`。
- `W_Original=107`，order hash 为 `1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f`；不使用 Wavelet、LoG 或其他 filtered radiomics 作为主 whole-tumour comparator。

## 固定模型与验证

保留全部 M0–M5，不因 FT03/FT06 的观察结果删除、升级或重新排序模型：

| 模型 | 预测块 | 模型类型 |
|---|---|---|
| M0 | C | unpenalized Cox PH |
| M1 | C + H_high_fraction | unpenalized Cox PH |
| M2 | C + G | unpenalized Cox PH |
| M3L | C + G + R_low | LASSO-Cox, `alpha=1` |
| M3H | C + G + R_high | LASSO-Cox, `alpha=1` |
| M4 | C + G + R_low + R_high | LASSO-Cox, `alpha=1` |
| M5 | C + W_Original | LASSO-Cox, `alpha=1` |

A 内部验证固定为 W07 repeat-1 的 single-repeat 5-fold outer validation；不使用旧 W07 的 10-repeat 设计。高维模型的 lambda 只能在每个 outer-training set 内通过 training-only inner 5-fold CV 选择，outer-validation 数据不得参与插补、缩放、过滤、特征选择或 lambda 选择。

## B 外部验证边界

B 只能按以下顺序执行：

```text
load frozen model
→ load frozen-compatible B predictors
→ predict
→ evaluate
```

B 不得用于 feature selection、lambda tuning、coefficient refit、cutoff optimization、habitat refit、radiomics candidate re-selection 或 B→A feedback。B 的模型身份必须在 B 评价前冻结。

## 证据与完整合同

已核对的 FT03/FT04/FT06 状态及哈希、cohort 分母说明、模型定义、验证规则和 fail-closed 边界见 [protocol.json](protocol.json)。本目录不保存患者级特征、预测、原始影像、ROI、临床/病理/预后表或分析输出。
