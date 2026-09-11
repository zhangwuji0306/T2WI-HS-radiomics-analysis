# T2WI-HS 生境预后快速验证（FT）方案书

## 一、任务定位

FT 为独立于正式 L9 的快速探索性验证支线。

目标：

- 使用冻结的 full_A habitat；
- 复用既有 A 影像组学特征及 B 的 W_Original 资产；
- 保持正式分析 M0–M5 全部模型；
- A 使用普通单层 5-fold CV；
- A 模型冻结后，先在 outcome-blind 条件下首次生成 B habitat radiomics，再冻结 B 特征并进行一次 external validation；
- 不修改、不暂停、不替代正式 L9。

FT 结果统一标记：

`exploratory_fullA_habitat_non_nested_validation`

---

## 二、冻结原则

FT 不重新优化：

- A/B cohort；
- DFS endpoint；
- full_A habitat；
- SLIC；
- K=2；
- `n_init=100`；
- H-low/H-high 定义；
- C、G、R_low、R_high、W（全瘤 Original 特征）；
- M0–M5 模型结构。

固定：

- `R_low = 49`
- `R_high = 10`

禁止在全 A 上重新进行 DFS-based 单因素特征筛选。

本次小范围协议修订记录于：

`prognosis_analysis/ft/FT_protocol_amendment_20260911.json`

该修订不改变 FT 主框架、模型集合、A 分析、结局、split、候选池或模型冻结要求，只修正 B habitat radiomics 的生成时点与访问顺序，并确认 M5 的 FT 专用定义。

### 全瘤影像组学特征 W

为与生境影像组学特征保持定义一致，FT 中的全瘤特征块 `W` 仅纳入既有的 **Original** 特征。

排除：

- Wavelet 特征；
- LoG 及其他滤波特征。

M5 使用 `C + W_Original`，作为 `FT-specific approved amendment`。W_Original 固定为现有资产中按既定顺序排列的 107 个 Original whole-tumor features；其顺序 SHA-256 为：

`1c07cd4e129e368dde8539d552ecb0f453d9c655fe2a5383d00a5de7b408ca1f`

A、B 均不得为 FT 重新提取全瘤特征；B 仅核验并复用既有 W_Original 资产。该定义是已批准的 FT 快速验证设计，不作为待整改项。

特别明确：

“B 不重新提取 radiomics”定义为：B habitat radiomics 历史上从未生成，因此 FT05A 允许且仅允许一次 `outcome-blind` 的首次提取；完成后禁止重复提取、重新优化或根据 B 结果重跑。W_Original 始终直接复用现有 B 资产，不重新提取。

---

## 三、模型

| Model | Predictors | FT fitting |
|---|---|---|
| M0 | C | Cox |
| M1 | C + H_high_fraction | Cox |
| M2 | C + G | Cox |
| M3L | C + G + R_low | LASSO-Cox |
| M3H | C + G + R_high | LASSO-Cox |
| M4 | C + G + R_low + R_high | LASSO-Cox |
| M5 | C + W_Original | LASSO-Cox |

高维模型固定：

`family = Cox`

`alpha = 1`

采用普通单层 5-fold CV 选择 λ。

优先复用 W07 中预先冻结的一组 5-fold，例如 repeat 1。

不得根据性能重新生成 split。

---

# 四、A 快速内部验证

完成：

- 5-fold CV；
- cross-validated risk score；
- Uno C-index；
- Harrell C-index；
- 3/5-year AUC；
- 3/5-year Brier score；
- calibration；
- KM；
- DCA；
- bootstrap 95% CI；
- paired model comparisons。

主要比较：

- M0 vs M1；
- M0 vs M2；
- M2 vs M3L；
- M2 vs M3H；
- M2 vs M4；
- M3L vs M3H；
- M4 vs M5。

所有比较使用共同 eligible population。

FT 的 A performance 明确属于：

`non_nested_exploratory_estimate`

不得替代正式 L9 的严格 nested-CV 结果。

---

# 五、B 验证原则

A 最终模型冻结以前，不得开展 B 影像级 habitat 技术处理，也不得读取 B outcome。

完成 A 后冻结：

`FT_model_freeze_lock.json`

随后只开放 FT05A 所需的 B 影像技术访问；B DFS/outcome 继续保持锁定。

B 中禁止：

- feature selection；
- λ tuning；
- K-means fitting；
- habitat optimization；
- cutoff optimization；
- preprocessing parameter estimation；
- model selection；
- 根据 B 修改模型。

## B 特征资产的明确处理规则

B 的 R_low/R_high 历史上从未提取。其缺失状态为：

`NOT_YET_GENERATED`

而不是既有资产不兼容或重新提取失败。

FT05A 仅允许一次 outcome-blind 的首次 B habitat radiomics extraction：

- 使用冻结的 A-full habitat definition；
- B supervoxel 直接投影至 A 的 H-low/H-high 定义；
- 不在 B 上拟合 K-means；
- 使用与 A/W03 完全一致的 PyRadiomics 配置；
- 最终仅保留冻结的 R_low=49 与 R_high=10；
- W_Original 直接复用既有 B 资产，不重新提取。

完成特征表、hash 与 provenance 审核并冻结 `FT05_B_feature_manifest.json` 后，FT05B 才可读取 B DFS/outcome。

因此 FT-B 的单向顺序为：

**A model freeze → B outcome-blind technical generation → B feature freeze → B outcome unlock → frozen model prediction → evaluation**

---

# 六、简化串行工作流

## FT00 — Isolation & Protocol Freeze

完成：

- FT 独立 branch/worktree/output；
- L9 隔离检查；
- baseline HEAD；
- M0–M5；
- frozen 5-fold；
- alpha=1；
- λ 规则；
- endpoints；
- comparisons；
- B lock。

产物：

- `FT00_protocol.json`
- `FT00_isolation_audit.md`

Reviewer PASS → FT01。

---

## FT01 — A Asset & Full_A Habitat Audit / B Asset-State Registration

一次性审核：

### A

- full_A habitat；
- centers/boundary；
- `n_init=100`；
- C/H/G；
- R_low49；
- R_high10；
- W_Original（仅全瘤 Original 特征）；
- existing feature matrices。

### B

此阶段仅允许审核**不涉及 B outcome 的技术资产/provenance**，不得读取 B DFS。

确认：

- B W_Original 既有资产的 schema、顺序和 provenance；
- B R_low/R_high 尚未生成，登记为 `NOT_YET_GENERATED`；
- B habitat radiomics 将在 FT04 模型冻结后按 A-full 定义首次生成；
- 当前未读取 B DFS/outcome，未运行任何 B 影像级处理。

产物：

- `FT01_asset_manifest.json`
- `FT01_asset_audit.md`

FT01 分项结论固定为：

- `FT01_A = PASS`
- `FT01_B_habitat_assets = NOT_YET_GENERATED`
- `FT01_overall = PARTIAL_PASS`

B habitat 资产尚未生成不阻断 A-only 的 FT02–FT04。A 审核通过后，允许直接进入 FT02；在 FT04 冻结 `FT_model_freeze_lock.json` 前不得启动 FT05A。

---

## FT02 — Modeling Runner & Technical Validation

本阶段及其审计均为 A-only，不读取或生成任何 B 数据。

实现：

- M0–M5；
- Cox；
- LASSO-Cox；
- imputation；
- NZV；
- correlation reduction；
- scaling；
- frozen 5-fold；
- λ selection；
- risk prediction；
- paired eligibility；
- metrics。

完成 synthetic/regression tests。

产物：

- scripts/tests；
- `FT02_technical_audit.md`

Reviewer PASS → FT03。

---

## FT03 — A Modeling & Internal Validation

完成全部 M0–M5：

- ordinary 5-fold；
- λ selection；
- CV predictions；
- C-index；
- AUC；
- Brier；
- calibration；
- KM；
- DCA；
- bootstrap；
- paired comparisons。

禁止 post-hoc：

- 改 λ；
- 改 split；
- 改 features；
- 改模型。

产物：

- `FT03_A_validation.json`
- `FT03_A_validation_report.md`

Reviewer PASS → FT04。

---

## FT04 — Full_A Final Refit & Freeze

使用全部 A 重拟合 M0–M5。

冻结：

- cohort；
- habitat；
- features；
- preprocessing；
- λ；
- coefficients；
- risk formula；
- cutoff；
- endpoint；
- B evaluation code；
- Git commit；
- environment。

核心产物：

`FT_model_freeze_lock.json`

Reviewer PASS 后模型永久冻结。

---

## FT05 — B Technical Generation & Outcome Unlock

FT05 保留一个模块名称，内部严格分为 FT05A 与 FT05B。

### FT05A — B Technical Generation

前提：FT04 已通过 Reviewer，且 `FT_model_freeze_lock.json` 已冻结。

执行期间 B DFS/outcome 继续锁定。仅允许：

- 使用冻结的 A-full habitat definition；
- 将 B supervoxel 直接投影到 A 的 H-low/H-high 定义；
- 使用与 A/W03 完全一致的 PyRadiomics 配置；
- 一次性、首次、outcome-blind 提取 B habitat radiomics；
- 最终仅保留冻结的 R_low=49 与 R_high=10；
- 核验 B patient ID、重复患者、feature names/order、candidate hash、配置 provenance 和完整性；
- 复用现有 B W_Original，不运行 whole-tumor extraction。

禁止：

- 在 B 上拟合 K-means；
- 读取 B outcome；
- 改变 PyRadiomics 参数；
- 提取非必要 whole-tumor features；
- 重复患者或重复 extraction；
- checkpoint/resume 重算已完成病例；
- 与 formal 目录混写；
- 根据 B 特征分布或后续验证结果重新优化、重复提取或重跑。

#### FT05A 运行前代码审计

正式运行前必须由独立 `GPT-5.6 Sol`、`Medium thinking` 审计：

- 是否调用 A-full frozen boundary；
- 是否存在 B K-means fit；
- 是否读取 B outcome；
- 是否改变 PyRadiomics 参数；
- 是否提取非必要 whole-tumor features；
- 是否存在重复患者或重复 extraction；
- checkpoint/resume 是否会导致重复计算；
- 是否与 formal 目录混写。

审计结论仅 `PASS` 或 `PASS_WITH_FINDINGS` 可放行。该阶段属于预计长时间运行任务时，启动前须按 `AGENTS.md` 先进行小样本估时，并遵守单次进度检查与产物核验规则。

FT05A 产物：

- `FT05_B_feature_manifest.json`
- `FT05A_B_technical_generation_audit.md`
- `FT05A_code_audit.md`

### FT05B — B Outcome Unlock

仅当以下条件全部满足后才能读取 B DFS/outcome：

- B feature table 完整；
- `FT05_B_feature_manifest.json` 已冻结；
- feature names/order 与冻结模型输入一致；
- R_low/R_high candidate hash 通过；
- PyRadiomics 配置及全流程 provenance 通过；
- 无重复患者、重复 extraction 或 formal 目录混写。

随后建立 FT 专用 outcome access 记录，并仅为 FT06 解锁 B DFS/outcome。

FT05B 产物：

- `FT_B_access_amendment.md`
- `FT_B_unlock.json`
- `FT05B_outcome_unlock_audit.md`

Reviewer PASS → FT06。

---

## FT06 — B External Validation & Final Review

所有 M0–M5：

**只 predict，不 fit。**

不得调 λ、筛特征、调 cutoff、重做 habitat 或重提 radiomics。

完成：

- Uno/Harrell C-index；
- 3/5-year AUC；
- 3/5-year Brier；
- calibration；
- KM；
- DCA；
- bootstrap CI；
- paired comparisons；
- A/B model ranking comparison。

产物：

- `FT06_B_validation.json`
- `FT06_B_validation_report.md`
- `FT06_final_summary.md`

最终结论：

- `FT-POSITIVE`
- `FT-PROMISING`
- `FT-INCONCLUSIVE`
- `FT-NEGATIVE`
- `HOLD`

无论结果如何不得修改正式 L9。

---

## FT07 — FT vs Formal L9 Concordance

仅在正式 L9 完成后进行。

比较：

- model ranking；
- M3L vs M3H；
- M4 vs M5；
- ΔC-index / ΔAUC；
- feature selection；
- A/B generalization。

FT07 不属于本次快速验证完成的必要条件。

---

# 七、执行顺序

`FT00`
→ Review
→ `FT01 (A PASS / B NOT_YET_GENERATED)`
→ `FT02`
→ Review
→ `FT03`
→ Review
→ `FT04`
→ **FT MODEL FREEZE**
→ Review
→ `FT05A`
→ **B TECHNICAL GENERATION + FEATURE FREEZE**
→ Review
→ `FT05B`
→ **B OUTCOME UNLOCK**
→ Review
→ `FT06`
→ Final Review

FT01 的 `B NOT_YET_GENERATED` 是预定状态，不触发停止。其余任一 Gate 不通过：

`STOP / FAIL CLOSED`

---

# 八、明确禁止事项

执行智能体不得：

- 干扰正在运行的 L9；
- 重新优化 full_A habitat；
- 重新筛选 R_low/R_high；
- 在全 A 做 DFS-based univariate screening；
- 根据性能换 split；
- 根据性能改 λ；
- 删除表现差的模型；
- FT05B 前读取 B outcome；
- FT04 模型冻结前运行 B habitat 技术处理；
- 在 B 上 fit；
- 在 B 上重新 K-means；
- 超出 FT05A 许可进行 B habitat radiomics 重复提取；
- 为 B 重新提取 W_Original 或其他 whole-tumor radiomics；
- 根据 B 结果重新优化或重跑 B habitat/radiomics；
- 根据 B 调 features/λ/cutoff；
- 根据 B 修改 A 模型；
- 将 FT freeze 冒充正式 `model_freeze_lock.json`。

---

# 九、完成标准

FT00–FT06 全部完成且满足：

1. M0–M5 A 分析完整；
2. FT model freeze 完成；
3. FT05A 仅在 A 模型冻结后运行，并通过独立 Sol-Medium 代码审计；
4. B habitat radiomics 在 outcome-blind 条件下完成唯一一次首次提取；
5. B W_Original 直接复用既有 107-feature 资产；
6. `FT05_B_feature_manifest.json` 完整且 hash/provenance 审核通过；
7. B outcome 只在 B feature freeze 后解锁；
8. M0–M5 全部直接 external prediction，无 fit 或调参；
9. 无 B→A feedback；
10. L9 未受影响；
11. Final Reviewer 非 HOLD。

即认为 FT 主任务完成。
