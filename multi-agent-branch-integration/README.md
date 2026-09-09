# multi-agent-branch-integration

多个 Agent App、多 worktree、多 feature 分支并行开发时，
由仓库内统一工具做分支判断、同步、检查和强制，
而不依赖每个 Agent 自己记住 Git 策略。

支持 CodeBuddy、Codex、Claude Code、Trae、Cursor、OpenCode、
ChatGPT Agent 等任何能跑 shell 的 Agent，不依赖任一 App 的专有能力。
只需要 `bash` + `git`（+ GitHub Actions YAML 用于远端检查）。

规则详解见 `references/policy-guide.md`。

---

## 第一次安装（项目维护者执行一次）

```bash
/path/to/multi-agent-branch-integration/install.sh .
```

安装器会：装入 `scripts/branchctl` 与 `.githooks/pre-push`；
缺失时创建 `.agent/branch-policy.yaml`（已有绝不覆盖）；
向 `AGENTS.md` 追加带 marker 的接入片段（幂等）；
设置 `core.hooksPath=.githooks`；缺失时安装 GitHub workflow。
重复执行安全，第二次不复制、不覆盖、不重复追加。

更新运行时（保留项目策略）：

```bash
/path/to/multi-agent-branch-integration/update.sh .
```

本地改过受管文件时默认报冲突并退出非 0，
确认后可加 `--force-managed-files` 强制。

## feature 第一次初始化（每个 feature 一次）

```bash
./scripts/branchctl init --private   # 个人分支，可安全重写历史
./scripts/branchctl init --shared    # 多人/Agent共用，禁止 rebase
```

不带参数时按 `.agent/branch-policy.yaml` 的 `feature.default_visibility`
落盘。未初始化的分支可见性一律视为未知，同步与集成会被阻断。

## 日常开发（每个 Agent 每次：两个自动入口）

```bash
./scripts/branchctl agent-start    # 任务开始：初始化→同步→准入，一次搞定
./scripts/branchctl agent-finish   # 任务收尾：同步→测试→review-ready，一次搞定
```

`agent-start` 通过（`AGENT_START=true`）才能改动产物；
`agent-finish` 通过（`REVIEW_READY=true`）才能送审。
单步命令（`init` / `preflight` / `status` / `sync` / `review-ready`…）
照常保留，用于诊断与特殊流程。

## 评审与门禁

```bash
./scripts/branchctl review-ready   # 评审前，只读
./scripts/branchctl gate-ready     # 门禁前，只读，要求工作树干净
./scripts/branchctl merge-ready    # 集成前，只读，要求工作树干净
```

失败时看 `REASON` + `ACTION`，例如：

```text
MERGE_READY=false
REASON=INTEGRATION_SYNC_REQUIRED
ACTION=./scripts/branchctl sync
```

## GitHub PR 模式（推荐）

推荐 PR + CI + Merge Queue：PR 指向项目配置的集成分支（默认 `develop`），
CI 自动跑 `ci-check`，最终用 merge commit 合入，
不把 squash / rebase merge 当默认。
本地 `integrate` 只适用于约定本地集成的项目：

```bash
./scripts/branchctl integrate   # 本地 develop 上生成 --no-ff 合并提交
```

## 命令一览

| 命令 | 读写 | 说明 |
|---|---|---|
| `agent-start` | 检查+按需写 | 任务开始自动入口（初始化→同步一次→preflight） |
| `agent-finish` | 检查+按需写 | 任务收尾自动入口（同步一次→测试→review-ready） |
| `freeze/unfreeze` | 写配置 | 冻结/解冻自动同步（送审期间防漂移） |
| `status` | 只读 | 当前分支可见性、落后/领先数、年龄、决策 |
| `init` | 写配置 | 落盘显式可见性，幂等 |
| `share` | 写配置 | private 转 shared（单向） |
| `preflight` | 检查 | 改动前准入；脏工作树只告警 |
| `sync` | 写历史 | private=rebase，shared=merge；冲突交人工 |
| `review-ready` | 只读 | 评审基线验证 |
| `gate-ready` | 只读 | 更严格，要求干净 |
| `merge-ready` | 只读 | 集成前最终验证 |
| `integrate` | 写历史 | 本地 `--no-ff` 集成，不推送 |
| `push-check` | 只读 | pre-push 调用，只拦不改 |
| `ci-check` | 只读 | CI 调用，兼容 detached HEAD |

`--no-fetch` 可跳过远端拉取（离线时自动降级并告警）。
退出码与阻断速查见 `references/policy-guide.md`。
