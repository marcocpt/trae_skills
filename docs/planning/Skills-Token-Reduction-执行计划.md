# Skills 省 Token 重构执行计划（2026-08-29）

## 目标

在不降低可执行性与质量门禁的前提下，降低 Skill 每次触发时的加载 token 成本。手段仅限四类：
去重复（回归单一事实源）、细节下沉 reference、消费方一句话概述＋路由、英文叙述中文化。
遵循 AGENTS.md 全部纪律；以 `dd-feature-development-workflow/SKILL.md`（thin executable router，
commit e0aeb7d）为形态样板。所有省 token 结论只报告 `wc -c` 实测数字。

## 范围

修改 13 个 Skill，跳过 3 个。

跳过理由：

- `dd-feature-development-workflow`：刚完成同型重构（e0aeb7d），本任务将其作为样板；
- `dd-git-workflow`（56 行）：已是目标形态的最薄入口；
- `dd-project-docs`（44 行）：已是目标形态的最薄入口。

## 分类与分批（≤3 worktree 并行）

| 批次 | worktree 分支 | Skill | 主要问题点（动手前需逐条核实属主） |
|---|---|---|---|
| 1 | `refactor/skills-runtime` | dd-workflow-runtime | 「询问与执行预算」两条巨型 adapter 路由子弹与 model-routing.md 重复（已核实 model-routing.md 拥有全部细节）；其余保守 |
| 1 | `refactor/skills-bugfix-specs` | dd-bug-fix-workflow、dd-writing-specs | 核心原则英文；Host Close 协议重复（属主=runtime 宿主结束合同）；bug-fix 状态 schema＋legacy 映射内联；specs Git 授权长论述与 runtime 重复 |
| 1 | `refactor/skills-refactor-bootstrap` | dd-ai-refactor-workflow、dd-project-bootstrap-workflow | Host Close 协议重复；核心原则英文；bootstrap Handoff 12 项清单与 execution-contract.md 疑似重复；受 test_ci_contracts.py 两条断言约束 |
| 2 | `refactor/skills-gpt-review` | gpt-grilling-review | 基线失败表／红线表／禁止事项三段大面积语义重叠；模板与字段不动 |
| 2 | `refactor/skills-xctest` | dd-xctest-newbie-grilling-review | ChatGPT 传输机制与 gpt-grilling-review 重复（传输属主=后者）；A/B/C 四段模板重复 |
| 2 | `refactor/skills-later-docreview` | dd-later-tracking、dd-docreview-grilling | later：TodoWrite 边界三处重复、INDEX 规则两处重复、借口表与红线重叠；docreview 轻度 |
| 3 | `refactor/skills-writing-skills` | writing-skills | 红-绿-重构循环五处重复表述；CSO 示例块过多；测试类型四段可压缩 |
| 3 | `refactor/skills-tools` | detailed-log、workflow-runner、mcp-builder | detailed-log 四语言示例违反单示例原则（另两个仅轻度） |

## 流程（每批）

1. 从 develop 建 worktree 与分支；
2. 并行 subagent 修改：每个 Skill 单独 commit，message 含 `wc -c` 前后字节数；
3. 主线程程序化检查：相对链接有效性、`git diff --check`、相关自动化测试；
4. 按 `gpt-grilling-review` 送 ChatGPT 审核，循环处置直到本批 finding 全部关闭；
5. merge 回 develop（本地，不 push）；
6. 进入下一批。

## 纪律红线（摘自 AGENTS.md，全程适用）

- 不修改字段名、枚举值、状态值、CLI 参数、稳定 ID；frontmatter `name` 不动；
- 不删除或弱化任何 Gate、红线、HARD-GATE；红线仅允许按主题分组与合并字面重复项；
- 去重前先核实属主文件确实拥有该内容；禁止制造第二事实源，也禁止丢失属主信息；
- `dd-*/tests/baseline-*.md` 与 `tests/evidence/` 为历史测试证据，不修改；
- 测试断言不放宽；共享合同修改后必须检查全部直接消费者。

## 度量

每文件记录修改前后 `wc -lc`；最终汇总报告只陈述实测数字，不做无测量声明。
