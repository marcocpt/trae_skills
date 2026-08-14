---
name: gpt-review-loop
description: Use when 完成一轮代码修改后需要送外部 ChatGPT 审核、调用 chatgpt_send/chatgpt_get_result/chatgpt_send_file、轮询审核结果或处置审核意见；或遇到 timeout_seconds 上限、[RUNNING]/[FAILED]、轮询连接中断、cpdf-wt worktree 仓库命名问题。触发词：ChatGPT 审核、送审、复审、审核闭环、chatgpt_send。
---

# ChatGPT 审核闭环

## 概述

弱模型修改代码后，向外部 ChatGPT 发起审核：**只发审核要求，不发代码**；审核方经授权通道自行读取本地代码并返回意见，agent 逐条处置形成闭环。

**违反规则的字面意思就是违反规则的精神。**

## 基线失败（无本技能时的真实错误）

| 真实失败 | 技能对策 |
|---|---|
| 传 timeout_seconds=900 → 参数校验报错（上限 600） | 固定 600 |
| 轮询连接 ECONNRESET → 脚本崩溃放弃（任务其实还在跑） | 每次轮询新建连接 + 重试 |
| 用了已删除的 worktree 名 → 白跑一轮 | 送审前 `git worktree list` 确认 |
| content 指令含糊 → 审核方等待粘贴代码 | 用本技能模板 + 逃逸句 |

## 三步法

### 1. 提交 chatgpt_send

- `conversation_id`：固定 `"<app 名>-<仓库名>-<分支名>-<月日时分>"`，同一个会话中多轮复用（复审带上下文）
- `instruction`：传 `""`（不加默认前缀）
- `timeout_seconds`：`600`（这是上限，传更大直接报参数错误）
- `content`：按下方模板。只写业务要求 + 仓库名 + 范围；**禁止粘贴代码/diff**

### 2. 轮询 chatgpt_get_result

- 开始 20 秒间隔轮询 3次，随后 40 间隔轮询；`[RUNNING]` 继续等，审核通常 5-10 分钟
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

## content 模板

**分支整体审（最常用）：**

```
请使用你可用的工具，自行读取仓库 "<repo>" 的代码（不要依赖我提供内容）：
1. 查看 git 状态与当前分支；
2. 查看该分支相对 develop 的全部改动；
3. 审核这些改动的代码质量、正确性与潜在风险。
输出：先确认你读到的分支名，再按 高/中/低 给结构化意见，每条含 问题、位置（文件:行号）、建议。
如果无法读取该仓库，直接回复一行：无法读取该仓库。
```

**复审（同 conversation_id 续发）：**

```
我已按你上一轮意见修改，请重新读取仓库 "<repo>" 相对 develop 的最新改动，
重点复查上次问题 <编号> 是否修复，并检查是否引入新问题。输出格式同上。
```

**针对性审：**

```
请读取仓库 "<repo>" 的 <目录/文件> 及其测试，专门审核 <关注点>。
输出结构化意见（问题、位置、建议）。
```

## 禁忌

- content 提及 MCP、tunnel、浏览器、插件等实现机制 → 只写业务视角
- 粘贴代码/diff 进 content → 审核方自行读取
- 敏感文件（密钥/凭据/.env）进入请求
- timeout_seconds 超过 600
- `[RUNNING]` 期间重复提交
- 省略模板末尾的逃逸句

## 红线 - 出现即停下纠正

| 借口 | 现实 |
|---|---|
| "改动很小跳过审核" | 小改动也会错；审核是强制步骤 |
| "轮询太慢再提交一次" | 重复提交浪费 5-10 分钟并污染会话 |
| "直接把 diff 粘过去更快" | 粘贴 = 失去审核方主动探索上下文的能力 |
| "连接断了任务肯定没了" | 任务在 daemon，重连继续轮询 |
| "审核意见只是建议" | 必须逐条处置（采纳或说明理由），不得忽略 |
