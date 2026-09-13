# Primary Analysis v2 Protocol Transition — 2026-09-13

## Decision

Primary Prognostic Analysis v2（Primary v2）自 2026-09-13 起登记为新的正式预后分析方法框架。该决定发生在旧 Formal W08 v1 尚未成功完成之前。

- Formal W08 v1 未成功完成。现有 Formal 记录为 `W08 / HOLD`；最近一次正式运行因 `Elastic-Net Cox fit did not converge` 失败，未生成完整正式结果、最终 W08 manifest 或正式 `model_freeze_lock.json`。
- Formal v1 为 superseded。旧 Formal W08/R5/R6/L0–L7 材料仍由既有归档锚点保留，仅用于历史追溯，不再作为活动主分析协议。
- 换轨理由为 computational feasibility、fixed phenotype interpretability 和 methodological simplicity。
- 本次是方法框架提升与登记，不是重新计算患者级结果，也不是对既有 FT03/FT04/FT06 患者级结果的重跑、改写或重新评价。

本次决定属于 **post-FT protocol transition**。

## 可见性与时间顺序

在决定将 streamlined FT framework 提升为 Primary v2 正式主分析方法时，FT03 A 结果和 FT06 B 外部验证结果已经可见：

- FT03 已完成 A-only fixed repeat-1 ordinary 5-fold 验证，覆盖 M0–M5；其记录的 A 参考队列为 393 例、89 个 DFS events。
- FT06 已完成 B frozen prediction only 验证，授权验证队列为 163 例、42 个 DFS events；最终 FT 状态为 `FT-INCONCLUSIVE`。

因此，本记录不追溯声称 Primary v2 在 B 验证前已经作为正式主分析被预先指定，并明确承认 B 结果在本次决定之前已经可见。准确的时间顺序是：

> The modeling pipeline itself was frozen before external validation. The subsequent decision to adopt this streamlined pipeline as the principal analytic framework was made for computational feasibility, fixed-phenotype interpretability and methodological simplicity.

模型对 B 的验证仍是 frozen external validation；但把该框架提升为论文正式主分析，是在 B 结果已经可见之后作出的项目方法学决策。两者在解释时必须区分。

## 科学合同的连续性

Primary v2 保留原 FT 科学框架中的全部模型和预设比较，不因已观察到的 FT03 或 FT06 表现重新设计：

- M0–M5 全部保留；不得把某个模型事后升级为唯一 primary model。
- `R_low=49`、`R_high=10` 和 `W_Original=107` 保持冻结。
- 使用固定 full-A habitat：3D SLIC 4 mm、cross-case K-means、K=2；不在 CV fold 或 B 中重拟合 habitat。
- 高维模型固定 `alpha=1`；lambda 只能在外层训练数据内部通过 training-only CV 选择。
- B 不再用于新的 tuning、feature selection、coefficient refit、cutoff optimization、habitat refit 或任何 B→A 反馈。

具体合同见 [prognosis_analysis/primary/protocol.json](prognosis_analysis/primary/protocol.json) 和 [prognosis_analysis/primary/README.md](prognosis_analysis/primary/README.md)。

## V2-00 — Freeze current history

以下只读核对在当前工作区完成，未创建、切换或删除任何 ref：

| 项目 | 已核对事实 |
|---|---|
| current `main` HEAD | `b09306182e072d0d913d8820d849b4da54d7f1ba` |
| `codex/primary-v2-transition` HEAD | `b09306182e072d0d913d8820d849b4da54d7f1ba`，与当前 `main` 相同 |
| `archive/formal-nested-cv-v1-20260913` | annotated tag；peeled commit 为 `b09306182e072d0d913d8820d849b4da54d7f1ba`，与 `main` HEAD 相同 |
| current `codex/ft-validation` HEAD | `3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34` |
| `archive/ft-validation-v1-20260913` | annotated tag；peeled commit 为 `3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34`，与 FT 分支 HEAD 相同 |
| old Formal state | `W08 / HOLD`；最近一次 formal W08 失败；正式最终输出和正式 model freeze 不存在 |
| FT final state | FT00–FT06 已完成相应记录；FT06 为 frozen prediction only；最终判定 `FT-INCONCLUSIVE`；FT final audit 为 accepted with non-blocking findings |

两个归档 tag 均可直接定位到换轨前对应的完整历史提交；本模块不执行分支清理、历史归档搬迁或远程推送。

## 已核对的 FT 证据哈希

以下哈希来自 `codex/ft-validation` 当前 HEAD 的既有非患者级 JSON/Markdown 记录；本文件只登记哈希，不复制患者级结果：

| 证据 | 路径 | SHA-256 |
|---|---|---|
| FT03 aggregate JSON | `prognosis_analysis/ft/FT03_A_validation.json` | `1cd71d9309c8ea23aec7ac485f39ff761d25e661a31c9844f3b4cd9c4fd83ec4` |
| FT03 report | `prognosis_analysis/ft/FT03_A_validation_report.md` | `7af68b0c99e042fc9e828b9486ca473d58c52acd9aafcd3afc77a0e0941b21de` |
| FT04 lock payload identity | `prognosis_analysis/ft/FT_model_freeze_lock.json` | `10a2c1fe2de9a36a074a604ea4966537b22cbb7191b8e04a71a1469ac508b56e` |
| FT04 serialized lock file | `prognosis_analysis/ft/FT_model_freeze_lock.json` | `bb0c00b49b68cc31eb3899a9099ca8330551a7c2afd0ff3f849abc091a80c2d2` |
| FT04 lock attestation file | `prognosis_analysis/ft/FT04_lock_sha256.json` | `877800e482b531b3073e290c4bcbf7270d19904d9ff939726b95fca3b69ff30a` |
| FT06 aggregate JSON | `prognosis_analysis/ft/FT06_B_validation.json` | `0ab1af7a60e63d8d18e30e4db965757b27fefffad7df7e6ea3803f590bdb6583` |
| FT06 report | `prognosis_analysis/ft/FT06_B_validation_report.md` | `8a2dbc4a233085a1442aa5c7c384926a9d3383e52d49733e546eb3aceaaccba1` |

## 交付边界

本次登记不改变原始影像、ROI、临床/病理/预后表、患者级特征、分析输出或任何 A/B 访问锁；不运行真实影像、临床或长时建模任务。后续 Primary v2 实现必须以本模块生成的科学合同为准，并继续保持 A/B 隔离、provenance binding、fail-closed validation 和患者隐私边界。
