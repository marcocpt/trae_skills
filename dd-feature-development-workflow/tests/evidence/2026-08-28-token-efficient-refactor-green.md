# 绿测证据：2026-08-28 dd-feature-development-workflow token-efficient refactor

> 本文件记录**实际运行**的绿测输出。禁止预填或伪造；任何新增条目必须来自真实命令执行。

## 环境

- 日期：2026-08-28
- branch：`develop`
- 说明：本重构已按每任务粒度 commit，当前 HEAD 为最终实现提交。
- 工具：`python3` (`/opt/homebrew/bin/python3`)，`unittest` 标准库
- 注：`rg` 未安装，扫描以 `grep -R` 等价替代（语义一致）。

## 1. 确定性全套验证（Task 7 Step 2）

命令与退出码：

```bash
python3 -m unittest dd-feature-development-workflow/tests/test_feature_workflow_contracts.py   # OK (8 tests)
python3 -m unittest dd-workflow-runtime/tests/test_ci_contracts.py                            # OK (9 tests)
python3 -m unittest discover -s dd-workflow-runtime/tests -p 'test_*.py'                       # OK (131 tests)
python3 dd-workflow-runtime/agents/validate-bindings.py                                        # bindings OK: 6 hosts / 7 roles
python3 dd-workflow-runtime/agents/validate-review-routing.py                                  # review routing OK: 5 backends / 1 roles
git diff --check                                                                               # clean
```

全部退出码 0，未标 PASS 项都有真实命令输出。

## 2. 链接 / 重复 / 红线扫描（Task 7 Step 3）

- 红线扫描命中仅在已 `retired-reference: not-routed` 的旧 reference（`specification-and-planning.md`、`implementation-and-verification.md`）与历史 evidence/baseline 字符串，现行合同命中为零。
- retired-link 扫描：唯一命中为红测 evidence 的历史记录（`test_retired_references_have_no_active_links` 的描述），无 active Router/reference 链接。

## 3. 弱模型绿测（Task 7 Step 4）

状态：`BLOCKED_EVAL_UNAVAILABLE`

原因：当前执行环境只暴露 `code-explorer` 子代理，无法取得全新的弱模型（`luna-worker`）实例对四个 scenario 逐字评测。按计划约束，不得编造模型输出，故标记 `BLOCKED_EVAL_UNAVAILABLE`。

四个 scenario 的正确行为已由 `baseline-7/8/9/10` 冻结，且对应的机械断言已由 contract tests 覆盖（AC-05/07/08/09 与 compact verification）。

## 4. 规模与实际加载集合（Task 7 Step 5）

任务 0 基线 → 当前：

```text
main_skill_bytes_before / after: 11693 / 6451
planning_loaded_bytes_before / after: 6161 / 6800   (planning.md 增加 source_manifest 模板)
phase_loaded_bytes_before / after: 6177 / 5062      (implementation.md 精简)
candidate_loaded_bytes_before / after: (was embedded in implementation-and-verification) / 2235
xcode_ci_loaded_bytes_before / after: 20160 / 9815  (ci.md 通用化) + ci-xcode.md 2875 按需
token_saving_claim: NOT_PROVEN
```

说明：以上仅记录字节观察值；未按计划要求固定模型/请求/允许文件后实测，故 `token_saving_claim=NOT_PROVEN`，不得据此宣称固定 token 降幅。
