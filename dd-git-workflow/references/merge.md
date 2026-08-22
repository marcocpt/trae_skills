> 迁移来源：`dd-git-merge/SKILL.md`。现作为按需 reference 使用，不参与顶层 Skill 路由。

# Git 合并流程

## 概述

合并流程遵循 merge-only 原则，禁止 rebase。本技能涵盖每日合并、Push 流程、完整 Merge 流程和 Commit 规范。完整工作流总览见 [dd-git-workflow](../../dd-git-workflow/SKILL.md)。

本技能按 `invocation_mode=helper` 返回调用方，不自行 Host Close。直接承接用户目标时由顶层 `standalone` 会话按 [dd-workflow-runtime/ask](../../dd-workflow-runtime/references/ask.md) 收尾。

## merge-only 原则与混合模式

坚持 merge-only 原则，不引入 rebase。在 merge 基础上引入混合模式：

| 模式 | 命令 | 适用场景 | 历史保留 |
|------|------|---------|---------|
| 默认 | `git merge --no-ff origin/develop` | 常规合并、功能分支合并 | 保留分支历史（merge commit） |
| 简化 | `git merge --ff-only origin/develop` | 连续小修复、纯同步操作 | 线性历史，无 merge commit |

**使用约束**：

- `--ff-only` 仅用于"分支已无独立提交"或"纯同步上游"场景
- 功能合并到 develop 一律使用 `--no-ff`，保留分支边界
- 禁止用 `--ff-only` 替代功能合并以"简化历史"

## 每天必须合并

"每天同步"升级为"每天必须合并"：AI Coding 场景下，分支每天必须有合并动作。

**含义**：

- **拉取上游**：`git fetch origin && git merge origin/develop` 同步上游改动
- **推送可合并部分**：将已完成且通过自检的部分合并回 develop

**为什么"必须合并"而不只是"同步"**：

- 同步只拉取上游，不回馈下游，分支仍然是单向流动
- 必须合并强制 AI Agent 把可合并的成果及时回到主干，避免分支长期独立
- 长分支即使每天同步，冲突也会随分支存活时间指数增长

**每日同步脚本**：`scripts/daily-sync.sh`

```bash
# 用法：在 feature 分支上执行
bash scripts/daily-sync.sh
# 冲突时输出冲突文件清单并以退出码 2 退出
```

## Push 流程（每天可合并部分回 develop）

**触发条件**：本分支有可独立验证的提交（如修复 bug、完成子功能、补充文档）

**操作流程**：

1. 先执行 `scripts/pre-merge-check.sh` 自检，确认 `all_pass=true`
2. 推送本分支到远端：`git push origin <branch>`
3. 选择合并方式：
   - 远端 PR：在远端开 PR，审查通过后合并到 develop
   - 本地直合并：`git checkout develop && git pull origin develop && git merge --no-ff <branch> && git push origin develop`
4. 合并完成后回到原分支：`git checkout <branch>`

**不可合并情况**：

- 功能未完成（仅部分模块就绪，未达到验收标准）
- 测试未通过（含 SwiftLint strict 未通过）
- 文档未同步（修改了用户可见行为、技术架构、UI 行为但未同步对应文档）

上述情况下仅执行 pull 同步上游，不执行 push 合并，避免污染 develop。

## Merge 完整 5 步流程

| 步骤 | 动作 | 命令/工具 | 失败处理 |
|------|------|----------|---------|
| ① | merge develop 到 feature | `git merge --no-ff origin/develop` | 解决冲突后继续 |
| ② | merge-tree 预检 | `git merge-tree --write-tree origin/develop HEAD` | severity=high 禁止合并 |
| ③ | Build / Tests / SwiftLint | 项目测试脚本 | 修复后重新执行 |
| ④ | AI 自检 | `scripts/pre-merge-check.sh` | all_pass=false 禁止合并 |
| ⑤ | PR / Merge | `git merge --no-ff` 到 develop | PR 审查通过后合并 |

## 合并后动作

- 立即清理 worktree：`git worktree remove <path>`
- 立即删除本地分支：`git branch -d <branch>`
- 通知其他活跃 Agent 拉取 develop

## Commit 规范

### type 列表

- `feat:` 新功能
- `fix:` 缺陷修复
- `refactor:` 重构（不改变行为）
- `test:` 测试相关
- `docs:` 文档相关
- `style:` 格式调整（不改逻辑）
- `chore:` 构建、依赖、配置等杂项

### 规范约束

- 避免使用 `update`、`modify` 等无意义提交信息
- subject 使用简洁祈使语气，不超过 50 字符
- 一个 commit 只做一件事，禁止混合多个独立改动
- 公共文件修改必须加 `PublicFile: <路径>` tag

### 示例

```text
feat(F3.1): add two-stage OCR acceleration

PublicFile: Sources/MacimCore/OCR/OCREngine.swift
```

## 禁止事项

- 长期未同步 develop 的分支（超过 1 天未合并视为陈旧）
- Merge 前不测试
- 已共享分支频繁 Rebase
- **禁止用 `--ff-only` 替代功能合并**：功能合并必须 `--no-ff` 保留分支历史
- **禁止跳过 AI 自检直接合并**：合并前必须运行 `scripts/pre-merge-check.sh`
- **禁止用固定 sleep 掩盖合并竞态**：合并冲突必须显式解决
