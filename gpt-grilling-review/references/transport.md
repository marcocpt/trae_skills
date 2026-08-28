> 迁移来源：`gpt-review-loop/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。

# ChatGPT 审核闭环

## 概述

弱模型修改代码后，向外部 ChatGPT 发起审核：**只发审核要求，不发代码**；审核方经授权通道自行读取本地代码并返回意见，agent 逐条处置形成闭环。

**违反规则的字面意思就是违反规则的精神。**

## 基线失败（无本技能时的真实错误）

| 真实失败 | 技能对策 |
|---|---|
| 传 timeout_seconds 超过上限 → 参数校验报错 | 固定 600（参数上限 3600） |
| 轮询连接 ECONNRESET → 脚本崩溃放弃（任务其实还在跑） | 每次轮询新建连接 + 重试 |
| 用了已删除的 worktree 名 → 白跑一轮 | 送审前 `git worktree list` 确认 |
| content 指令含糊 → 审核方等待粘贴代码 | 用本技能模板 + 逃逸句 |

## 三步法

### 1. 提交 chatgpt_send

- `conversation_id`：固定 `"<app 名>-<仓库名>-<分支名>-<月日时分>"`，同一个会话中多轮复用（复审带上下文）
- `instruction`：传 `""`（不加默认前缀）
- `timeout_seconds`：`600`（单轮审核等待上限；MCP 参数上限 3600，传更大直接报参数错误）
- `content`：按下方模板。只写业务要求 + 仓库名 + 范围；**禁止粘贴代码/diff**

### 2. 取结果 chatgpt_get_result（长轮询）

- 直接调用 `chatgpt_get_result`，不必传 `wait_seconds`：服务端默认挂起最长 55 秒等待，完成立即返回；返回 `[RUNNING]` 则循环再调，审核通常 5-10 分钟
- 无需客户端自定节奏（旧的“隔 20/40 秒再调”已废弃）；仅当所在客户端单次工具调用超时小于 55 秒时显式传更小的 `wait_seconds`（传 0 = 立即返回不等待）
- **禁止重复提交**；`[FAILED]` 检查原因后最多重试 1 次
- 连接异常（ECONNRESET 等）：任务仍在 daemon，**新建连接更新 conversation_id 重试轮询**，不要放弃
- 满 10 分钟仍未完成：报告用户等待中，不得无限阻塞

### 3. 处置意见

- 逐条：采纳 → 修改并注明依据哪条意见；不采纳 → 说明理由（审核方可能掌握你没看到的事实）
- 重大修改后复用同一 conversation_id 复审

## 仓库命名

| 目标 | repo 名 |
|---|---|
| develop 主目录 | `cpdf` |
| CPDF worktree | `cpdf-wt/<分组>/<分支名>`，如 `cpdf-wt/test/S5-Governance-review` |
| 其他项目（~/Working 下全部，含未来新增） | `work/<相对路径>`，如 `work/Keyboard/Macim-worktrees/F-3.3` |

worktree 动态变化，送审前先确认仍存在：`git -C /Users/dengdeng/Working/PDF/CPDF worktree list`。

### Tunnel 解析规则（强制）

ChatGPT 只能通过 **Tunnel 工具按 repo 名解析**到本地真实目录，映射固定：

- `work/<相对路径>` → `~/Working/<相对路径>`
- `cpdf` / `cpdf-wt/<分组>/<分支名>` → CPDF 仓库对应位置

**content 中的 repo 必须是上表的名字形式，严禁使用任何绝对路径（如 `/Users/dengdeng/Working/...`）或项目真实目录名。** 弱模型送审前必须把本地绝对路径按此表换算成 `work/<相对路径>` 形式（例：`/Users/dengdeng/Working/Keyboard/Macim-worktrees/F-3.3` → `work/Keyboard/Macim-worktrees/F-3.3`）。文件清单也必须是 repo 内相对路径，不得写绝对路径。

## content 模板

**分支整体审（最常用）：**

```
请使用 Tunnel 工具按仓库名读取 "<repo>" 的代码（不要依赖我提供内容，也不要猜绝对路径——"<repo>" 即本地 work 下的相对路径，Tunnel 会解析到真实目录）：
1. 查看 git 状态与当前分支；
2. 查看该分支相对 develop 的全部改动；
3. 审核这些改动的代码质量、正确性与潜在风险。
输出：先确认你读到的分支名，再按 高/中/低 给结构化意见，每条含 问题、位置（文件:行号）、建议。
如果无法读取该仓库，直接回复一行：无法读取该仓库。
```

**复审（同 conversation_id 续发）：**

```
我已按你上一轮意见修改，请通过 Tunnel 工具重新读取仓库 "<repo>" 相对 develop 的最新改动（repo 名=work 下相对路径，不要猜绝对路径），
重点复查上次问题 <编号> 是否修复，并检查是否引入新问题。输出格式同上。
```

**针对性审：**

```
请通过 Tunnel 工具读取仓库 "<repo>"（repo 名=work 下相对路径）的 <目录/文件> 及其测试，专门审核 <关注点>。
输出结构化意见（问题、位置、建议）。
```

## 禁忌

- content 透漏 MCP/浏览器/插件等底层实现细节；repo 必须以 `work/<相对路径>` 形式给出，并明确让 ChatGPT 用 Tunnel 工具按 repo 名读取（不得写绝对路径，也不得写项目真实目录名）
- 粘贴代码/diff 进 content → 审核方自行读取
- 敏感文件（密钥/凭据/.env）进入请求
- timeout_seconds 超过 3600（参数上限）
- `[RUNNING]` 期间重复提交
- 省略模板末尾的逃逸句
- 在 content 中写本地绝对路径（如 `/Users/dengdeng/Working/...`）或项目真实目录名代替 `work/<相对路径>` 形式的 repo 名

## 红线 - 出现即停下纠正

| 借口 | 现实 |
|---|---|
| "改动很小跳过审核" | 小改动也会错；审核是强制步骤 |
| "轮询太慢再提交一次" | 重复提交浪费 5-10 分钟并污染会话 |
| "直接把 diff 粘过去更快" | 粘贴 = 失去审核方主动探索上下文的能力 |
| "连接断了任务肯定没了" | 任务在 daemon，重连继续轮询 |
| "审核意见只是建议" | 必须逐条处置（采纳或说明理由），不得忽略 |
