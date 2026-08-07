# TODO, LATER and Batch Repair

## 目录

- [TODO Schema](#todo-schema)
- [LATER](#later)
- [收尾分组](#收尾分组)
- [审核成果提交](#审核成果提交)
- [批次分类与路由](#批次分类与路由)
- [完成标记与验证摘要](#完成标记与验证摘要)
- [批次后 ASK](#批次后-ask)

## TODO Schema

文件头：

```markdown
审核文档:: /absolute/path/to/doc.md
```

条目之间留一个空行：

```markdown
- [ ] TODO1. [P1] 登录失败路径与实现不一致 #登录
  文档位置:: docs/spec.md#失败处理
  现状:: 文档声称重试，生产路径直接返回。
    (a) 证据：`src/login/handler.ts:84` 直接 return；
    (b) 文档依据：`docs/spec.md` §失败处理第 2 段声称自动重试 3 次。
  改进建议:: 将文档改为当前行为并补迁移说明（用户已选定的单一方案）。
  验证方式:: 重跑 TestLoginFlow，断言失败后返回码与修订后文档描述一致。
  审核时间:: 2026-07-28
  推荐修复文件:: src/login/handler.ts（生产分支在此决定返回）
  代码位置:: src/login/handler.ts:84
  图形化预览:: http://127.0.0.1:8000/index.html
```

必填属性：文档位置、现状、改进建议、验证方式、审核时间。模式 B 验证过代码时"推荐修复文件"与"代码位置"必填；预览只在真实存在时写。

### 可读性硬规则（2026-08-07 起强制）

- 字段值含多个独立事实时**必须分条**：续行缩进与字段值对齐，用 `(a)/(b)/(c)` 或 `-` 子项，一条事实独占一行并硬换行；
- 禁止把数百字糊成一段不换行的长文（反例：`现状::` 单段 500+ 字混合证据、推理与建议）；
- 代码标识符、路径、行号用反引号包裹；
- 条目之间留一个空行，不再"连续排列不留空行"。

### 面向后续修复的内容要求

TODO 的消费者是后续执行修复的会话（可能没有当前会话的任何上下文），条目必须自足：

- `现状` 写证据不写感受：行号、测试名、commit、可复现输入；
- `改进建议` 是用户已选定单一方案的具体操作步骤，达到可执行粒度（改哪个文件哪段、改成什么）；多方案未经裁决不得写入；
- `验证方式` 给出可判定的完成标准（跑哪个测试 / 观察什么输出）；"应该没问题"不是验证方式；
- 不得只写一句模糊的"后续优化"。

首次 TODO 时创建头部并追加 TODO1；后续根据实际已有最大编号追加。恢复时先读文件，不能依赖内存计数。

完成时：

```markdown
- [x] TODO1. [P1] ...
  ...
  修复SHA:: a1b2c3d
```

`修复SHA` 是代码修复工作流最后一个真实 Commit 的短 SHA，不是 TODO 状态提交自身 SHA。

## LATER

**强制规则：** 审核中发现、但后续才实现/延后/暂缓的事项，一律必须记入 LATER 持久化，避免遗忘。不得只在会话里口头延后或停留在记忆里；不得因为"不主动建文档"而跳过写入。

路径固定为项目根 `docs/AI/later/`（一项一文件）。调用 [dd-later-tracking](../../dd-later-tracking/SKILL.md)：

1. Grep `docs/AI/later/` 中现有条目的 title、tags、trigger 与正文关键词，找出可能重复项；
2. 语义复核（必要时子代理精判）；
3. 重复则合并更新已有条目文件，不新建；相关但独立则新增并在双方 frontmatter `related` 互链；
4. 新增：有 `docs/AI/later/_TEMPLATE.md` 则复制模板；文件名为权威 ID `LATER-<YYYYMMDD>-<slug>.md`（无全局顺序号）；开放条目 frontmatter 必填 `id`、`title`、`status`、`created`、`source`、`target_phase`、`trigger`；
5. 项目存在 INDEX 生成脚本（如 `Tools/gen_later_index.py`）时，改动条目后必须立即重新生成 INDEX.md，并与条目改动放在同一 commit。

正文分节、分条、硬换行；title 保持一句话。LATER 条目记录现状、延后理由、触发条件与关闭所需证据，但不扩写成方案文档。

## 收尾分组

只在用户明确选择收尾后插入，位置为 `审核文档::` 后、首条 TODO 前：

```markdown
- 并行分组
  - 可并行批次
    - 批次 P1:: T2(src/a.ts) | T5(src/b.ts)
  - 需串行批次
    - 批次 S1:: T1(src/shared.ts) -> T3(src/shared.ts)
  - 分组依据:: 推荐修复文件优先，其次代码位置，最后功能标签
  - 并行建议:: P1 可同时启动；S1 按 P0→P1→P2→P3 串行
```

模式 B：

- 推荐修复文件集合有交集 → 同一串行组；
- 无交集 → 可并行；
- 同功能不同文件仍可并行；
- 无文件位置时才按功能标签。

模式 A：同标签视为潜在冲突，不同标签可并行。空 TODO 不创建文件或分组。

## 审核成果提交

提交 TODO 与变更过的 LATER：

```text
docs(dd-docreview-grilling): 记录 <doc-name> 审核发现的 N 个 TODO + M 个 LATER
```

审核提交不包含代码修复。公共文件遵循 `PublicFile` 规则；不使用 `--no-verify`，不暂存无关变更。

## 批次分类与路由

先性质、再模块、再优先级：

- bug：已有完整实现，行为与文档/合同不符；
- feature：空桩、模块缺失、新入口、新状态或新用户能力；
- 不确定：ASK。

每批 ≤5；不跨 bug/feature；不跨模块；跨模块 P0 单独成批。

bug 批调用 `dd-bug-fix-workflow`，feature 批调用 `dd-feature-development-workflow`，均传：

```yaml
invocation_mode: child
todo_ids: [1, 3]
todo_file: /absolute/path/TODO.md
reviewed_document: /absolute/path/spec.md
repository_root: /absolute/path
```

只有同时满足“纯后端、单函数、不跨文件、无状态流转/回调/外部系统”的 feature 小补全才可降级 Bug 流程，并在提交正文记录理由。UI、可见行为、E2E、跨文件、多函数、状态/回调/外部系统、模块缺失均禁止降级。

父工作流不改写 child 的 TDD、规格、验证或提交规范。child 返回成功证据后才更新 TODO。

## 完成标记与验证摘要

取得 child 的 tip SHA，确认工作区没有遗漏的修复变更，再：

1. `[ ]` 改 `[x]`；
2. 条目最后追加 `修复SHA`；
3. 创建 `验证摘要/<doc-name>_批次<N>_验证摘要.md`；
4. 提交 TODO 状态和摘要。

摘要模板：

```markdown
# <doc-name> 第 N 批验证摘要

TODO 文件:: path/to/TODO.md
批次:: 第 N 批（bug/feature，#模块）
修复SHA:: a1b2c3d

## TODO1. [P1] 问题

- 修复文件：path/to/file
- 验证前置条件：...
- 操作：
  1. ...
  2. ...
- 预期：可观察的具体文本、页面、状态或返回值
- 结果：[ ] 通过 [ ] 失败
```

每条至少 2 个可操作步骤；“应该没问题”不是可判定预期。

状态与摘要提交使用批次语义：

- bug：`fix(<scope>): 修复 <doc-name> 审核的第 N 批问题`
- feature：`feat(<scope>): 实现 <doc-name> 审核的第 N 批缺失功能`

## 批次后 ASK

每批提交后提供全部选项：

1. `继续修复下一批`
2. `选择特定批次`
3. `暂停修复，保留 TODO`
4. `全部自动修复（后续每批仅持久化进度）`

即使只剩一批也不减少选项。用户选择全部自动后仍逐批验证、提交、记录 SHA 和摘要，只是不重复 ASK。
