# 分支策略详解（执行层规则，事实源头见 `dd-git-workflow`）

私有 / 共享分支同步方式的 canonical 事实归
`dd-git-workflow/references/branch.md`（“私有 / 共享分支同步”节）所有；
本文档只拥有本 Skill 执行层面的细节（判定算法实现、退出码、命令语义、
配置键、红线），与源头冲突时以源头为准并记录 finding。
项目 `.agent/branch-policy.yaml` 只做取值配置。

---

## 1. 核心合同（不可自行改变）

1. 默认集成分支为 `develop`，项目可通过 `integration_branch` 修改。
2. feature 最终合入 `develop` 默认使用 `git merge --no-ff`，
   不得默认改为 squash、rebase merge 或 fast-forward。
3. 私有（private）feature 同步 `develop` 使用
   `git fetch origin` + `git rebase origin/develop`。
4. 共享（shared）feature 同步 `develop` 使用
   `git fetch origin` + `git merge origin/develop`；
   同步性 merge 不强制 `--no-ff`；禁止自动 rebase，禁止 force push。
5. 可见性未知（unknown）时宁可阻断，也绝不猜测为 private 后 rebase。
6. 检查可以自动强制，改写历史必须是 Agent 的显式动作。

---

## 2. 可见性判定链

优先级从高到低：

1. **显式分支配置**（最高）：`branch.<分支名>.agentShared`，
   `true` 为 shared，`false` 为 private。
2. **项目策略默认值**：`feature.default_visibility`。
   该值只决定无参数 `init` 与 `agent-start` 落盘什么；
   落盘后即为普通显式配置，此后一切判定走显式路径。
   因此“按策略自动初始化”不是猜测：输入确定、落盘明确、全程打印
   `AUTO_INIT=true` 与 `SOURCE=policy`；显式配置永远优先。
   在显式落盘之前，当前可见性一律视为 `unknown`，
   `sync` / `integrate` / `share` 照样阻断，不因自动入口存在而放宽。
3. **无法安全确定**：返回 `VISIBILITY=unknown` + `DECISION=ACTION_REQUIRED`，
   要求先执行 `./scripts/branchctl init`（或 `share`）。

「远端存在同名分支」不得作为 shared 依据：
个人 private 分支同样经常 push 到远端备份。

`share` 只允许 private → shared 单向转换，不提供回退。
已共享的分支可能仍被他人、其它 Agent 或外部流程依赖，
回退为 private 会诱发历史重写风险。
可见性未知时 `share` 直接拒绝（`REASON=UNKNOWN_VISIBILITY`），
必须先 `init` 明确身份，不存在 unknown → shared 直通。

---

## 3. 同步判定算法

`branchctl` 从不使用「behind > 0 就强制同步」。
是否必须同步按以下输入综合判定（`must_sync_for_ref`）：

- 落后提交数（BEHIND）与 `sync.warning_behind_commits`（默认 20）；
- 分支年龄（自 merge-base 起的天数）与
  `branch_lifetime.warning_days / hard_days`（默认 3 / 7）；
- 路径重叠：feature 与 develop 相对 merge-base 的改动路径交集
  （`git merge-base` + `git diff --name-only`，路径级即可，不做语义分析）；
- 关键公共文件：develop 侧是否动了内置清单或
  `sync.critical_paths` 追加的路径；
- 当前阶段：`sync.require_before_review / require_before_gate /
  require_before_merge` 任一关闭时，对应阶段不再强制
  （push 检查与 CI 检查沿用 merge 要求）。

必须同步的条件（阶段开关打开时，满足任一即成立）：

```text
behind > 0 且（behind ≥ 预警数
              或 存在路径重叠
              或 develop 动了关键公共文件
              或 分支年龄 ≥ hard_days）
```

内置关键路径清单：`.agent/branch-policy.yaml`、常见锁文件与构建描述文件
（`package.json`、`package-lock.json`、`pnpm-lock.yaml`、`yarn.lock`、
`go.mod`、`go.sum`、`Cargo.toml`、`Cargo.lock`、`pyproject.toml`、
`poetry.lock`、`Pipfile`、`Gemfile`、`pom.xml`、gradle 文件、
`Dockerfile*`、`Makefile`、`CMakeLists.txt`）、
`.github/workflows/*`、`.githooks/*`、`scripts/branchctl`。

---

## 4. 命令语义与干净工作树要求

术语先行，避免与 `dd-workflow-runtime` 碰撞：本文件的 `preflight`
指分支准入检查（能否在这个分支上开工），不是 runtime 的工作流入口
Preflight；`*-ready` 指分支策略层的合入前检查，不是工作流 Stage Gate
（Stage Gate 不是 Git Delivery Gate，前者归调用方与 runtime 所有）。
`freeze` 冻的是自动同步动作，不是外部审查的送审候选绑定（后者归
外部审查流程与 runtime 状态所有，本工具只读写自家的
`branch.<名>.agentSyncFrozen`）。

每个命令的干净工作树要求按语义独立定义，
不得互相复用导致误判：

| 命令 | 只读 | 脏工作树 | 说明 |
|---|---|---|---|
| `agent-start` | 否（组合） | 允许进入（同步需要时照样拒绝） | 初始化→按需同步一次→preflight；失败透出原命令输出 |
| `agent-finish` | 否（组合） | 允许进入（各原语独立判定） | 同步一次→项目测试→review-ready；不做初始化、不提交 |
| `freeze/unfreeze` | 写配置 | 不判定 | 冻结/解冻自动同步；冻结只拦自动同步，不拦只读检查 |
| `status` | 是 | 仅报告 `DIRTY=` | 从不 fetch，从不修改 |
| `preflight` | 准入检查 | 告警但通过 | 开始修改前使用；增量开发常带未提交改动。但 `checks.before_work=true` 时若已存在必须同步条件则直接阻断（提前暴露，不等到 push 才拦） |
| `sync` | 否 | 拒绝（不自动 stash） | 冲突时保留原生状态并返回非 0 |
| `review-ready` | 是 | 允许 | 评审看的是提交基线 |
| `gate-ready` | 是 | 拒绝 | 门禁需要确定性的 HEAD 与基线 |
| `merge-ready` | 是 | 拒绝 | 同上 |
| `integrate` | 否 | 拒绝 | 集成前必须干净 |
| `push-check` | 是 | 不判定 | 只看已提交分支状态，绝不修改历史 |
| `ci-check` | 是 | 不适用 | 跑在 CI 检出上，兼容 detached HEAD |

`preflight` 默认执行 `git fetch origin` 获取最新基线，
可用 `--no-fetch` 跳过（离线时自动降级为本地基线并告警）。

---

## 5. 退出码合同

```text
0   成功 / 允许 / 就绪为真
10  参数用法错误
20  需要上层采取行动（需同步、需提交、需初始化、冲突待人工处理）
30  可见性不安全（unknown 时拒绝一切改写历史的操作）
40  仓库 / worktree / 分支状态非法
50  就绪检查未通过（REVIEW/GATE/MERGE/CI 返回 false）
```

所有就绪类输出均为机器可解析的 `KEY=VALUE` 行，
失败时必带稳定的 `REASON` 与 `ACTION`（如
`REASON=INTEGRATION_SYNC_REQUIRED` +
`ACTION=./scripts/branchctl sync`）。

---

## 6. 配置键一览

见 `templates/branch-policy.yaml` 注释。补充说明：

- `protection.allow_direct_on_integration`：是否允许直接在集成分支上
  开发，默认 `false`。打开后 `preflight` 放行，其它命令仍要求合法 feature。
- `checks.before_work`：`preflight` 是否在开工前就阻断必须同步的条件，
  默认 `true`。关闭后 `preflight` 回到只做准入不断同步的状态。
- `checks.test_command`：`agent-finish` 自动执行的本地项目测试命令，
  为空即跳过（`LOCAL_TESTS=skipped`，绝不声称通过）；非空时在仓库根目录
  用 bash 执行，非零退出即阻断收尾（`REASON=LOCAL_TESTS_FAILED`）。

## 6.2 本地测试与远端 CI 的边界（必读）

`LOCAL_TESTS=passed` 只是“本地命令跑过了”，**永不代表远端 CI 门禁通过，
也不得据此关闭任何必需远端 CI 的 Gate**。测试位置决策、CI 复用与触发、
“CI 优先、禁止本地替代”的完整合同归 `dd-workflow-runtime` 所有：

- 测试位置与“CI 不可用”的严格定义：`dd-workflow-runtime/references/test-location.md`；
- CI 发现、触发、等待与失败语义：`dd-workflow-runtime/references/ci.md`。

有必需远端 CI 门禁的项目：`agent-finish` 的本地测试最多算快速反馈，
仍须按上述两份合同走 CI 验证；`REVIEW_READY=true` 只是分支策略就绪，
不是 CI 通过，更不是工作流完成。
- `sync.critical_paths`：空格分隔的 shell 通配符，追加到内置关键清单。
- `shared.allow_force_push` 为安全下限字段：即使项目写成 `true`，
  `branchctl` 也绝不自动 force push（见第 8 节）。

读取实现只支持「顶层段.键: 标量值」子集，不依赖 yq / PyYAML，
因此不要在策略文件中使用嵌套列表或多行结构。

---

## 6.1 SHA 证据与重写历史

rebase 会改写 feature 历史：旧提交 SHA 随即悬空，此前钉在旧 SHA 上的
送审绑定与证据全部作废，外部审查的关闭前复验会判基线漂移（该复验机制归外部审查流程所有，本工具只如实报告新旧 HEAD）。因此：

- 自动同步只允许发生在尚无已冻结送审候选时；冻结载体为分支配置
  `branch.<名>.agentSyncFrozen`，由 `freeze` / `unfreeze` 管理：
  Agent 发起外部送审的同时执行 `freeze`，评审关闭后再 `unfreeze`；
- 冻结期间 `agent-start` 与 `agent-finish` 拒绝一切自动同步
  （private 也不例外，`REASON=SYNC_FROZEN`），只读检查不受影响；
- 一旦重写发生，工具在同步成功后**立即**输出 `HEAD_BEFORE` /
  `HEAD_AFTER` / `PRIOR_EVIDENCE`，之后测试或门禁再失败也不得吞掉该声明；
- merge 不改写历史，输出 `PRIOR_EVIDENCE=PRESERVED`；
- 需要长期多轮审查的任务尽早 `share`，用 merge 保 SHA 稳定。

## 7. worktree

一次安装即对全仓库所有 worktree 生效：
`scripts/branchctl`、`.agent/branch-policy.yaml`、`AGENTS.md` 均为版本内容，
新 worktree 自动获得，无需逐个复制 Skill。

分支可见性是 Git 分支配置（`git config branch.<名>.agentShared`），
天然随仓库共享，多 worktree 读取一致。

实现上统一使用 `git rev-parse` / `git config` 定位，
从不假设 `.git` 是目录（worktree 中它可能是文件），
也从不直接读取 `.git/config`。

`core.hooksPath` 是仓库级本地配置，多 worktree 共享，
安装器只设置一次；已有自定义值时告警且不覆盖。

---

## 8. 安全红线（项目配置不得放宽）

- 任何命令不得执行 `git reset --hard`、`git clean -fd`、
  `git push --force(-with-lease)`、自动删分支、自动删 worktree。
- shared 分支绝不自动 rebase；未知可见性绝不猜 private。
- pre-push hook 与 CI 只做验证，绝不自动 rebase / merge / commit / push。
- `shared.allow_force_push: true` 这类放宽一律视为无效，
  工具保持拒绝并告警。
- `install.sh` / `update.sh` 永不覆盖项目已有的
  `AGENTS.md` 全文、`branch-policy.yaml` 与未知来源的 workflow。
  `install.sh` 遇到来源未知的已有 `scripts/branchctl` /
  `.githooks/pre-push` 直接 fail-closed；
  `update.sh` 遇到残缺 marker（start/end 不是唯一有序）碰都不碰该文件。
- GitHub workflow 的触发分支由安装器按 `integration_branch` 生成，
  不是写死的 `develop`；`ci-check` 必须用 `--head-sha / --base-sha`
  传入 PR 真实两端，绝不拿 `GITHUB_SHA`（常为合成 merge commit）冒充。

---

## 9. GitHub PR 模式

采用 PR / Merge Queue 的项目：

- PR 目标分支应为项目配置的集成分支（默认 `develop`），模板 workflow
  由安装器按策略生成触发分支；
- CI 检出使用 `fetch-depth: 0`，保证 `ci-check` 能算出 merge-base；
- `ci-check` 通过 `--head-ref / --base-ref` 或
  `GITHUB_HEAD_REF / GITHUB_BASE_REF` 确定分支，不依赖
  `git branch --show-current`（detached HEAD 下为空）；
- 最终集成由 PR 的 merge commit 完成，不推荐本地 `integrate`；
  默认合入方式应保持 merge commit，不用 squash / rebase merge 做默认。

---

## 10. 常见阻断速查

| 输出 | 含义 | 动作 |
|---|---|---|
| `REASON=UNKNOWN_VISIBILITY` | 未显式初始化 | `./scripts/branchctl init` |
| `REASON=INTEGRATION_SYNC_REQUIRED` | 存在必须同步条件 | `./scripts/branchctl sync` |
| `REASON=DIRTY_WORKTREE` | 该阶段要求干净 | 提交改动后重试 |
| `REASON=INTEGRATION_BRANCH` | 在集成分支上做 feature 开发 | 切到 feature 分支 |
| `REASON=NO_BASELINE` | 无可用基线（常为离线或浅克隆） | `git fetch origin` / `fetch-depth: 0` |
| `REASON=UNEXPECTED_BASE` | PR 目标不是集成分支 | 改 PR 目标为集成分支 |
| `REASON=UNRESOLVED_HEAD` | CI 内找不到源分支引用（且无明确 SHA） | 用 `--head-sha` 传入 PR 源端真实提交 |
| `REASON=LOCAL_TESTS_FAILED` | `agent-finish` 中本地项目测试失败 | 修复测试失败后重试（另见 §6.2：本地通过不等于 CI 通过） |
| `REASON=SYNC_FROZEN` | 分支已冻结自动同步（送审候选中） | 评审关闭后 `unfreeze` 再重试 |
| `REASON=INTEGRATION_BRANCH_CHECKED_OUT_ELSEWHERE` | 集成分支被另一 worktree 占用 | 改用 PR；或在占用的 worktree 内手工 merge（不得再调 integrate） |
