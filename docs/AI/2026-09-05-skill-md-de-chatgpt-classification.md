# SKILL.md 去 ChatGPT 化：31 行 / 43 处分类与处置方案

> 起草：2026-09-05 | 版本：v0.1-DRAFT（未批准）
> 依据：[多后端强审 Grilling 闭环需求与草案设计](2026-09-02-multi-backend-grilling-requirements-design.md) 的 FR-MB-002、FR-MB-008 与 §7.2。
> 评审对象：本文件（分类方案）+ 同分支已完成的 `gpt-grilling-review/references/transport.md` 重构。

## 1. 目标

把 `gpt-grilling-review/SKILL.md` 中把"谁是主审、谁有权关闭 finding"写成 `ChatGPT` 的表述，改为后端中立的角色名，使同一套闭环语义对 `chatgpt-tunnel`、`opencode-cli` 及未来后端一致成立。

设计文档 §7.2 的原文约束：

> 协议层术语去 ChatGPT 化（**保留"同一强审身份/同一闭环上下文"语义，不做机械全局替换**）

### 不是什么

- **不是**字符串全局替换：`conversation_id` → `review_session_handle` 是续接句柄的抽象，重点是保留"同一"这个不变式，不是把词换掉。
- **不是**删除 ChatGPT：`chatgpt-tunnel` 仍是默认后端，指向传输的部分照旧引用 `transport.md`。
- **不是**给 skill 改名：FR-MB-008 明确保留 `gpt-grilling-review` 名称与属主身份（`dd-workflow-runtime/references/model-routing.md`、`review-gate.md`、`dd-xctest-newbie-grilling-review/SKILL.md` 均硬引用）。
- **不是**改 finding 生命周期语义：三字段、CLOSED 判据、DISPUTED、HARD-GATE 一个字不动。

## 2. 统计

`SKILL.md` 中 `ChatGPT` 共 **31 行 / 43 处**（`grep -c` 统计的是行数 31，`grep -o` 统计的是出现次数 43）。

| 类别 | 行 | 处 | 处置 |
|---|---|---|---|
| A 角色主语 | 25 | 35 | 改为「强审者（strong-reviewer）」，语义不变 |
| B 续接句柄 | 2 | 2 | 改为「同一强审者 + `review_session_handle`」，保留"同一"语义 |
| C 传输细节 | 2 | 2 | 移出 SKILL.md 或改为引用 `transport.md` 对应分节 |
| D 保留·待裁决 | 2 | 4 | 保留；第 6 行标题待用户裁决 |
| **合计** | **31** | **43** | |

## 3. A 类：角色主语（25 行 / 35 处）

规则主体与"是 ChatGPT 还是 opencode"无关——换任何 reviewer，都只有**原来那个 reviewer** 能确认自己的 finding 是否真修好了。故主语换成角色名，语义完全不变。

| 行 | 处 | 现表述要点 | 改后 |
|---|---|---|---|
| 10 | 3 | ChatGPT（强模型）是主审与最终关闭人 / 凡 ChatGPT 提出的 finding / 由 ChatGPT 针对性复查 | 强审者（strong-reviewer） |
| 16 | 1 | 角色表 `ChatGPT（强模型/主审）` | `强审者（主审）` |
| 31 | 1 | 仍须由 ChatGPT 按风险等级复审 | 强审者 |
| 37 | 1 | SEVERITY（首审 ChatGPT 输出） | 首审强审者输出 |
| 50 | 1 | 突破下限降级须送 ChatGPT 复核 | 强审者 |
| 62 | 2 | 对 ChatGPT finding 提出反证，待 ChatGPT 复核 | 强审者 |
| 94 | 1 | 拿到 ChatGPT 的 finding 清单 | 强审者 |
| 95 | 1 | 对 ChatGPT 引用的每个文件、行号、结论 | 强审者 |
| 98 | 1 | 依据「风险分流规则」+ ChatGPT 建议分流 | 强审者 |
| 135 | 4 | 改变 ChatGPT 建议的 CLASSIFICATION / 送 ChatGPT targeted reconsideration / 均须 ChatGPT 复核 / 例如 ChatGPT 判定 FINDING | 强审者（4 处） |
| 139 | 1 | 不得静默否定 ChatGPT finding | 强审者 |
| 141 | 1 | 发现 ChatGPT 引用/结论不成立 | 强审者 |
| 143 | 1 | ChatGPT 确认不成立 → `INVALIDATED` | 强审者 |
| 180 | 2 | 凡 ChatGPT 提出的 finding…由 ChatGPT 针对性复查 | 强审者 |
| 181 | 1 | 轻量 ChatGPT targeted review | 强审者 |
| 189 | 2 | LOW 复查要求表 | 强审者 |
| 190 | 2 | MEDIUM 复查要求表 | 强审者 |
| 191 | 2 | HIGH 复查要求表 | 强审者 |
| 197 | 1 | 给 ChatGPT 输入：finding ID、原 finding… | 强审者 |
| 237 | 1 | 展示四段：ChatGPT 意见 → … | 强审者意见 |
| 247 | 1 | 按风险等级送 ChatGPT 针对性复查 | 强审者 |
| 273 | 1 | 红线："ChatGPT 说的肯定对" | 强审者 |
| 274 | 1 | 红线：必须由 ChatGPT 复查返回 CLOSED | 强审者 |
| 277 | 1 | 红线：必须送 ChatGPT 复核 | 强审者 |
| 278 | 1 | 红线：附反证送 ChatGPT 复核 | 强审者 |

## 4. B 类：续接句柄（2 行 / 2 处）

**最不能机械替换的部分**——重点是保留"**同一**强审身份"这个不变式，而不是把 `conversation_id` 换个名字。

| 行 | 处 | 现表述 | 改后 |
|---|---|---|---|
| 142 | 1 | 送 ChatGPT 复核反证（同 `conversation_id`） | 送**同一**强审者复核反证（复用 `review_session_handle`） |
| 195 | 1 | `### ChatGPT 针对性复查模板（同 conversation_id 续发）` | `### 针对性复查模板（同一强审者续接）` |

注：第 142 行同时属于 A 类（角色），两处一起改。

## 5. C 类：传输细节（2 行 / 2 处）

这两条是 `chatgpt-tunnel` **专有**规则，对 `opencode-cli` 不成立甚至有害——`opencode-cli` 不使用 Tunnel、不认 `work/<相对路径>` repo 名，改用 cwd + 相对 `scope`（FR-MB-005）。

| 行 | 处 | 现表述 | 改后 |
|---|---|---|---|
| 87 | 1 | 文件清单与 repo 名都必须是 `work/<相对路径>` 形式，禁止任何绝对路径 | 按所选后端的读取规则，引用 `transport.md` 的对应后端分节 |
| 283 | 1 | 红线：ChatGPT 经 Tunnel 按 `work/<相对路径>` repo 名自行读取 | 移入 `transport.md` 的 `chatgpt-tunnel` 禁忌（新版已保留该条） |

## 6. D 类：保留 / 待裁决（2 行 / 4 处）

| 行 | 处 | 内容 | 处置 |
|---|---|---|---|
| 3 | 3 | description 触发词「ChatGPT 文件审核 / 让 ChatGPT 自行读取」 | **保留**（用户实际用词，删除会影响触发）；建议**补充**一个多后端触发词 |
| 6 | 1 | 标题 `# ChatGPT 文件 Grilling 审核` | **待用户裁决**：保留原名利于识别与既有引用；改为「强审 Grilling 审核」更中立 |

## 7. 待评审确认的问题

1. 「强审者（strong-reviewer）」是否为最合适的统一角色名？与 `dd-workflow-runtime/references/model-routing.md` 的 `strong-reviewer` 角色、以及 `agents/opencode/strong-reviewer-cli.md` 等既有命名是否一致、会不会产生歧义。
2. A 类 25 行的替换是否**逐处语义等价**？是否存在某处的 `ChatGPT` 实际承载了"默认后端"含义而非"角色"含义，替换后会丢失信息。
3. B 类改成「同一强审者 + `review_session_handle`」后，与 `transport.md` 新版「续接句柄与身份校验」一节的措辞是否一致（应引用同一套术语，不得各说一套）。
4. C 类第 87 行改为"引用 transport.md 对应分节"后，SKILL.md 是否仍具备足够的可执行性（Agent 只读 SKILL.md 时能否知道该怎么做），还是需要在 SKILL.md 保留一句后端中立的最小规则。
5. D 类第 6 行标题：保留还是改中立？若保留，是否需要在正文首段加一句说明"本 skill 支持多后端，ChatGPT 为默认后端"。
6. 是否存在本方案**遗漏**的 `ChatGPT` 硬绑定点（例如没有出现 `ChatGPT` 字样但实际只在 `chatgpt-tunnel` 下成立的表述，如 `conversation_id`、`Tunnel`、`content`、`repo 名`、`timeout_seconds` 等隐含耦合）。

## 8. 红线

- 不得为缩短文件删除必要规则（AGENTS.md §5.8）。
- 不得借"去 ChatGPT 化"改动 finding 生命周期、三字段语义、CLOSED 判据或关闭权归属。
- 不得改名 `gpt-grilling-review` skill 或文件路径（FR-MB-008）。
- 不得在 SKILL.md 复制 `transport.md` 或 runtime registry 的内容（FR-MB-006：只引用）。
- 不得为通过测试加入无语义关键词。
