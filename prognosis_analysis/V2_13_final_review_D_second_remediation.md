# V2-13 Final Scientific Release Review D — second remediation

## 审查对象与边界

本复审以当前 `main` HEAD `d527131` 为目标，独立核对 Worker E provenance 修复提交 `b0c8262`、Worker F 分支状态透明性提交 `d527131`、V2-13 Worker 审计 `f129093`、前一轮 Reviewer D 记录 `2bd2c4a`/`d3b18d5`、V2-08～V2-12 Reviewer C 记录 `98a7c26`，以及当前 Primary v2 合同、活动代码、归档引用和 Git refs。

本复审未读取 `prognosis_analysis/output/`、`habitat_analysis/output/`、`feature_extract/output/`、原始影像、ROI、临床/病理/预后原始表、患者级特征/预测/分析结果或 image ID mapping；未执行患者级 A/B 分析、FT03/FT04/FT06 重算或真实结局评价。未修改被审查的代码、JSON、README、PROJECT_STATUS、归档文件、分支或远程 refs；未删除 linked worktree；未推送远程。

## Semantic disposition

**accepted for downstream use with non-blocking findings**

## 复审结论

当前 Primary v2 的科学合同与真实可执行技术 gate 均满足下游使用要求。Primary v2 仍是唯一正式科学基线。受保护 FT04 coefficients、risk predictions 和 metrics 的跨记录数值等价性未被本复审评估，继续透明记录为 `NOT EVALUATED`，不将其伪称为通过。

## Provenance 与真实 gate

1. `.gitattributes` 由 Worker E 提交精确加入以下四条规则，且没有科学内容变更：

   ```text
   prognosis_analysis/primary/protocol.json text eol=lf
   prognosis_analysis/primary/PRIMARY_V2_EVIDENCE_MANIFEST.json text eol=lf
   prognosis_analysis/primary/model_freeze_lock.json text eol=lf
   prognosis_analysis/primary/external_validation_registration.json text eol=lf
   ```

2. 四个活动 JSON 均成功 JSON parse，原始字节均为纯 LF（CRLF=0）。`protocol.json` 原始字节 SHA-256 为 `8d0e8239558ad9ecd2f5605bc1ecce29ef93f7769452319c3c804cda20b28e89`，与 `PRIMARY_V2_EVIDENCE_MANIFEST.json` 的 `protocol_sha256` 一致。

3. 在锁定的 `t2_radiomics` 环境、未 monkeypatch、未换行归一化替代的条件下，以下真实 gate 均通过：

   ```text
   validate_evidence_manifest: PASS
   validate_canonical_lock: PASS
   validate_external_registration: PASS
   final_report.build_final_report: PASS
   ```

4. Primary v2 六个 Python 模块均 AST parse 通过；`git diff --check`、暂存区 diff check 以及 Worker E/F 提交自身的 diff check 均通过。

## Synthetic equivalence 与 fail-closed 行为

主 wrapper `prognosis_analysis/primary/test_equivalence.py` 在锁定环境中退出码为 0。其可评估检查均为 `PASS`：feature order、eligibility、training-only preprocessing、lambda-selection behavior、canonical coefficient repeatability 和 canonical fold metric contract；cross-artifact coefficients、risk predictions、metrics 均明确为 `NOT EVALUATED`。

全部 8 个 synthetic test functions 逐一调用并通过：

```text
test_synthetic_equivalence: PASS
test_fail_closed_promotion_metadata: PASS
test_synthetic_cohort_identity_boundaries: PASS
test_b_frame_completeness_is_bound_to_ft06_denominator: PASS
test_external_registration_builder_is_self_consistent: PASS
test_synthetic_runtime_model_identity_gate: PASS
test_evaluate_frozen_predictions_requires_complete_b_gate: PASS
test_evaluate_frozen_predictions_accepts_only_complete_b_frame: PASS
SUMMARY 8/8 PASS
```

这些检查未读取患者级材料；synthetic B frame 只验证固定 schema、完整性、身份绑定和 frozen-prediction gate。

## 科学边界核对

- 当前只有一个活动 Primary v2 protocol：`PRIMARY_ANALYSIS_V2`，version `2.0`；Formal v1 和 FT validation v1 均明确为 archived/historical，不作为当前分析入口。
- M0–M5 全部保留且顺序未改变；未发现由 FT03/FT06 性能驱动的模型删除、候选池重选、alpha/lambda 改写或冠军模型升级。
- 表型固定为 full-A、3D SLIC 4 mm、cross-case K-means `K=2`、`n_init=100`；CV outer fold、B 和 DFS-based boundary adjustment 不重拟合 habitat。
- A 验证固定为 repeat-1 single 5-fold；预处理、特征选择和 lambda 选择均为 training-only，LASSO `alpha=1`，lambda 在 outer-training 内部 5-fold 中选择。
- B 只允许 `load frozen model → load frozen-compatible B predictors → predict → evaluate`；FT06 authorized B=163（42 events、121 censored）与技术筛选参考 B=107 明确分开，不合并、不静默替换。
- Primary v2 明确为 post-FT protocol transition：FT03/FT06 结果在 promotion decision 时已可见，`retrospective_prespecification_claim=false`；同时保留 B evaluation 前模型冻结的时间边界。

## FT04 受保护等价性

`model_freeze_lock.json` 继续声明 `coefficients_available_in_promoted_record=false`、`coefficient_verification=requires protected runtime verification`，且不复制 patient-level coefficients 或 predictions。本复审未读取 protected FT04 runtime fixture，因此以下三项保持 `NOT EVALUATED`：

- FT04 coefficients 跨记录数值等价性；
- FT04 risk predictions 跨记录数值等价性；
- FT04 metrics 跨记录数值等价性。

## V2-12 分支与归档状态

`prognosis_analysis/archive_reference.md` 已明确：`main` 是唯一 active long-term branch，Primary v2 是唯一 active scientific protocol；`codex/l7-current-code-technical-preflight` 与 `codex/w00-formal-archive` 仍被 linked worktree 占用，远程 `origin/codex/*` refs 是 historical references only。这些 refs 未被删除，也不应被解释为第二条 active analysis route。

在用户明确的“不得删除 linked worktree/远程 refs”安全边界下，上述保留属于可逆、非活动的仓库清理例外，不阻断 Primary v2 科学放行，也不改变其唯一正式科学基线地位。

## 提交范围与数据边界

- Worker E `b0c8262` 只新增四条精确 LF 属性规则；四个活动 JSON 的科学字段未变化。
- Worker F `d527131` 只新增 `prognosis_analysis/archive_reference.md` 的分支/历史引用透明性说明；未修改活动代码、JSON 或分析参数。
- 当前工作区的未跟踪 Primary v2 方案书与 `_codex_ft_run_*` transition contracts 仍保持未提交；未被本复审纳入。
- 当前 tracked diff 为空，状态中没有患者级材料、outputs、绝对本机路径或密钥；本次只新增本审查记录。

## 审查框架参考

本记录采用科学方法学、训练/验证隔离、偏倚风险和证据边界的结构化审查框架：Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents* (arXiv version 2). https://doi.org/10.48550/arXiv.2609.00065
