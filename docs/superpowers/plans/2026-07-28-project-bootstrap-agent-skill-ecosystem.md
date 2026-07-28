# 项目 Bootstrap Agent Skill 生态重构实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `subagent-driven-development`（用户明确要求子代理时）或 `executing-plans` 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法跟踪进度。本次已选择内联执行，不启动子代理。

**目标：** 将项目 Bootstrap 工作流及其直接依赖重构为可在 Trae/Codex 中跨会话恢复、按需加载、低重复询问并保持质量 Gate 的 Agent Skill 生态。

**架构：** `dd-project-bootstrap-workflow/SKILL.md` 只保留路由、状态、依赖图、Gate 和 Handoff，详细治理规则拆入三份 reference。共享 skill 提供宿主询问、状态恢复和风险分级审查协议；原子 writer 消费统一上游上下文；新增 `dd-write-phase-contract`；最终统一交接给 Feature workflow。

**技术栈：** Markdown Agent Skills、YAML frontmatter、Git、Python 3 静态验证、`rg`、Codex `quick_validate.py`

---

## 文件结构

### 创建

- `dd-project-bootstrap-workflow/references/docs-governance.md`：项目文档目录、SSOT、同步、History/ADR 和阅读策略。
- `dd-project-bootstrap-workflow/references/execution-contract.md`：Preflight、状态模型、节点 Gate、审查预算、子 skill 协议和 Handoff。
- `dd-project-bootstrap-workflow/references/brownfield-policy.md`：模式判定、兼容分类、公开面、lint ratchet 和架构冻结。
- `dd-project-bootstrap-workflow/tests/baseline-3-resume-without-reasking.md`：恢复后不重复询问。
- `dd-project-bootstrap-workflow/tests/baseline-4-trae-final-ask.md`：Trae 最终 ASK。
- `dd-write-phase-contract/SKILL.md`：准备/迁移阶段需求与验收 writer。
- `dd-write-phase-contract/tests/baseline-1-brownfield-classification.md`：Characterization 分类映射。
- `dd-write-phase-contract/tests/baseline-2-known-defect-not-ac.md`：已知缺陷不进入目标 AC。
- `dd-write-phase-contract/tests/baseline-3-upstream-context.md`：上游事实复用。

### 修改

- `dd-shared-ask/SKILL.md`：宿主无关询问和 Trae 会话结束合同。
- `dd-shared-state/SKILL.md`：增加 `project-bootstrap` 状态类型和恢复验证。
- `dd-shared-subagent/SKILL.md`：固定语义视角、风险分级执行。
- `dd-project-bootstrap-workflow/SKILL.md`：重写为短编排入口。
- `dd-project-bootstrap-workflow/tests/baseline-1-greenfield-skip-phase-contract.md`：改用兼容义务判断。
- `dd-project-bootstrap-workflow/tests/baseline-2-brownfield-baseline-first.md`：改用 requested entry + gap scan。
- `dd-brownfield-baseline/SKILL.md`：兼容义务、处置分类和上游上下文。
- `dd-project-research/SKILL.md`：上游上下文和风险触发研究。
- `dd-write-roadmap/SKILL.md`：消费上游事实和 Gap Scan。
- `dd-write-architecture-contract/SKILL.md`：状态三阶段与双公开面。
- `dd-write-coding-standards/SKILL.md`：Greenfield/ Brownfield lint 策略。
- `dd-write-ai-conventions/SKILL.md`：短入口、nested `AGENTS.md`、薄 Trae adapter 和最终 ASK。
- `dd-feature-development-workflow/SKILL.md`：消费统一 Bootstrap Handoff。

---

### 任务 1：重构共享询问、状态和审查协议

**文件：**

- 修改：`dd-shared-ask/SKILL.md`
- 修改：`dd-shared-state/SKILL.md`
- 修改：`dd-shared-subagent/SKILL.md`

- [ ] **步骤 1：运行旧协议扫描并确认缺口**

运行：

```bash
rg -n "project-bootstrap|requested_entry|session_close|结束本次任务|review_level|low.*standard.*high" \
  dd-shared-ask/SKILL.md \
  dd-shared-state/SKILL.md \
  dd-shared-subagent/SKILL.md
```

预期：找不到完整的 Bootstrap 状态、Trae 会话结束合同和 `low/standard/high` 审查等级，命令返回 1。

- [ ] **步骤 2：为 `dd-shared-ask` 增加宿主无关决策协议**

在“结构化询问”后加入以下完整规则：

```markdown
## 决策协议

需要用户决策时：

1. 优先使用宿主当前可用的结构化询问机制；
2. 提供 2–4 个互斥选项，有充分理由时标记推荐项；
3. 结构化工具不可用时，使用包含相同选项的简短文本；
4. 一次只问一个阻塞决策；
5. 已存在于上游状态或已批准文档中的事实不得重复询问；
6. happy path 不为形式确认而暂停，只有歧义、失败、冲突或风险分支才 ASK。

## Trae 会话结束合同

当调用方声明 `host=trae` 且工作流达到最终完成 Gate 时：

1. 禁止直接结束会话；
2. 必须使用 Trae 的结构化 ASK 询问：
   - `结束本次任务`
   - `还有其他任务`
3. 选择“还有其他任务”时接收新任务并继续；
4. 选择“结束本次任务”后，先持久化 `status=completed`，再输出最终摘要；
5. null 输入必须重新询问，不能把 null 当作结束。

Codex 和其他宿主不强制无意义的结束确认，除非用户或项目规则明确要求。
```

- [ ] **步骤 3：将 `dd-shared-state` 泛化到 Bootstrap**

把参数表扩展为：

```markdown
| 工作流 | `WORKFLOW_TYPE` | 文件名 | 进度字段 |
|---|---|---|---|
| bug 修复 | `bug-fix` | `bug-fix-state.json` | `current_step` |
| 新特性 | `feature-development` | `feature-development-state.json` | `current_step` |
| 项目启动 | `project-bootstrap` | `project-bootstrap-state.json` | `current_node` |
```

在通用状态字段中加入：

```json
{
  "schema_version": 1,
  "workflow_type": "project-bootstrap",
  "status": "active",
  "worktree_path": "/absolute/path/to/worktree",
  "base_branch": "develop",
  "current_node": "preflight",
  "created_at": "2026-07-28T00:00:00Z"
}
```

加入 Bootstrap 特有字段：

```json
{
  "project_mode": "brownfield",
  "host": "trae",
  "requested_entry": "roadmap",
  "completed_nodes": ["preflight", "docs-governance"],
  "artifacts": {},
  "decisions": [],
  "blocking_gaps": ["brownfield-baseline"],
  "deferred_gaps": [],
  "handoff": {}
}
```

并明确：

```markdown
- 恢复状态后必须验证 `worktree_path`、已记录产物和适用规则仍存在；
- 状态缺失时从仓库事实重建，禁止默认从头 grill；
- `status=completed` 的状态文件不阻塞新工作流；
- Bootstrap Handoff 被下游确认前不得删除状态；
- 并发检查必须同时覆盖三个状态文件。
```

- [ ] **步骤 4：将 `dd-shared-subagent` 改为风险分级审查**

保留三个固定语义视角，替换“所有检查必须三子代理”为：

```markdown
## 审查语义与执行等级

所有检查必须覆盖：

1. 覆盖与范围；
2. 一致与正确；
3. 可验证与可观测。

| `review_level` | 执行方式 | 适用情况 |
|---|---|---|
| `low` | 主 Agent 一次完成三视角自检 | 机械迁移、链接和低风险格式变更 |
| `standard` | 一个独立 reviewer 完成三视角 | 普通文档和常规节点 |
| `high` | 三个方向 reviewer 并行，主 Agent 汇总 | Brownfield 基线、架构、兼容迁移和高风险 UI/数据变更 |

没有子 Agent 能力时，使用同一 Agent 的独立检查轮次替代。执行方式可以降级，检查项不得减少。
```

处理规则改为：

```markdown
- blocker 和“必须修复”项自动修复并以同等级复验；
- 建议项只有涉及范围、产品语义、架构或高风险处置时 ASK；
- `low` 发现跨文档风险时升级到 `standard`；
- `standard` 出现冲突或兼容性争议时升级到 `high`；
- 禁止为了省 Token 跳过确定性 lint、解析、链接或映射检查。
```

- [ ] **步骤 5：验证共享协议**

运行：

```bash
python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py dd-shared-ask
python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py dd-shared-state
python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py dd-shared-subagent
rg -n "结束本次任务|还有其他任务|project-bootstrap-state.json|review_level" \
  dd-shared-ask/SKILL.md \
  dd-shared-state/SKILL.md \
  dd-shared-subagent/SKILL.md
git diff --check
```

预期：三个 validator 均返回 `Skill is valid!`；四个关键合同均可定位；`git diff --check` 无输出。

- [ ] **步骤 6：Commit**

```bash
git add dd-shared-ask/SKILL.md dd-shared-state/SKILL.md dd-shared-subagent/SKILL.md
git commit -m "refactor(skills): add portable bootstrap runtime contracts"
```

---

### 任务 2：新增 `dd-write-phase-contract`

**文件：**

- 创建：`dd-write-phase-contract/SKILL.md`
- 创建：`dd-write-phase-contract/tests/baseline-1-brownfield-classification.md`
- 创建：`dd-write-phase-contract/tests/baseline-2-known-defect-not-ac.md`
- 创建：`dd-write-phase-contract/tests/baseline-3-upstream-context.md`

- [ ] **步骤 1：建立三个失败场景**

三个 baseline 分别写入以下确定答案：

```markdown
# Brownfield classification

输入包含 PRESERVE、ADAPT、REPLACE、KNOWN_DEFECT、TOLERATED_COMPATIBILITY、REVIEW。

预期：
- PRESERVE 映射保持行为 AC；
- ADAPT 写目标语义 AC；
- REPLACE 不保留旧行为；
- KNOWN_DEFECT 禁止进入目标 AC；
- TOLERATED_COMPATIBILITY 明确兼容范围后才能进入 AC；
- REVIEW 阻塞合同批准。
```

```markdown
# Known defect

输入：现有 Characterization Test 证明错误结果为 0，分类为 KNOWN_DEFECT。

预期：阶段合同把“修复错误结果”写入目标 AC，不把“结果为 0”写成保留行为。
```

```markdown
# Upstream context

输入状态已经确认 host、project_mode、platform、scope、baseline 和 architecture。

预期：writer 直接消费这些事实，只询问缺失的阶段特有 blocker。
```

验证失败：

```bash
test -f dd-write-phase-contract/SKILL.md
```

预期：返回 1。

- [ ] **步骤 2：创建 skill frontmatter 与边界**

`dd-write-phase-contract/SKILL.md` 以以下内容开始：

```markdown
---
name: dd-write-phase-contract
description: 当需要为项目准备阶段、Brownfield 迁移阶段或兼容性阶段编写 `{X}_01_阶段需求与验收.md` 时使用。覆盖阶段 Goal、Scope、FR、NFR、Constraints、Acceptance Criteria、Out of Scope、Decision Freedom 和 Exit Gate；消费 Bootstrap baseline/roadmap/architecture 上游事实，不用于普通功能规格、设计文档或实现计划。
---

# 编写阶段需求与验收合同

## 核心边界

本 skill 只编写阶段合同。它不编写设计、测试用例表、实现计划或代码。

首次独立触发时执行最小 Preflight；被 Bootstrap 调用时消费上游上下文，禁止重复询问已解决事实。
```

- [ ] **步骤 3：写入流程与 Gate**

使用以下固定流程：

```markdown
## 流程

1. 读取上游上下文、docs governance、Roadmap、Architecture 和 Brownfield Baseline；
2. 验证阶段边界不扩大 Roadmap 的 IN/OUT；
3. 对 Characterization Test 执行处置映射；
4. 只询问缺失的阶段特有 blocker；
5. 编写 `{X}_01_阶段需求与验收.md`；
6. 按 `review_level` 覆盖三个审查视角；
7. 修复 blocker，更新 Bootstrap state。

## 必含章节

1. Goals
2. Scope
3. Functional Requirements
4. Non-Functional Requirements
5. Constraints
6. Acceptance Criteria
7. Out of Scope
8. Decision Freedom
9. Exit Gate

## HARD-GATE

- Roadmap 边界存在冲突时停止；
- REVIEW 分类未解决时停止；
- KNOWN_DEFECT 被写成保留 AC 时停止并修正；
- AC 无验证方式时停止并修正；
- 产物未经语义审查时不得标记 approved。
```

- [ ] **步骤 4：验证新 skill 与场景文件**

运行：

```bash
python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py dd-write-phase-contract
test "$(find dd-write-phase-contract/tests -maxdepth 1 -name 'baseline-*.md' | wc -l | tr -d ' ')" = "3"
rg -n "KNOWN_DEFECT|TOLERATED_COMPATIBILITY|REVIEW|禁止重复询问|Exit Gate" dd-write-phase-contract
git diff --check
```

预期：validator 通过；baseline 数量为 3；五类关键合同可定位；补丁卫生通过。

- [ ] **步骤 5：Commit**

```bash
git add dd-write-phase-contract
git commit -m "feat(skills): add phase contract writer"
```

---

### 任务 3：拆分并重写 Bootstrap 核心

**文件：**

- 创建：`dd-project-bootstrap-workflow/references/docs-governance.md`
- 创建：`dd-project-bootstrap-workflow/references/execution-contract.md`
- 创建：`dd-project-bootstrap-workflow/references/brownfield-policy.md`
- 修改：`dd-project-bootstrap-workflow/SKILL.md`

- [ ] **步骤 1：记录重构前基线**

运行：

```bash
wc -l dd-project-bootstrap-workflow/SKILL.md
rg -n "^## docs 治理规范|^## 流程|^## 步骤 0|^## 步骤 9" dd-project-bootstrap-workflow/SKILL.md
```

预期：`SKILL.md` 为 679 行；docs 治理从第 38 行开始，流程约从第 411 行开始。

- [ ] **步骤 2：抽取 docs governance**

把当前 `SKILL.md` 中“docs 治理规范”完整迁移到 `references/docs-governance.md`，同时修正：

```markdown
- 技术探针按风险触发，不再写“可选，greenfield 必含”；
- Architecture 使用 hypothesis → provisional → approved baseline → frozen；
- `AskUserQuestion` 改为引用 `dd-shared-ask` 的宿主协议；
- Git 分支/merge/rebase 细则改为引用 `dd-git-workflow`；
- AI 阅读策略明确“Always read / Read when relevant / Do not preload”。
```

`references/docs-governance.md` 顶部加入：

```markdown
# Docs Governance Reference

仅在创建或校验根目录 `docs.md`、目录、SSOT、同步或归档规则时读取。不要为模式判定或状态恢复预加载本文件。
```

- [ ] **步骤 3：创建执行合同 reference**

`references/execution-contract.md` 必须包含：

```markdown
# Bootstrap Execution Contract

## Preflight
- 检测 host、worktree、适用规则、requested entry 和已有产物；
- 恢复或重建 `project-bootstrap-state.json`；
- 将产物标记为 missing、partial、valid、stale 或 conflicting；
- 生成 blocking_gaps 和 deferred_gaps；
- 只询问无法从事实推断的 blocker。

## Node contract
每个节点声明 requires、produces、gate、next。

## Workflow Gate
artifact exists + validated + decisions resolved + state persisted + blockers zero。

## Delivery Gate
Git、lint、test、commit、push 和 PR 由项目规则与 dd-git-workflow 决定。

## Child invocation
传递 host、mode、workspace、resolved decisions、artifact paths、review level 和 delivery policy；子 skill 不得重复询问。

## Handoff
统一交给 dd-feature-development-workflow，包含 Goal、Scope、Mode、Selected Feature/Phase、Required Reading、Relevant Files、Constraints、Acceptance Criteria/Requirements Seed、Verification、Out of Scope、Resolved Decisions。

## Host close
Trae 必须 ASK“结束本次任务 / 还有其他任务”；Codex 按项目规则正常交付。
```

- [ ] **步骤 4：创建 Brownfield policy reference**

`references/brownfield-policy.md` 写入完整政策：

```markdown
# Brownfield Policy

## Mode
Greenfield 无历史兼容义务；Brownfield 存在必须理解、保留、适配、替换或明确废弃的既有行为。

## Characterization disposition
PRESERVE → 保持行为 AC
ADAPT → 目标语义 AC
REPLACE → 不保留旧行为
KNOWN_DEFECT → 禁止进入目标 AC
TOLERATED_COMPATIBILITY → 明确范围后进入 AC
REVIEW → 阻塞

## Public surfaces
Legacy Compatibility Surface 只能经明确决策缩减。
Target Public Surface 可经 Requirements + Architecture Review/ADR 新增。

## Quality ratchet
历史违规建 baseline；changed code 不新增违规；new code 遵守完整规范；CI 使用 ratchet。

## Technical validation
只有未验证且影响 Roadmap/Architecture 的高风险假设才强制技术探针。
```

- [ ] **步骤 5：重写短 `SKILL.md`**

保留 frontmatter，正文按以下顺序组织：

```markdown
# 项目 Bootstrap 工作流

## 目标
把 Greenfield/Brownfield repo 推进到可由 Feature workflow 稳定开发的状态。

## 核心原则
1. Flexible entry, strict exit.
2. Brownfield requires baseline.
3. One fact, one SSOT.
4. Workflow orchestrates; child skills author.
5. Resolved facts are inherited, never re-asked.
6. Workflow Gate is not Git commit.
7. Review semantics are fixed; execution cost follows risk.

## 首步：Preflight
读取 `references/execution-contract.md` 的 Preflight 和状态章节并执行。

## 依赖图
Preflight → Docs Governance → Baseline?/Research? → Roadmap → Architecture → Coding Standards → AI Conventions → Phase Contract? → Handoff。

## 节点路由
- docs-governance：需要创建或校验 docs.md 时读取 docs-governance reference；
- brownfield-baseline：Brownfield 强制；
- research：风险触发；
- roadmap：所有模式强制；
- architecture-contract：所有模式强制；
- coding-standards：所有模式强制；
- ai-conventions：所有模式强制；
- phase-contract：Brownfield 强制，Greenfield 默认跳过；
- handoff：统一交给 dd-feature-development-workflow。

## Exit Gate
验证模式要求的产物、状态、blocker、Handoff 和宿主结束合同。

## References
- docs governance：`references/docs-governance.md`
- execution：`references/execution-contract.md`
- brownfield：`references/brownfield-policy.md`
```

正文同时列出七个子 skill 的精确相对路径，并明确首次修改文件前复用 `dd-shared-ask` 的 worktree 选择。

- [ ] **步骤 6：验证瘦身与链接**

运行：

```bash
python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py dd-project-bootstrap-workflow
test "$(wc -l < dd-project-bootstrap-workflow/SKILL.md)" -le 320
for f in \
  dd-project-bootstrap-workflow/references/docs-governance.md \
  dd-project-bootstrap-workflow/references/execution-contract.md \
  dd-project-bootstrap-workflow/references/brownfield-policy.md; do
  test -s "$f"
done
rg -n ">=1 个源文件.*brownfield|严格按 0→1→2→3→4→5→6→7→8→9|git log --oneline -1.*禁止" \
  dd-project-bootstrap-workflow/SKILL.md
git diff --check
```

预期：validator 通过；核心文件不超过 320 行；三份 reference 非空；旧矛盾扫描返回 1；补丁卫生通过。

- [ ] **步骤 7：Commit**

```bash
git add dd-project-bootstrap-workflow/SKILL.md dd-project-bootstrap-workflow/references
git commit -m "refactor(bootstrap): split orchestration from policy"
```

---

### 任务 4：更新 Baseline、Research 与 Roadmap 子 skill

**文件：**

- 修改：`dd-brownfield-baseline/SKILL.md`
- 修改：`dd-project-research/SKILL.md`
- 修改：`dd-write-roadmap/SKILL.md`

- [ ] **步骤 1：加入统一上游上下文协议**

三个文件都加入：

```markdown
## 上游上下文协议

被 `dd-project-bootstrap-workflow` 调用时，先读取其传入的 project mode、host、workspace、resolved decisions、artifact paths、review level 和 delivery policy。

- 已解决事实不得重复询问；
- 只询问本产物缺失的 blocker 或新增决策；
- 发现上游冲突时返回 blocker；
- 独立触发时才执行本 skill 的最小 Preflight。
```

- [ ] **步骤 2：修订 Baseline 语义**

把 Brownfield 定义改为历史义务，并把矩阵扩展为：

```markdown
| CAP | Disposition | Behavior class | Legacy surface | Target surface | Reason | Evidence |
|---|---|---|---|---|---|---|
```

Disposition 固定：

```text
PRESERVE / ADAPT / REPLACE / KNOWN_DEFECT / TOLERATED_COMPATIBILITY / REVIEW
```

Gate 要求 REVIEW 阻塞，KNOWN_DEFECT 不得进入兼容 allowlist。

- [ ] **步骤 3：修订 Research 风险触发**

把固定调研/探针改为：

```markdown
技术调研仅在以下情况强制：

- 未验证假设会改变 Roadmap；
- 未验证假设会改变架构边界；
- 外部 API、平台、性能或兼容性证据不足；
- 用户明确要求调研。

已有可靠证据时记录证据并跳过重复研究。Bootstrap 已确认的平台、目标和技术栈不得重新 grill。
```

- [ ] **步骤 4：修订 Roadmap 输入与 Gate**

明确 Roadmap：

```markdown
- 消费 Preflight Gap Scan、Research 与 Brownfield Baseline；
- Goal/IN/OUT/Exit Gate 是阶段边界 SSOT；
- Greenfield 空骨架不因存在源文件切换 Brownfield；
- 子 skill 不重新询问上游已确认目标、平台、模式；
- Review 执行方式由 `review_level` 决定。
```

- [ ] **步骤 5：验证并提交**

运行：

```bash
for d in dd-brownfield-baseline dd-project-research dd-write-roadmap; do
  python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$d"
done
rg -n "上游上下文协议|不得重复询问|review_level" \
  dd-brownfield-baseline/SKILL.md \
  dd-project-research/SKILL.md \
  dd-write-roadmap/SKILL.md
rg -n "PRESERVE|KNOWN_DEFECT|Legacy.*Surface|Target.*Surface" dd-brownfield-baseline/SKILL.md
git diff --check
git add dd-brownfield-baseline/SKILL.md dd-project-research/SKILL.md dd-write-roadmap/SKILL.md
git commit -m "refactor(skills): consume bootstrap context upstream"
```

预期：三个 validator 通过；协议和分类可定位；补丁卫生通过；提交成功。

---

### 任务 5：更新 Architecture、Coding Standards 与 AI Conventions

**文件：**

- 修改：`dd-write-architecture-contract/SKILL.md`
- 修改：`dd-write-coding-standards/SKILL.md`
- 修改：`dd-write-ai-conventions/SKILL.md`

- [ ] **步骤 1：加入统一上游上下文协议**

复用任务 4 的“上游上下文协议”，并把无条件“三子代理审查”改为遵循 `dd-shared-subagent` 的 `review_level`。

- [ ] **步骤 2：修订 Architecture 状态与公开面**

加入：

```markdown
## 契约状态

1. `hypothesis`：尚未验证的架构假设；
2. `provisional`：已有技术证据但未经过真实功能；
3. `approved-baseline`：足以约束首个 Feature，是 Bootstrap Exit Gate 所需状态；
4. `frozen`：经过首个真实实现证据后冻结。

Bootstrap 不得把 `approved-baseline` 误写成永久冻结。

## Public Surface

- Legacy Compatibility Surface：来源于 Brownfield Baseline，只能经明确决策缩减；
- Target Public Surface：来源于 Requirements + Architecture Review/ADR，可以新增；
- 两者必须分表维护，禁止把“legacy 只减不增”解释为项目永远不能新增 Public API。
```

- [ ] **步骤 3：修订 Coding Standards 的 lint 策略**

加入：

```markdown
## Lint 策略

### Greenfield
- zero new lint violations；
- error 为零；
- 项目确认后将 warning 作为 error。

### Brownfield
- 现有违规建立 baseline；
- changed code 不新增违规；
- new code 遵守完整标准；
- CI 使用 ratchet；
- Bootstrap 不要求一次清零全部历史违规。
```

- [ ] **步骤 4：修订 AI Conventions**

明确：

```markdown
- 根 `AGENTS.md` 只保存 durable repo instructions、必读入口、禁止事项和验证命令；
- 大型模块按需生成 nested `AGENTS.md`；
- Trae project rule 是薄适配器，只引用 AGENTS.md、Roadmap、当前 Phase 和 Standards；
- 不写死 `.trae/rules/*.md`，实际路径由当前 Trae 环境确定；
- 不复制 Coding Standards、Architecture 或 docs governance 正文；
- Context strategy 分成 Always read / Read when relevant / Do not preload。
```

当 `host=trae` 时必须直接纳入：

```markdown
## 会话结束

禁止直接结束会话。任务最终完成后必须使用结构化 ASK 询问：

1. 结束本次任务
2. 还有其他任务

选择“还有其他任务”时继续；只有用户选择“结束本次任务”后才允许结束。
```

该已决策事实来自 Bootstrap，禁止子 skill 再问一次。

- [ ] **步骤 5：验证并提交**

运行：

```bash
for d in dd-write-architecture-contract dd-write-coding-standards dd-write-ai-conventions; do
  python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$d"
done
rg -n "approved-baseline|Legacy Compatibility Surface|Target Public Surface" dd-write-architecture-contract/SKILL.md
rg -n "ratchet|changed code|new code" dd-write-coding-standards/SKILL.md
rg -n "Always read|Do not preload|结束本次任务|还有其他任务|nested" dd-write-ai-conventions/SKILL.md
git diff --check
git add \
  dd-write-architecture-contract/SKILL.md \
  dd-write-coding-standards/SKILL.md \
  dd-write-ai-conventions/SKILL.md
git commit -m "refactor(skills): align architecture quality and host rules"
```

预期：三个 validator 通过；状态、ratchet、上下文与 Trae ASK 均可定位；提交成功。

---

### 任务 6：统一 Bootstrap → Feature Handoff

**文件：**

- 修改：`dd-feature-development-workflow/SKILL.md`
- 修改：`dd-project-bootstrap-workflow/SKILL.md`
- 修改：`dd-project-bootstrap-workflow/references/execution-contract.md`

- [ ] **步骤 1：在 Feature workflow 增加 Bootstrap Handoff 入口**

在流程前增加：

```markdown
## Bootstrap Handoff 入口

如果存在 active 或 handoff-ready 的 `project-bootstrap-state.json`：

1. 验证 Handoff 中的路径与产物；
2. 读取 Goal、Scope、Mode、Selected Feature/Phase、Required Reading、Constraints、AC/Requirements Seed、Verification、Out of Scope 和 Resolved Decisions；
3. 复用已确认工作环境，不重复 worktree 询问；
4. Greenfield 使用 Requirements Seed 进入规格套件；
5. Brownfield 复用已批准 Phase Contract，不重新 grill 已确认内容；
6. 只有缺失的 Feature 特有 blocker 才询问用户；
7. 接收成功后把 Bootstrap state 标记为 `completed`，并在 Feature state 记录 `bootstrap_handoff_consumed=true`。
```

- [ ] **步骤 2：补充 Feature 状态字段**

在 `feature-development-state.json` 特有字段中加入：

```json
{
  "bootstrap_handoff_consumed": true,
  "bootstrap_state_path": "/absolute/git-dir/project-bootstrap-state.json",
  "requirements_seed_source": "bootstrap-handoff",
  "phase_contract_path": "docs/phases/P-1_迁移/P-1_01_阶段需求与验收.md"
}
```

- [ ] **步骤 3：移除 Bootstrap 双出口**

Bootstrap 核心和 execution reference 只保留：

```markdown
Handoff target: `dd-feature-development-workflow`
```

Greenfield/Brownfield 差异全部进入 payload，不再由 Bootstrap 直接调用 `dd-writing-specs`。

- [ ] **步骤 4：验证 Handoff**

运行：

```bash
python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py dd-feature-development-workflow
python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py dd-project-bootstrap-workflow
rg -n "bootstrap_handoff_consumed|Requirements Seed|Phase Contract|不重复 worktree" dd-feature-development-workflow/SKILL.md
rg -n "dd-writing-specs.*greenfield|greenfield.*dd-writing-specs" dd-project-bootstrap-workflow
git diff --check
```

预期：validator 通过；Feature Handoff 字段可定位；Bootstrap 双出口扫描返回 1。

- [ ] **步骤 5：Commit**

```bash
git add \
  dd-feature-development-workflow/SKILL.md \
  dd-project-bootstrap-workflow/SKILL.md \
  dd-project-bootstrap-workflow/references/execution-contract.md
git commit -m "refactor(workflows): unify bootstrap feature handoff"
```

---

### 任务 7：更新 Bootstrap 行为场景

**文件：**

- 修改：`dd-project-bootstrap-workflow/tests/baseline-1-greenfield-skip-phase-contract.md`
- 修改：`dd-project-bootstrap-workflow/tests/baseline-2-brownfield-baseline-first.md`
- 创建：`dd-project-bootstrap-workflow/tests/baseline-3-resume-without-reasking.md`
- 创建：`dd-project-bootstrap-workflow/tests/baseline-4-trae-final-ask.md`

- [ ] **步骤 1：更新 Greenfield 场景**

场景必须明确：

```markdown
空 Xcode/Swift Package 骨架含源文件，但无发布、用户、Public API、数据或兼容义务。

预期：
- project_mode=greenfield；
- 不执行 Brownfield Baseline；
- 默认不写 Phase Contract；
- Handoff 到 dd-feature-development-workflow，由其进入 Feature Specs。
```

- [ ] **步骤 2：更新 Brownfield requested-entry 场景**

场景必须明确：

```markdown
用户 requested_entry=roadmap，但项目存在发布版本、外部调用方和兼容性测试。

预期：
- Preflight 识别 brownfield；
- blocking_gaps 包含 brownfield-baseline；
- 先补 Baseline，再进入 Roadmap；
- 不因用户请求入口而跳过阻塞依赖。
```

- [ ] **步骤 3：新增恢复场景**

写入：

```markdown
状态已经记录 platform=macOS、minimum_version=13、language=Swift、current_node=architecture-contract，Roadmap 文件有效。

预期：
- 验证状态和 Roadmap；
- 从 architecture-contract 继续；
- 不重新询问平台、最低版本、语言、模式和工作环境；
- 只询问新的架构 blocker。
```

- [ ] **步骤 4：新增 Trae 最终 ASK 场景**

写入：

```markdown
host=trae，所有 Exit Gate 已通过，Handoff 已准备。

预期：
- 禁止直接输出“工作流结束”并终止；
- ASK 两个选项：结束本次任务 / 还有其他任务；
- “还有其他任务”继续接收任务；
- “结束本次任务”先写 status=completed，再最终交付。
```

- [ ] **步骤 5：验证并提交**

运行：

```bash
test "$(find dd-project-bootstrap-workflow/tests -maxdepth 1 -name 'baseline-*.md' | wc -l | tr -d ' ')" = "4"
rg -n "兼容义务|requested_entry|不得重复询问|结束本次任务|还有其他任务" dd-project-bootstrap-workflow/tests
git diff --check
git add dd-project-bootstrap-workflow/tests
git commit -m "test(bootstrap): cover entry resume and Trae completion"
```

预期：baseline 数量为 4；关键场景全部可定位；提交成功。

---

### 任务 8：全生态一致性验证与收尾

**文件：**

- 验证：本计划涉及的所有 skill 和测试文件
- 修改：仅限验证发现的本计划范围内问题

- [ ] **步骤 1：运行所有 skill validator**

```bash
for d in \
  dd-project-bootstrap-workflow \
  dd-write-phase-contract \
  dd-shared-ask \
  dd-shared-state \
  dd-shared-subagent \
  dd-brownfield-baseline \
  dd-project-research \
  dd-write-roadmap \
  dd-write-architecture-contract \
  dd-write-coding-standards \
  dd-write-ai-conventions \
  dd-feature-development-workflow; do
  python3 /Users/dengdeng/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$d" || exit 1
done
```

预期：12 个 skill 全部输出 `Skill is valid!`。

- [ ] **步骤 2：运行 Markdown、链接与禁用模式检查**

```bash
python3 - <<'PY'
from pathlib import Path

roots = [
    Path("dd-project-bootstrap-workflow"),
    Path("dd-write-phase-contract"),
    Path("dd-shared-ask"),
    Path("dd-shared-state"),
    Path("dd-shared-subagent"),
    Path("dd-brownfield-baseline"),
    Path("dd-project-research"),
    Path("dd-write-roadmap"),
    Path("dd-write-architecture-contract"),
    Path("dd-write-coding-standards"),
    Path("dd-write-ai-conventions"),
    Path("dd-feature-development-workflow"),
]
for root in roots:
    for path in root.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        fence_lines = sum(1 for line in text.splitlines() if line.startswith("```"))
        if fence_lines % 2:
            raise SystemExit(f"unbalanced fence: {path}")
print("markdown fences: ok")
PY

rg -n ">=1 个源文件.*brownfield|严格按 0→1→2→3→4→5→6→7→8→9|每步产物已 git commit" \
  dd-project-bootstrap-workflow dd-write-phase-contract

git diff --check
```

预期：Fence 检查输出 `markdown fences: ok`；旧矛盾扫描返回 1；`git diff --check` 无输出。

- [ ] **步骤 3：执行规格覆盖自检**

逐项核对书面设计的 11 条成功标准：

```text
1. Bootstrap core short
2. requested entry + Gap Scan
3. history-based mode
4. state resume
5. no re-ask
6. workflow/delivery split
7. risk-based review
8. characterization disposition
9. dual public surfaces
10. unified Feature handoff
11. Trae final ASK
```

预期：每项都能指出具体 skill 文件和 baseline 场景；无遗漏。

- [ ] **步骤 4：检查提交和工作区**

运行：

```bash
git status --short
git log --oneline -8
git diff origin/develop...HEAD --stat
```

预期：没有未提交的本计划文件；最近提交与任务 1–7 对应；差异只包含设计、计划和 Skill 生态重构文件。

- [ ] **步骤 5：提交验证修正（仅有修正时）**

```bash
git add \
  dd-project-bootstrap-workflow \
  dd-write-phase-contract \
  dd-shared-ask/SKILL.md \
  dd-shared-state/SKILL.md \
  dd-shared-subagent/SKILL.md \
  dd-brownfield-baseline/SKILL.md \
  dd-project-research/SKILL.md \
  dd-write-roadmap/SKILL.md \
  dd-write-architecture-contract/SKILL.md \
  dd-write-coding-standards/SKILL.md \
  dd-write-ai-conventions/SKILL.md \
  dd-feature-development-workflow/SKILL.md
git commit -m "fix(skills): close bootstrap ecosystem validation gaps"
```

预期：只有步骤 1–3 发现并修复问题时创建该提交；没有修正时不创建空提交。
