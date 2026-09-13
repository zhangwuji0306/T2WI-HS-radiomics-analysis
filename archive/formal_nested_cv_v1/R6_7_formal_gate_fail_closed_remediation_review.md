# R6-7 formal release gate fail-closed remediation 独立审查

## 结论

**ACCEPT**

本轮修复真实解决了上一轮 blocker。`_git_commit_file_exists` 现在只在已验证的 commit 中没有精确匹配路径时返回 `False`，对精确 blob 返回 `True`；非 blob、无效 commit、Git 命令失败、进程启动错误、UTF-8 解码失败和非法列表记录均拒绝。A/M successor 状态严格由 execution snapshot 中两个固定 evidence 路径的共同存在性决定。

## Blocker

无。

## Non-blocker

无。

## 独立核查结果

- 基线 `HEAD` 为 `b48d5ccb0a543d668fdadf5a69fe6344b533de6b`。Worker tracked diff 仅修改 `prognosis_analysis/scripts/w08_formal_run_a.py` 和 `tests/test_w08_formal_release_gate.py`；上一轮 `prognosis_analysis/R6_7_formal_gate_M_successor_remediation_review.md` 保留为未跟踪历史审查记录。
- `_git_commit_resolves` 使用 40 位 commit 值和 `rev-parse --verify <commit>^{commit}` 校验对象类型与精确解析值。helper 在该校验通过后才执行 `git ls-tree -z --full-tree <commit> -- <relative_path>`。
- `ls-tree` 记录按 NUL 分隔、按 tab 分离 metadata/path，且只接受与请求路径完全相等的 `blob`。无精确匹配记录才返回 `False`；精确 `tree` 抛出 `RuntimeError`。
- `subprocess.CalledProcessError` 和 `OSError` 被转换为 `RuntimeError`；`UnicodeDecodeError` 也被明确拒绝，不再将 Git 失败误判为路径 absent。
- execution snapshot 中两个 allowlisted evidence 路径均 absent 时，successor diff 必须精确为两条 `A`；均为 blob 时，必须精确为两条 `M`。混合 presence、混合 A/M、缺失 allowlisted 路径、额外路径、delete 和 rename 均被拒绝。
- evidence commit 仍必须是 execution commit 的 direct child。current HEAD 仍只能是 evidence commit，或其仅修改两个 evidence 文件的 direct-child finalization commit；`successor_mode` 必须与实际拓扑一致。
- 精确 allowlist、clean worktree、current evidence 与 current HEAD 字节一致、protected manifest、compatibility provenance、R5 frozen bindings、G3/P4R、technical freeze、B flags 和 model-freeze absent 检查未被放宽。
- diff 未改变科学、技术、统计、建模参数，也未改动冻结输入、P4R 或 B 边界。

## 验证结果

- `python -m unittest tests.test_w08_formal_release_gate -v`：**40 tests passed**。
- `python -m compileall -q prognosis_analysis/scripts/w08_formal_run_a.py tests/test_w08_formal_release_gate.py`：**PASS**。
- `git diff --check b48d5ccb0a543d668fdadf5a69fe6344b533de6b -- prognosis_analysis/scripts/w08_formal_run_a.py tests/test_w08_formal_release_gate.py`：**PASS**。
- 实际 `git ls-tree -z --full-tree HEAD -- <path>` 格式抽查确认：文件返回 `blob` 记录，absent 路径返回空结果，目录返回 `tree` 记录，与 helper 解析逻辑一致。

## 主控提交与后续边界

**允许主控提交。** 新的 execution code commit 应一并纳入本轮代码、测试、本轮审查报告和上一轮审查报告。提交后必须重新执行与当前代码 commit 绑定的 P5 technical-only preflight，再重建 R5 evidence successor/finalization。

本次 ACCEPT 不允许直接启动 formal W08。Worker 的只读 gate `HOLD` 不等于 formal W08 放行；只有新 execution commit 对应的 P5/R5 证据链完成并通过当前 release gate 后，才能由主控根据协议决定后续执行。
