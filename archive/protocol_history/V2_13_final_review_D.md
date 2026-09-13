# V2-13 Final Scientific Release Review D

## 审查结论

本复审独立核对当前 `main` 的目标提交 `f1290934f71258670298c8ca768922a3e1956979`、其父提交 `98a7c26788a7f35cf3c7703ee19b7b919993d61c`、Worker D 的 `V2_13_final_scientific_audit.md`、V2-00～V2-12 审查记录、Primary v2 合同与方案书、项目状态文档、归档引用及两个 immutable tags。

Primary v2 的科学身份和方法边界核对通过：当前只有一个活动的 Primary v2 科学合同；M0–M5、固定 full-A habitat、A-only training-only 验证、B frozen prediction only 和 post-FT disclosure 均保持一致。Worker D 对以下两个阻断的判断也被独立复现：

1. Windows 工作树的 `core.autocrlf=true` 使 `protocol.json` 的工作树字节为 CRLF，而 manifest、canonical lock 和 external registration 绑定的是 Git LF blob 的 SHA-256；当前真实验证器按原始字节计算，因此 provenance gate 确实失败。
2. 方案书第二十一部分要求“只有 `main` 为长期主分支”，但当前仍存在历史本地和远程 `codex/*` refs，严格完成定义未满足。linked worktree 分支保留本身可作为安全性的非阻断处理，但当前远程历史 refs 仍在，不能把严格条件改写为通过。

因此当前状态不能作为正式 downstream handoff 或“整改完成”放行。

## 审查边界与状态锚点

本复审未读取 `prognosis_analysis/output/`、`habitat_analysis/output/`、`feature_extract/output/`、原始影像、ROI、临床/病理/预后原始表、患者级特征/预测/分析结果或 `local_private/image_id_mapping.csv`；未执行患者级 A/B 分析、FT03/FT04/FT06 重算或真实结局评价。

两个归档 refs 均保持 annotated tag 类型，peeled commits 为：

- `archive/formal-nested-cv-v1-20260913` → `b09306182e072d0d913d8820d849b4da54d7f1ba`
- `archive/ft-validation-v1-20260913` → `3c1eb3b702831a17f2265ba0ce42d7ce3ddf3d34`

Worker D 审计的实质结论大体准确，但其“当前 HEAD”状态锚点仍写为 `98a7c26`；该值是审计文件提交前的父提交，不是当前目标 `f129093`。本复审以 `f129093` 的实际提交树和当前 refs 为准。

## 逐项结果

| 项目 | 结果 | 证据与下游影响 |
|---|---|---|
| 1. Scientific identity | **PASS** | `prognosis_analysis/primary/protocol.json` 固定 `PRIMARY_ANALYSIS_V2`、version `2.0` 和活动合同状态；Primary README、根 README、`PROJECT_STATUS.md`、`archive_reference.md` 及归档 README 均把 Primary v2 作为当前主线，并将 Formal v1/FT 标为 superseded 或 historical-only。根目录科学主协议和上游 SOP 是方法文档，不构成第二个活动 Primary v2 protocol。未发现 Formal v1 或 FT 仍作为当前 Primary 输入入口。 |
| 2. No performance-driven redesign | **PASS** | protocol、方案书和 transition record 均保留 M0–M5、`R_low=49`、`R_high=10`、`W_Original=107`，并记录 `performance_driven_model_redesign=false`、`retain_all_M0_M5=true`。活动 Primary 代码没有以 FT06 性能结果选择模型、删减候选池、改变 alpha/lambda 或重构候选集合。下游解释仍须保留“post-FT decision”，不能改写为 B 结果未知时的事前预指定。 |
| 3. B integrity | **PASS（科学边界）** | protocol 的 B allowed sequence 与 forbidden actions、`validate_external.py` 的 B gate/runtime identity 检查，以及 `run_cv.py` 的 A-only 入口均禁止 B feature selection、lambda tuning、coefficient refit、cutoff optimization、habitat refit、radiomics candidate re-selection 和 B→A feedback。当前 gate 会先因 protocol hash mismatch 阻断，属于第 9 项技术发布阻断，不改变未发现 B-guided refitting/tuning 路径的结论。 |
| 4. Fixed phenotype | **PASS** | protocol 和 `validate_protocol` 固定 full-A habitat、3D SLIC 4 mm、cross-case K-means `K=2`、`n_init=100`，并禁止 CV outer fold、B 和 DFS-based boundary adjustment 重拟合；`fit_outer_cv` 使用同一固定输入，不重建 habitat。下游模型比较共享同一个固定 phenotype。 |
| 5. A validation isolation | **PASS** | protocol、`validate_assets.py` 和 `run_cv.py` 固定 repeat-1 single 5-fold，禁止 split regeneration；预处理、feature selection 和 lambda 选择均在 outer-training 数据内，lambda 使用 inner 5-fold，`alpha=1`，outer-validation 不参与选择。核心 synthetic equivalence 输出的 feature order、eligibility、training-only preprocessing、lambda behavior 和 fold metric contract 均为 PASS。 |
| 6. External validation | **PASS（合同边界；当前执行受阻）** | protocol、manifest、lock 和 registration 明确区分技术筛选 B=107 与 FT06 authorized B=163，并固定 B=163 的 cohort identity、冻结模型和 frozen prediction only 顺序。`_validate_b_frame_completeness` 设计上要求实际 B predictor frame 恰为授权 163 行；但当前工作树在进入该 gate 前即因 protocol hash mismatch 失败，所以不能把当前环境称为已完成的可执行外部验证 handoff。 |
| 7. Transparency | **PASS** | transition record、protocol、registration 和 Primary README 均明确 Primary v2 是 post-FT protocol transition，FT03/FT06 结果在 promotion/registration decision 时已可见，`retrospective_prespecification_claim=false`；同时保留“pipeline 在 B evaluation 前冻结”与“提升为正式框架发生在 FT 结果可见后”的区别。 |
| 8. Archive clarity | **PASS（活动科学路径）** | Formal v1、FT development history、repeated 10×5 nested CV、fold-specific habitat reconstruction、R6 remediation 和 FT recovery chain 均被归档为历史材料；README、项目说明和 PROJECT_STATUS 只把 Primary v2 作为当前主线。`run_cv.py` 虽复用通用 Cox/preprocessing 原语模块名，但未调用旧 W08 orchestration、fold-specific habitat reconstruction 或旧 remediation state machine，不构成活动 pipeline 回归。 |
| 9. Technical release integrity | **FAIL** | `git config core.autocrlf=true`；当前 `protocol.json` 为 426 个 CRLF，工作树 SHA-256 为 `db671001c00bbe2eaac1985ebeff1c48f681f99b5a1cb343d0656a23c5dbce3b`；Git LF blob 及 manifest/lock/registration 记录为 `8d0e8239558ad9ecd2f5605bc1ecce29ef93f7769452319c3c804cda20b28e89`。`sha256_file()` 按原始字节计算，故 `validate_evidence_manifest` 和 canonical lock gate 真实失败；针对 B completeness、registration builder self-consistency 和 complete-B evaluation 的三个 synthetic tests 分别在该上游 gate 处失败。主 synthetic wrapper 的 PASS 不能掩盖这些失败；仅在内存中做 CRLF→LF 的诊断归一化也不能作为当前工作树正式验证。 |
| 10. V2-12 branch completion | **FAIL** | `archive_reference.md` 将 `main` 声明为 active long-term branch，当前 checkout 也是 `main`；但方案书第二十一部分的严格条件是只有 `main` 为长期主分支。当前仍有本地 `codex/l7-current-code-technical-preflight`、`codex/w00-formal-archive` 以及多个远程历史 `origin/codex/*` refs。两个本地分支被 linked worktree 占用，保留它们可视为非阻断的保守操作；但远程历史 refs 仍存在，因此整体严格完成定义仍为 FAIL。 |
| 11. Protected equivalence | **NOT EVALUATED** | canonical lock 明确 `coefficients_available_in_promoted_record=false`、`coefficient_verification=requires protected runtime verification`；当前 synthetic output 和既有 B/C 复审均将 FT04 coefficients、risk predictions、metrics 的跨记录 numerical equivalence 保持为 `NOT EVALUATED`。本复审未访问 protected runtime fixture，不宣布数值等价完成。 |

## 运行核对摘要

在项目锁定环境中执行了 `prognosis_analysis/primary/test_equivalence.py` 及其 8 个 synthetic test functions：核心 synthetic equivalence、metadata/cohort/runtime negative tests 和 required-gate negative test 保持通过；B completeness、registration builder self-consistency、complete-B evaluation 三项因当前 protocol hash mismatch 失败。失败发生在真实 validator 的 manifest/lock provenance gate，而不是 monkeypatch、伪造 runtime state 或患者级数据路径。

V2-00～V2-12 记录的科学边界、归档事实和隐私边界与当前树一致；V2-03～V2-07 最终记录已明确 pytest 未安装和 protected FT04 numerical equivalence 未评估，不能在本次复审中改写。

## 下游影响与必要状态

Primary v2 可以继续作为当前唯一正式科学基线，但当前不能宣称技术 release 完成、外部验证 handoff 可执行或方案书第二十一部分已全部满足。后续若获得独立修复授权，应处理跨平台 provenance 字节一致性并重新运行受影响的 manifest/lock/registration/final-report validators 与 synthetic tests；另需按项目策略处理历史 refs。不得在此过程中伪造或复制 FT04 protected coefficients、risk predictions、metrics，也不得把第 11 项改写为 PASS。

## Semantic disposition

**not accepted for downstream use**

本复审只新增本文件；未修改被审查文件、canonical protocol、manifest、model lock、external registration、活动代码、分支、tag 或远程 refs，未推送远程。
