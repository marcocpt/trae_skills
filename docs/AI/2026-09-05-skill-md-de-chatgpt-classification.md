# SKILL.md 去 ChatGPT 化：三层清单与处置方案

> 起草：2026-09-05 | 版本：v0.2-DRAFT（未批准）
> 依据：[多后端强审 Grilling 闭环需求与草案设计](2026-09-02-multi-backend-grilling-requirements-design.md) 的 FR-MB-002、FR-MB-008 与 §7.2。
> 评审对象：本文件（分类方案）+ 同分支已完成的 `gpt-grilling-review/references/transport.md` 重构。
>
> v0.1 → v0.2 修订依据：ChatGPT 首轮复核（MB-SKILL-CLASS-001~005）。
> - **001**：本方案原以"31 行含 `ChatGPT` 字符串"为审计全集，漏掉 `backend` 输入项这一结构性改动；
> - **002**：C 类严重漏项——整组"不含 `ChatGPT` 字样但只在 Tunnel 下成立"的硬绑定未被识别，故清单扩为三层；
> - **003**：第 197 行实为 A+C 混合项，不是纯角色主语；
> - **004**（用户裁决）：第 6 行标题改为「强审 Grilling 审核」，`name` 不变；
> - **005**：§8 红线不足，补三条 migration redline。

## 1. 目标

把 `gpt-grilling-review/SKILL.md` 中把"谁是主审、谁有权关闭 finding"写成 `ChatGPT` 的表述，改为后端中立的角色名，使同一套闭环语义对 `chatgpt-tunnel`、`opencode-cli` 及未来后端一致成立。

设计文档 §7.2 的原文约束：

> 协议层术语去 ChatGPT 化（**保留"同一强审身份/同一闭环上下文"语义，不做机械全局替换**）

### 不是什么

- **不是**字符串全局替换：`conversation_id` → `review_session_handle` 是续接句柄的抽象，重点是保留"同一"这个不变式，不是把词换掉。
- **不是**删除 ChatGPT：`chatgpt-tunnel` 仍是默认后端，指向传输的部分照旧引用 `transport.md`。
- **不是**给 skill 改名：FR-MB-008 明确保留 `gpt-grilling-review` 名称与属主身份（`dd-workflow-runtime/references/model-routing.md`、`review-gate.md`、`dd-xctest-newbie-grilling-review/SKILL.md` 均硬引用）。
- **不是**改 finding 生命周期语义：三字段、CLOSED 判据、DISPUTED、HARD-GATE 一个字不动。

## 2. 统计与三层清单

`SKILL.md` 中 `ChatGPT` 共 **31 行 / 43 处**（`grep -c` 统计行数，`grep -o` 统计出现次数）。但**字符串不是审计全集**（MB-SKILL-CLASS-002），完整改动清单分三层：

| 层 | 内容 | 规模 | 处置 |
|---|---|---|---|
| **第一层：字符串** | 含 `ChatGPT` 字样的表述 | 31 行 / 43 处 | 见下方 A/B/C/D 分类 |
| **第二层：隐式 transport 绑定** | 不含 `ChatGPT` 字样、但只在 `chatgpt-tunnel` 下成立的表述 | 6 处（另 2 处与 A/B 重叠） | 见第 7 节 |
| **第三层：结构性改动** | `backend` 输入项与选择入口（非字符串问题） | 1 项 | 见第 8 节 |

### 第一层细分

| 类别 | 行 | 处 | 处置 |
|---|---|---|---|
| A 角色主语 | 25 | 35 | 改为「强审者（strong-reviewer）」，语义不变 |
| B 续接句柄 | 2 | 2 | 改为「同一强审者 + `review_session_handle`」，保留"同一"语义 |
| C 传输细节 | 2 | 2 | 移出 SKILL.md 或改为引用 `transport.md` 对应分节 |
| D 保留·裁决后改 | 2 | 4 | 触发词保留；**第 6 行标题已裁决改为「强审 Grilling 审核」**（MB-SKILL-CLASS-004） |
| A+C 混合 | (197) | (1) | 见第 7 节；不得机械替换 |
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
| 6 | 1 | 标题 `# ChatGPT 文件 Grilling 审核` | **已裁决（2026-09-05，采纳主审建议）**：改为「强审 Grilling 审核」；`name: gpt-grilling-review` 不变；description 以「外部强审/多后端强审」描述能力并保留 `ChatGPT` 触发词作兼容别名 |

## 7. 第二层：隐式 transport 绑定（MB-SKILL-CLASS-002）

审计方式：在 `SKILL.md` 中检索 `Tunnel`、`work/<`、`timeout_seconds`、`conversation_id`、`content`、`repo 名`、`仓库名`、`文件清单`——这些词**不含 `ChatGPT` 字样，但只在 `chatgpt-tunnel` 下成立**。v0.1 的 C 类只抓到 87、283 两行，漏掉以下 6 处。

| 行 | 现表述 | 为何是 Tunnel 专属 | 改后 |
|---|---|---|---|
| 86 | 输入项「**仓库名**」，按 transport 仓库命名规则 | `opencode-cli` 用 cwd + 相对 `scope`，不需要 repo 名 | 输入项改为「受审范围（按所选后端的读取规则给出： Tunnel repo 名或 cwd + 相对 scope）」 |
| 93 | 状态机第 1 步「确认输入（**仓库名 + 文件清单**）」 | 同上 | 改为「确认输入（后端 + 受审范围 + 权威依据）」 |
| 154 | 「调用契约遵循 transport.md。**content**：」 | `content` 是 `chatgpt_send` 的字段名，非通用概念 | 改为「按所选后端打开 `transport.md` 对应分节构造请求」 |
| 157-171 | 整个首次送审模板硬编码 Tunnel、`<repo>`、`work/<相对路径>` | 整段是 `chatgpt-tunnel` 的线上格式 | **整段下沉到 `transport.md` 的 `chatgpt-tunnel` 分节**；SKILL.md 只留后端中立步骤 |
| 172 | 「repo 名与路径形式（强制）」 | 同上 | 随模板一并下沉 |
| 279 | 红线「中高风险复查用文件清单+摘要替代**真实 diff**」 | 与 `transport.md`「禁止粘贴代码/diff，审核方自行读取」冲突 | 改为「必须提供能定位真实 diff / 当前源码的 backend-appropriate scope，禁止只给摘要」 |

**A+C 混合项（MB-SKILL-CLASS-003）**：

| 行 | 现表述 | 冲突点 | 改后 |
|---|---|---|---|
| 197 | 给 reviewer 输入「**实际 diff、当前相关源码**」 | 与 `transport.md` chatgpt-tunnel 禁忌「禁止粘贴代码/diff」直接冲突，也不符合 `opencode-cli` 的 cwd + scope 自读模型 | 改为「向同一强审者提供 finding metadata、授权范围、baseline、验证结果，以及能定位真实 diff / 当前源码的 backend-appropriate scope；实际读取或传输方式按 `transport.md` 对应分节」 |

**边界判断**：第 282 行红线「输入必须含文件清单 + REVIEWED/UNREADABLE 覆盖」——**覆盖要求通用**（`dd-review-result/1` 有 `reviewed` / `unreadable` 字段），但 `REVIEWED:` / `UNREADABLE:` 字面标记是 `chatgpt-tunnel` 的线上格式。故该行保留"覆盖范围必须完整"的语义，标记格式改为引用 `dd-review-result/1` 的 `reviewed` / `unreadable`。

## 8. 第三层：结构性改动（MB-SKILL-CLASS-001）

**这一层不属于任何字符串替换**。即使把 A/B/C/D 的 43 处全部改完，Agent 仍不知道在哪里解析"用户显式 backend / 缺省 backend / 非法 backend"，SKILL.md 也就无法成为可选择多后端的 Thin Executable Router。

当前 `SKILL.md:84-89` 的输入项只有「仓库名 / 文件清单 / 权威依据 / baseline」，状态机第 2 步直接进入首审。

**改动**：

1. 输入项新增 `backend`（可选）：
   - **缺省** → `chatgpt-tunnel`（向后兼容）；
   - **显式给出** → 按 `transport.md` 的后端选择合同验证（canonical backend ID + 三项能力条件）；
   - **无法识别或不具资格** → `configuration_invalid` → BLOCKED，**不得静默回退**（FR-MB-001）。
2. 状态机第 1 步改为「确认输入（后端 + 受审范围 + 权威依据）」；第 2 步前插入「解析并校验 backend」。
3. SKILL.md **只保留这一最小执行入口**；资格条件、候选顺序、调用细节一律引用 `transport.md` 与 runtime，不复制（FR-MB-006）。

## 9. 待评审确认的问题

1. 「强审者（strong-reviewer）」是否为最合适的统一角色名？与 `dd-workflow-runtime/references/model-routing.md` 的 `strong-reviewer` 角色、以及 `agents/opencode/strong-reviewer-cli.md` 等既有命名是否一致、会不会产生歧义。
2. A 类 25 行的替换是否**逐处语义等价**？是否存在某处的 `ChatGPT` 实际承载了"默认后端"含义而非"角色"含义，替换后会丢失信息。
3. B 类改成「同一强审者 + `review_session_handle`」后，与 `transport.md` 新版「续接句柄与身份校验」一节的措辞是否一致（应引用同一套术语，不得各说一套）。
4. C 类第 87 行改为"引用 transport.md 对应分节"后，SKILL.md 是否仍具备足够的可执行性（Agent 只读 SKILL.md 时能否知道该怎么做），还是需要在 SKILL.md 保留一句后端中立的最小规则。
5. ~~D 类第 6 行标题：保留还是改中立？~~ **已裁决（2026-09-05）**：改为「强审 Grilling 审核」，`name` 不变。
6. ~~是否存在遗漏的 `ChatGPT` 硬绑定点？~~ **已由首轮复核 MB-SKILL-CLASS-002 指出并完成审计**，结果见第 7 节。
7. **（新增）** 第二层把首次送审模板整段下沉到 `transport.md` 后，SKILL.md 只剩"按所选后端打开对应分节"这类指针，是否会削弱 Thin Executable Router 要求的可执行性（`AGENTS.md` §3：只读主文件就知道下一步做什么）？是否需要保留一个后端中立的最小步骤清单？
8. **（新增）** 第三层的 `backend` 输入项，是否应在 description 的触发词里体现（例如加入"用 opencode 复审"），还是只作为内部输入项、不进触发词？
9. **（新增）** 第 282 行的 `REVIEWED:` / `UNREADABLE:` 字面标记改为引用 `dd-review-result/1` 的 `reviewed` / `unreadable` 字段后，与 `chatgpt-tunnel` 模板里仍要求输出的 `REVIEWED:` / `UNREADABLE:` 文字块是否会形成两套覆盖声明？

## 10. 红线

- 不得为缩短文件删除必要规则（AGENTS.md §5.8）。
- 不得借"去 ChatGPT 化"改动 finding 生命周期、三字段语义、CLOSED 判据或关闭权归属。
- 不得改名 `gpt-grilling-review` skill 或文件路径（FR-MB-008）。
- 不得在 SKILL.md 复制 `transport.md` 或 runtime registry 的内容（FR-MB-006：只引用）。
- 不得为通过测试加入无语义关键词。

### migration redline（MB-SKILL-CLASS-005，本次迁移特有的三条回归防线）

以下三条是"去 ChatGPT 化"最容易误改的地方，原 §8 未覆盖，现补入：

1. **后端专属细节不得回写**：后端专属的命令、路径、repo 名形式、读取方式（`Tunnel` / cwd / `scope`）、句柄语义，只存在于 `transport.md` 对应分节或 runtime 属主；SKILL.md 不得重新写回任何一条，也不得跨后端混用。
2. **关闭权不得因换后端被继承**：任何针对性复查必须保持**同一强审身份与同一 active session**；换后端即换 reviewer，判 `reviewer_continuity_lost` 并 BLOCKED，不得继承原会话的 CLOSED 权。
3. **能力不可证明即停**：只读能力、session continuity、candidate baseline 三者任一不可机械证明时立即 BLOCKED，**不得**以"这是默认后端""测试通过""以前能用"绕过。
