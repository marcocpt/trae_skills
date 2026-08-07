---
name: dd-docreview-grilling
description: 用户想逐条交互式审核文档时使用。触发词：审核文档、文档审核、review doc、逐条核对文档、grill this doc、审核代码是否符合文档、verify code against doc、check code matches doc。覆盖纯文档审核和文档-代码一致性审核。
---

# 文档审核访谈

## 目标

以“证据解答 → 可视化 → 满意度 → TODO/LATER 落盘 → 可选批量修复”持续审核文档。使用 [dd-shared-workflow-runtime](../dd-shared-workflow-runtime/SKILL.md) 保证长会话中断可恢复；默认只加载本文件，进入单轮问答或落盘/修复时再读对应 reference。

## 两种模式

- `document-only`：解释和审核文档本身；
- `doc-code-consistency`：同时核对真实代码、测试、生产装配和调用链，TODO 必须给出验证过的推荐修复文件。

文档说法不是代码事实。模式 B 必须先查仓库再下结论，缺证据时明确标记 `UNRESOLVED`，不得猜测。

## 运行时与所有权

直接响应用户：

```yaml
workflow_type: docreview-grilling
invocation_mode: standalone
host: auto
requested_entry: review-loop
state_file: $(git rev-parse --git-dir)/docreview-state.json
```

被其他编排器调用时使用 `invocation_mode=child`，完成后返回父工作流，不执行 Host Close。

状态至少保存：

- 文档绝对路径、mode、当前章节/问题；
- 已确认事实与待核实项；
- TODO 路径和已分配编号、LATER 条目文件与 ID；
- 每轮 disposition；
- 批次、修复 SHA、验证摘要；
- `current_stage`、blocker、`next_safe_action`。

每次用户选择、TODO/LATER 写入、Commit、批次完成后立即原子持久化。恢复时以文件、Git 和仓库证据为准；不得重问已确认的路径、模式或结论。

## 启动

1. 读取项目规则和被审核文档；
2. 判断是否只读。预计写 TODO/LATER/代码时，首次修改前按 [dd-shared-ask](../dd-shared-ask/SKILL.md) 选择 worktree；
3. 若未提供路径，ASK 一个问题获取路径；
4. ASK 审核模式；
5. ASK 起始章节；
6. ASK TODO 保存路径，默认 `docs/AI/doc-review-todo/<doc-name>_TODO.md`；
7. LATER 固定为项目根 `docs/AI/later/` 目录（一项一文件，见 [dd-later-tracking](../dd-later-tracking/SKILL.md)），不重复询问；
8. 写入状态后进入 Review Loop。

纯只读且不落盘、不修复时不询问 worktree。

## Review Loop

每个用户问题固定执行：

1. 定位文档锚点；
2. 模式 B 额外验证代码、测试、装配和调用路径；
3. 给出证据结论与可点击位置；
4. 对流程、状态、时序、架构或 UI 差异使用最小有效可视化；
5. 多方案时列出候选、推荐与权衡，并 ASK 用户选择；
6. ASK 满意度；
7. 满意后 ASK `加入 TODO / 加入 LATER / 不记录`；
8. 立即落盘并持久化；
9. 有新问题则循环；无新问题时 ASK `继续提问 / 进入收尾`。

详细选项、图形选择、代码证据纪律和 HTML server 协议见 [review-loop-and-evidence.md](references/review-loop-and-evidence.md)。

<HARD-GATE>
每轮不能省略满意度与 disposition 两阶段 ASK；用户沉默不代表结束或继续。不能用省 token、赶时间或“结论很明显”跳过证据、可视化、选择或即时落盘。
</HARD-GATE>

## TODO / LATER

TODO 使用 Logseq 兼容的 Markdown task：

```markdown
- [ ] TODO1. [P1] 可独立理解的问题描述 #模块
  文档位置:: path/to/doc.md#section
  现状:: ...
  改进建议:: 用户已选定的单一方案
  审核时间:: YYYY-MM-DD
  推荐修复文件:: path/to/file（理由）
  代码位置:: path/to/file:42
```

规则：

- 首次选择 TODO 时创建文件，此后只追加，不积压到收尾；
- 必填：文档位置、现状、改进建议、验证方式、审核时间；
- 多事实字段必须分条硬换行（一条事实一行），条目间留空行；禁止数百字不换行长段；
- 模式 B 验证过代码时必须有推荐修复文件与理由；
- 代码位置、HTML 预览只在真实存在时写；
- 待办不写 `修复SHA`；标记 `[x]` 时最后追加 `修复SHA:: <短SHA>`；
- LATER 通过 [dd-later-tracking](../dd-later-tracking/SKILL.md) 去重后写入 `docs/AI/later/`（一项一文件，frontmatter + 分节正文）；项目有 INDEX 生成脚本时，改动条目的同一 commit 必须刷新 INDEX。

完整 schema、去重、并行分组见 [todo-later-and-batch-repair.md](references/todo-later-and-batch-repair.md)。

## Review Close

用户选择收尾后：

1. 停止临时 HTML server，保留 HTML；
2. 汇总问题、优先级和 TODO/LATER/不记录分布；
3. 有 TODO 时按文件冲突生成并行/串行组，插入头部后、首条 TODO 前；
4. 提交 TODO/LATER 审核成果，不夹带修复；
5. 无落盘内容时不创建空文件、不做空提交；
6. ASK 是否进入批量修复。

审核成果与代码修复必须是不同提交。

## Batch Repair

用户选择修复时：

1. 逐条判定 bug/feature；不清楚时 ASK；
2. 再按模块、优先级分批，单批 ≤5，不跨性质、不跨模块；
3. 展示批次并 ASK 确认；
4. bug 批以 `invocation_mode=child` 调 [dd-bug-fix-workflow](../dd-bug-fix-workflow/SKILL.md)；
5. feature 批以 `invocation_mode=child` 调 [dd-feature-development-workflow](../dd-feature-development-workflow/SKILL.md)；
6. 父工作流取得已提交的 tip SHA，原位标记 TODO 完成并追加 `修复SHA`；
7. 生成 `验证摘要/<doc-name>_批次<N>_验证摘要.md`；
8. 提交 TODO 状态与验证摘要；
9. 除非用户已选“全部自动修复”，每批后 ASK 下一批/指定批/暂停/全部自动。

路由、降级边界、提交和验证摘要模板见 [todo-later-and-batch-repair.md](references/todo-later-and-batch-repair.md)。

## Exit Gate

- 用户明确进入收尾；
- 每轮已完成满意度与 disposition；
- TODO/LATER 均已即时持久化且去重；
- 并行分组、审核提交和批次状态可追溯；
- 已完成批次均有真实修复 SHA 和验证摘要；
- 未完成项保持 `[ ]` 且有恢复动作；
- 无 blocking issue；
- 状态已持久化。

暂停批量修复可以完成“本次审核流程”，但必须在摘要中列出剩余 TODO；不得伪装为代码全部修复。

## Host Close

仅 `invocation_mode=standalone` 执行。证据依据据却按功能标签代替文件冲突分组；
- 未提交修复就标 `[x]`；
- 同批混合 bug/feature 或超过 5 条；
- child 修复工作流自行 Host Close；
- 每批缺验证摘要；
- Trae 完成后直接结束。

## 按需读取

- 单轮问答、可视化、代码证据、三阶段 ASK：[references/review-loop-and-evidence.md](references/review-loop-and-evidence.md)
- TODO/LATER、收尾、分组、批量修复与验证摘要：[references/todo-later-and-batch-repair.md](references/todo-later-and-batch-repair.md)
