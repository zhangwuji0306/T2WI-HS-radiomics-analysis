# R6-7 formal release gate successor-compatibility remediation 独立审查

## 结论

**REJECT**

当前实现正确区分了 execution commit 中两个固定 evidence 路径“均不存在”与“均为 blob”时的 A/M 预期状态，并保留了 direct-child、精确 allowlist、clean worktree、finalization-only、`successor_mode`、G3、P4R、B flags 和 model-freeze 等既有边界。但新增的 Git 路径存在性判断没有对 Git 命令错误 fail closed，当前状态不得作为 formal release gate 的可接受实现提交。

## Blocker

### B1. `_git_commit_file_exists` 将所有 Git 非零退出解释为路径不存在

`_git_commit_file_exists` 对 `subprocess.CalledProcessError` 直接返回 `False`。这无法区分“指定路径在已解析 commit 中不存在”和仓库读取失败、对象损坏、权限或其他 Git 异常。

当两个固定路径的查询均因同一 Git 异常失败时，`execution_presence` 会成为 `[False, False]`，validator 随即选择 A 模式；若 successor diff 恰为两条 A 记录，其余绑定满足条件，错误状态可被接受。这违反 release gate 的 fail-closed 要求。

只读定向核验结果：mock `subprocess.check_output` 抛出 exit 128 的 `CalledProcessError` 时，`_git_commit_file_exists` 返回 `False`。

修复应只把可证实的“该固定路径在已解析 execution commit 中不存在”映射为 `False`；Git 命令异常必须抛出 `RuntimeError`。非 blob 对象必须继续拒绝。

## Non-blocker

### N1. helper 自身的 fail-closed 测试缺失

successor fixture 将 `_git_commit_file_exists` 整体 mock，因此当前测试没有覆盖：

- 路径不存在返回 `False`；
- blob 返回 `True`；
- tree 或其他非 blob 对象被拒绝；
- Git 非零退出被拒绝；
- Git 可执行文件或进程启动错误被拒绝。

应补充 helper 级测试，确保 B1 修复不会回归。

### N2. A/M 混合 diff 缺少显式测试

精确列表比较在当前实现中会拒绝 A/M 混合记录，但测试集没有独立覆盖这一指定负例。建议分别对 A successor 和 M successor 至少保留一个混合状态拒绝用例。

## 已确认边界

- 变更仅位于 `prognosis_analysis/scripts/w08_formal_run_a.py` 和 `tests/test_w08_formal_release_gate.py`。
- execution commit 中两个固定路径均不存在时，预期 diff 严格为两条 A；两者均存在且为 blob 时，预期 diff 严格为两条 M；混合存在会拒绝。
- successor diff 使用精确集合比较，额外路径、缺失路径、delete、rename 展开记录及错误状态不会被接受。
- evidence commit 仍必须是 execution commit 的 direct child。
- current HEAD 仍只能是 evidence commit，或其仅修改两个 evidence 文件的 direct-child finalization commit；`successor_mode` 必须与该拓扑一致。
- clean worktree、当前文件与 current HEAD 字节一致、protected manifest、compatibility provenance、frozen bindings、G3/P4R、B flags 和 model-freeze 检查未被本次 diff 削弱。
- 本次变更不涉及科学、技术、统计、建模参数、冻结输入、P4R、B 或 formal W08 执行。
- 任何只读 gate HOLD 结果均不是 formal 放行。

## 验证结果

- 基线 HEAD：`b48d5ccb0a543d668fdadf5a69fe6344b533de6b`
- `python -m unittest tests.test_w08_formal_release_gate -v`：**33 tests passed**
- `python -m compileall -q prognosis_analysis/scripts/w08_formal_run_a.py tests/test_w08_formal_release_gate.py`：**PASS**
- `git diff --check`：**PASS**

测试通过不能覆盖 B1，因为相关测试 mock 了存在性 helper，未执行其错误分支。

## 放行条件

1. 修复 B1，使 Git 异常与路径不存在可可靠区分，并对 Git 异常 fail closed。
2. 补充 N1 所列 helper 级测试及 A/M 混合 diff 负例。
3. 在锁定环境重新运行本报告列出的 unittest 与 compileall 检查，并进行新一轮独立审查。

