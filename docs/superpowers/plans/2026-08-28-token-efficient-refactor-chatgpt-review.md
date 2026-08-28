# ChatGPT 复核送审材料 — dd-feature-development-workflow token-efficient refactor

> 目的：给 ChatGPT 对本次重构做针对性审核。**只发审核要求与文件清单，不粘贴代码**——ChatGPT 应按 Tunnel 工具以 `work/skills` 为 repo 读取本地文件。
>
> 说明：当前执行环境无 `chatgpt_send`/`chatgpt_get_result`/Tunnel MCP 工具，无法由 agent 自动发起外部审核。此材料供你把内容粘贴到 ChatGPT 审核，并把意见带回后由 agent 按 gpt-grilling-review 闭环处置（本地核对 → F/V/H 分流 → 修复 → 针对性复查）。

## 送审 content 模板（可直接粘贴）

```
请使用 Tunnel 工具按仓库名读取仓库 "work/skills"（repo 名 = work 下相对路径，Tunnel 会解析到真实目录；不要猜绝对路径）。

这是一次 dd-feature-development-workflow 的 token-efficient 重构，目标是在不降低来源可信度、验证有效性、独立审查、UI 证据、exact-SHA CI 和 Delivery 授权边界的前提下，压缩重复读取/重复字段/重复审查，并修复 Candidate/Documentation/Delivery 与共享 CI 的合同冲突。

请逐文件审核以下改动（相对仓库根的路径）：
dd-feature-development-workflow/SKILL.md
dd-feature-development-workflow/references/candidate.md
dd-feature-development-workflow/references/documentation.md
dd-feature-development-workflow/references/implementation.md
dd-feature-development-workflow/references/intake-and-environment.md
dd-feature-development-workflow/references/planning-stage.md
dd-feature-development-workflow/references/specification.md
dd-feature-development-workflow/references/state-and-handoff.md
dd-feature-development-workflow/references/planning.md
dd-feature-development-workflow/references/delivery-and-closure.md
dd-workflow-runtime/references/artifact-contract.md
dd-workflow-runtime/references/ci.md
dd-workflow-runtime/references/test-location.md
dd-workflow-runtime/references/ci-xcode.md
dd-ai-refactor-workflow/SKILL.md
dd-ai-refactor-workflow/references/verification-and-delivery.md
dd-feature-development-workflow/tests/test_feature_workflow_contracts.py
dd-workflow-runtime/tests/test_ci_contracts.py
dd-feature-development-workflow/tests/baseline-7-candidate-before-delivery.md
dd-feature-development-workflow/tests/baseline-8-phase-anchor-loading.md
dd-feature-development-workflow/tests/baseline-9-compact-verification.md
dd-feature-development-workflow/tests/baseline-10-frozen-candidate-review.md

重点审核：
1. 主 SKILL.md 是否只做 Router（AC-01），每个 Stage reference 是否一层可达（AC-02）；
2. artifact-contract 的 source_manifest + plan/result verification 是否保留 coverage/runs/bindings/validity 四个语义（AC-04）；
3. Phase 是否改为读 anchors/global constraints 而非整份规格（AC-05），普通 Phase 是否零独立强审（AC-06）；
4. Documentation 是否在候选冻结前完成（AC-07）；Candidate Gate 是否不推进目标分支、只产出可交付候选（AC-08）；
5. Delivery 是否强制 review_sha == gap_sha == ci_sha == candidate_sha（AC-09）；
6. ci.md / test-location.md / ci-xcode.md 是否已通用化、无 Macim/固定 workflow/旧步骤号（AC-10），Refactor 是否不再无条件每 Commit push（AC-11）；
7. 合同测试断言是否与文档合同一致、是否会误伤。

对每个 finding 输出：finding ID、SEVERITY(HIGH/MEDIUM/LOW)、问题描述、位置(文件:行号)、修改建议、建议分流(FINDING/VERIFICATION_REQUIRED/HUMAN_DECISION_REQUIRED)。
最后输出文件覆盖清单：
REVIEWED: <已读文件>
UNREADABLE: <未能读取的文件>
如果有指定文件未读到，不得宣称范围审核完成。如果无法读取任何指定文件，直接回复一行：无法读取指定文件。
```

## 本重构各任务的 commit 清单（供你定位 diff）

| 任务 | commit | 内容 |
|---|---|---|
| Task 1 | `d73b237` | 红测合同测试、baseline 7-10、red evidence |
| Task 2 | `2983fd9` | artifact-contract compact schema、planning 模板 |
| Task 3 | `86dd756` | 7 个单一职责 reference |
| Task 4 | `c7772da` | 主 SKILL Router + 5-Gate、delivery exact-SHA |
| Task 5 | `9e28f2f` | ci/test-location 通用化、ci-xcode、refactor push 修正 |
| Task 6 | `af0f179` + `826e11d` | baseline 迁移、retired 标记（删除待授权） |
| Task 7 | `2ec3389` | green evidence、规模对比、NOT_PROVEN |

## 复核后闭环

把 ChatGPT 意见带回后，agent 将：对每个引用做本地核对（属实/有误）→ 按 FINDING/VERIFICATION_REQUIRED/HUMAN_DECISION_REQUIRED 分流 → 修复获批事项 → 按 CHANGE_RISK 针对性复查直到 ChatGPT 返回 CLOSED。涉及生产代码/测试语义的 finding 不得由 agent 自行 CLOSED。
