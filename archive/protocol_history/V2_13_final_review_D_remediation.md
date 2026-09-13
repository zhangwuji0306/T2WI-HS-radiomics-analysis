# V2-13 Final Scientific Release Review D — line-ending/provenance remediation

## Semantic disposition

**not accepted for downstream use**

## 审查结论

本复审以 `main` 当前 HEAD `b0c82620637d847ced61066877da511a53169e99` 为目标，父提交为 `2bd2c4a`。复审范围仅包括 Worker E 的 line-ending/provenance 补救提交、Primary v2 活动合同与代码、V2-13/V2-12 记录、Git refs/worktrees 及归档引用。未读取患者级输出或受保护 FT04 runtime fixture，未修改任何被审查文件、分支、tag 或远程 refs。

Worker E 提交只新增 `.gitattributes`，四条规则精确覆盖四个活动 Primary v2 JSON，并统一为 LF：

```text
prognosis_analysis/primary/protocol.json text eol=lf
prognosis_analysis/primary/PRIMARY_V2_EVIDENCE_MANIFEST.json text eol=lf
prognosis_analysis/primary/model_freeze_lock.json text eol=lf
prognosis_analysis/primary/external_validation_registration.json text eol=lf
```

当前工作树四个 JSON 均为纯 LF，未发现 CRLF 或孤立 CR；`protocol.json` 为 426 个 LF，manifest 为 149 个 LF，canonical lock 为 117 个 LF，external registration 为 61 个 LF。四个 JSON 在 `2bd2c4a..b0c8262` 间没有 Git 内容差异，科学字段未改变。当前原始字节 SHA-256 为：

```text
protocol.json = 8d0e8239558ad9ecd2f5605bc1ecce29ef93f7769452319c3c804cda20b28e89
```

该值与 `PRIMARY_V2_EVIDENCE_MANIFEST.json` 的 `protocol_sha256`、`model_freeze_lock.json` 的 `Primary_v2_protocol_hash` 以及 `external_validation_registration.json` 的 `protocol_sha256` 一致。

## 真实 gate 与合成验证

在锁定的 `t2_radiomics` 环境中，真实 gate 均通过：

- `validate_evidence_manifest`: `True`
- `validate_canonical_lock`: `True`
- `validate_external_registration`: `True`
- `final_report.build_final_report`: 通过，生成聚合报告字符串；未写入 output 目录

`tools/run_t2_radiomics.ps1 -PythonArguments @('-B','prognosis_analysis/primary/test_equivalence.py')` 退出码为 0。主 wrapper 的 feature order、eligibility、training-only preprocessing、lambda selection behavior、canonical coefficient repeatability 和 fold metric contract 均为 `PASS`。

全部 8 个 synthetic test functions 在未 monkeypatch、未进行换行归一化诊断替代的条件下逐一通过：

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

Primary v2 的 6 个 Python 文件 AST parse、4 个活动 JSON parse 和 `git diff --check` 均通过。

## V2-13 科学条件

以下科学条件均保持一致并通过核对：

1. 当前只有一个活动 Primary v2 protocol：`PRIMARY_ANALYSIS_V2`，version `2.0`；Formal v1 与 FT 仅作为 historical/archive material，未作为当前 Primary 输入入口。
2. 保留完整 M0–M5，未发现由 FT06 性能驱动的模型删除、变量重选、candidate pool 改写或 alpha/lambda 改写；固定候选规模仍为 `R_low=49`、`R_high=10`、`W_Original=107`。
3. 表型固定为 full-A、3D SLIC 4 mm、cross-case K-means `K=2`、`n_init=100`；CV outer fold 与 B 阶段均不重拟合 habitat。
4. A 验证固定为 repeat-1 single 5-fold；预处理、特征选择和 lambda 选择均限于 outer-training，LASSO `alpha=1`，lambda 使用 training-only inner 5-fold。
5. B 仅允许 `load frozen model → load frozen-compatible B predictors → predict → evaluate`。FT06 authorized B=163（42 events、121 censored）与技术筛选参考 B=107 明确分开，未合并或静默替换。
6. Primary v2 promotion 明确为 post-FT transition：FT03/FT06 结果在 promotion decision 时已可见，`retrospective_prespecification_claim=false`；B 模型身份在 B evaluation 前冻结。

## FT04 protected equivalence

FT04 coefficients、risk predictions 和 metrics 的跨记录 numerical equivalence 仍为 **NOT EVALUATED**。canonical lock 继续声明 `coefficients_available_in_promoted_record=false`、`coefficient_verification=requires protected runtime verification`；本次未访问 protected runtime fixture，也未将该状态改写为 PASS。

## V2-12 branch safety 与下游放行

当前 checkout 为 `main`，且 `prognosis_analysis/archive_reference.md` 将 `main` 记录为 active long-term branch；两个 immutable archive tags 及其历史归档引用仍在。

但当前仍保留：

- 被 linked worktree 占用的本地历史分支 `codex/l7-current-code-technical-preflight`、`codex/w00-formal-archive`；
- 远程历史 `origin/codex/*` refs，包括 `origin/codex/ft-validation`、`origin/codex/w08-nested-cv`、`origin/codex/w08-preflight-blocked`、`origin/codex/w08-coxph-remediation`、`origin/codex/p0-pre-w08-baseline`、`origin/codex/l7-current-code-technical-preflight`、`origin/codex/r2-w08-formal-release-gate`、`origin/codex/g2r-w00b-reader-remediation` 等。

方案书 V2-12 明确要求在 evidence/tag 可恢复后删除历史 codex 分支；V2-13 完成定义进一步写明“Formal v1 和 FT 均归档；只有 main 为长期主分支”。因此，虽然这些 refs 只涉及可逆历史引用和仓库卫生，不影响当前科学协议或上述真实执行 gate，但严格的 V2-12 completion condition 仍未满足。考虑到 linked worktree 与远程 refs 的安全边界，本复审不删除它们，也不把该条件伪称为通过；该未满足项足以阻断本次严格 downstream release。

结论是：Primary v2 仍是当前唯一活动科学合同，但本次不允许将其作为已经完成 V2-13 严格交付条件的唯一正式 downstream analysis baseline。

## 审查边界与提交边界

本复审未读取 `prognosis_analysis/output/`、`habitat_analysis/output/`、`feature_extract/output/`、原始影像、ROI、临床/病理/预后原始表、患者级特征/预测/分析结果或 `local_private/image_id_mapping.csv`；未执行患者级 A/B 分析、FT03/FT04/FT06 重算或真实结局评价。记录不包含患者标识、原始影像号、绝对本机路径或敏感数据。

本次只新增 `prognosis_analysis/V2_13_final_review_D_remediation.md`，不推送远程。
