---
name: multi-agent-branch-integration
description: 当多个 Agent App 在多 worktree、多 feature 分支上并行开发，需要统一分支可见性判定、develop 同步、合入检查与推送门禁时使用；也用于安装 branchctl、执行 preflight/sync/review-ready/gate-ready/merge-ready，或排查同步阻断与未知可见性。触发词：branchctl、preflight、多 Agent 分支、分支集成、push-check、ci-check。
---

# 多 Agent 分支集成

一句话原则：**Agent 不自己选择 merge / rebase，`branchctl` 决定；
hook 与 CI 负责兜底。**

Skill 决定流程合同，`branchctl` 执行机器判断，
Git pre-push hook 与 GitHub Actions 只做强制检查、不改写历史。

分支同步规则的事实属主是 `dd-git-workflow`（见其 `references/branch.md`
“私有 / 共享分支同步”节），本 Skill 只做自动化执行层，不自立第二套规则。

## 何时使用

- 在已安装本 Skill 的仓库中做任何 feature 开发之前；
- 同步 `develop`、进入评审 / 门禁 / 最终集成之前；
- 推送被 hook 拦截、CI 报分支策略失败之后；
- 把本 Skill 安装到新项目、或更新受管运行时之后。

## 何时不使用

- 通用 Git 原子操作（分支命名、commit 规范、worktree 创建、清理建议）：
  仍由 `dd-git-workflow` 拥有，本 Skill 不重复定义；
- 需要语义级冲突判断、自动解决冲突：本 Skill 不提供，转人工处理；
- 项目尚未安装：先看本文档「安装」一节，而不是手写 git 命令绕过。

## 标准执行顺序（Agent 全自动）

```text
任务开始：  ./scripts/branchctl agent-start   → AGENT_START=true 才继续
开发…测试…提交（Agent 按任务自行完成）
任务收尾：  ./scripts/branchctl agent-finish  → REVIEW_READY=true 才送审
```

`agent-start` 内部分三步：按项目策略自动初始化可见性（无默认值仍阻断）、
按需自动同步一次（private→rebase，shared→merge，不循环）、再过 preflight。
`agent-finish` 同理：同步一次→跑项目测试→过 review-ready。
历史一旦被重写即报告 `PRIOR_EVIDENCE=STALE`，旧 SHA 证据作废重冻。

诊断与单步执行仍可用原语（`status` / `init` / `sync` / `preflight` /
`review-ready` / `gate-ready` / `merge-ready`），语义不变；
其中 `sync` 等在可见性未知时照样阻断，不因自动入口存在而放宽。

GitHub PR 模式用 PR merge commit 做最终集成，不用本地 `integrate`；
本地 `integrate` 只适用于明确约定本地集成的项目，且固定 `--no-ff`。

## 核心合同（优先记住这八条）

1. 默认集成分支是 `develop`（项目可配）。
2. feature → `develop` 默认 `git merge --no-ff`，不用 squash / rebase merge 做默认。
3. private 同步用 rebase，shared 同步用 merge；由 `branchctl` 按可见性选择。
4. shared 绝不自动 rebase，绝不 force push。
5. 可见性未知时宁可阻断，也不猜测。
6. 检查可自动，改写历史必须是显式动作；冲突一律保留原生状态交人工处理。
7. 远端存在同名分支不等于 shared；`init` / `share` 显式落盘才算数。
8. 安装与更新永不覆盖项目自己的 `AGENTS.md` 全文、分支策略与未知 workflow。

以上只是索引，具体判定算法、退出码、配置键、红线见
[policy-guide.md](references/policy-guide.md)，它是唯一的详细事实源。

## Agent 必须做

- 正常任务只走自动生命周期：`agent-start` → 开发 → `agent-finish`；
  单步原语（`preflight` / `sync` / `review-ready` / `gate-ready` /
  `merge-ready`）仅用于诊断、恢复与特殊流程，不得与自动入口混拼流程；
- 被 `REASON` 阻断时按 `ACTION` 执行对应命令，不绕过；
- 发起外部送审的同时执行 `freeze`，评审关闭后执行 `unfreeze`。

## Agent 禁止做

- 自行 `git rebase` / `git merge` 做 develop 同步；
- 在 `develop` / `main` / `master` 上直接做 feature 开发（策略放行除外）；
- `git reset --hard`、`git clean -fd`、任何 force push、自动删分支或 worktree；
- shared 分支 rebase；unknown 可见性下同步或集成；
- 让 pre-push hook / CI 自动改写历史。

## 项目规则优先级

```text
仓库项目级明确规则
  > 项目 .agent/branch-policy.yaml
    > Skill 默认规则
```

但项目规则不得放宽安全红线（第 4 条、第 8 节列举的下限），
放宽写法一律视为无效。

## 自动执行机制

```text
AGENTS.md 接入片段
  → 任务开始 branchctl agent-start
    → 开发
      → 任务收尾 branchctl agent-finish
        → pre-push hook 调 push-check（本地兜底：只拦不改）
          → GitHub Actions 调 ci-check（远端兜底：只验不改）
```

`preflight` 是 `agent-start` 内部调用的原语，不是正常任务的顶层入口；
单步原语只留给诊断、恢复与特殊流程。

## 按需加载

| 场景 | 去哪里 |
|---|---|
| 判定算法、退出码、配置键、红线、排障 | [references/policy-guide.md](references/policy-guide.md) |
| 安装 / 更新 / 模板细节 | [README.md](README.md) |
| 项目策略取值 | 目标项目的 `.agent/branch-policy.yaml` |
| 通用 Git 原子操作 | `dd-git-workflow` |
