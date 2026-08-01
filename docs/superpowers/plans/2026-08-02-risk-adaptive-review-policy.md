# 风险自适应审查策略实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 `executing-plans` 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 让 GPT-5.6 默认以主 Agent 三视角自检完成审查，并只在显式高风险或上一层发现争议时升级为独立或三代理审查。

**架构：** `dd-shared-subagent` 是等级与升级条件的唯一权威；运行时保留“固定语义、风险决定成本”的全局约束。Brownfield 和重构工作流不再把任务类别或每次提交直接映射为三个 reviewer，而是消费当前 `review_level`。

**技术栈：** Markdown Skill 契约、`rg` 文本断言、Git。

---

## 文件结构

- 修改：`dd-shared-subagent/SKILL.md` — 定义三档执行方式、默认等级、显式升级触发器及复验规则。
- 修改：`dd-shared-workflow-runtime/SKILL.md` — 说明风险仅调整执行成本，确定性验证与验收条件不变。
- 修改：`dd-brownfield-baseline/SKILL.md` — 移除基线盘点的类别型 `high` 默认值，改为共享规则的初始等级和升级路径。
- 修改：`dd-ai-refactor-workflow/SKILL.md` — 移除每次提交后三代理并行的硬编码，改为当前等级的三视角审查。

### 任务 1：将共享审查等级改为风险触发升级

**文件：**
- 修改：`dd-shared-subagent/SKILL.md:30-62`
- 测试：`dd-shared-subagent/SKILL.md`

- [ ] **步骤 1：运行会失败的策略断言**

```bash
ruby -e 'text = File.read("dd-shared-subagent/SKILL.md"); abort "default low missing" unless text.include?("默认等级：`low`"); abort "standard trigger missing" unless text.include?("跨模块改动、测试或证据薄弱"); abort "high trigger missing" unless text.include?("安全或权限、不可逆数据迁移"); abort "legacy category default remains" if text.include?("Brownfield 基线、架构/兼容决策、用户可见高风险行为：`high`")'
```

预期：失败；当前文档没有新的默认值和风险触发器。

- [ ] **步骤 2：更新等级、默认与升级规则**

将等级表更新为：

```markdown
| `low` | 主 Agent 一次完成三视角自检 | 默认；机械、局部和常规实现/文档变更 |
| `standard` | 一个独立 reviewer 完成三视角 | 跨模块改动、测试或证据薄弱、主 Agent 结论不确定，或项目/用户明确要求 |
| `high` | 三个方向 reviewer 并行，主 Agent 汇总 | 安全或权限、不可逆数据迁移、兼容性或架构争议、关键用户路径缺乏真实 UI 证据，或 `standard` 发现 blocker/冲突 |
```

将默认规则改为“默认等级：`low`”。将升级规则明确为：`low` 发现跨模块、证据薄弱或结论不确定时升至 `standard`；`standard` 发现 blocker、结论冲突或 `high` 触发器时升至 `high`。

- [ ] **步骤 3：重复步骤 1 的断言**

预期：退出码 0。

- [ ] **步骤 4：提交共享策略**

```bash
git add dd-shared-subagent/SKILL.md
git commit -m "refactor(skills): make shared review risk-adaptive"
```

预期：创建只包含共享审查等级规则的提交。

### 任务 2：同步运行时与 Brownfield 入口

**文件：**
- 修改：`dd-shared-workflow-runtime/SKILL.md:105-113`
- 修改：`dd-brownfield-baseline/SKILL.md:200-223`
- 测试：上述两个文件

- [ ] **步骤 1：运行会失败的入口断言**

```bash
ruby -e 'runtime = File.read("dd-shared-workflow-runtime/SKILL.md"); baseline = File.read("dd-brownfield-baseline/SKILL.md"); abort "runtime invariant missing" unless runtime.include?("不删除验收条件"); abort "baseline default remains high" if baseline.include?("基线盘点默认 `review_level=high`"); abort "baseline low default missing" unless baseline.include?("默认 `review_level=low`")'
```

预期：失败；Brownfield 当前默认 `high`。

- [ ] **步骤 2：写入入口契约**

在运行时说明风险由共享 Skill 的触发器逐级升级，且不得删除验收条件或确定性验证。将 Brownfield 默认等级替换为 `low`；保留上游更高等级、发现的高风险触发器或明确项目规则的升级能力。

- [ ] **步骤 3：重复步骤 1 的断言**

预期：退出码 0。

- [ ] **步骤 4：提交运行时与 Brownfield 入口**

```bash
git add dd-shared-workflow-runtime/SKILL.md dd-brownfield-baseline/SKILL.md
git commit -m "refactor(skills): apply risk-adaptive review defaults"
```

预期：创建只包含运行时与 Brownfield 入口契约的提交。

### 任务 3：移除重构工作流的每提交并行硬编码并做一致性检查

**文件：**
- 修改：`dd-ai-refactor-workflow/SKILL.md:119`
- 测试：四份修改后的 Skill

- [ ] **步骤 1：运行会失败的重构入口断言**

```bash
ruby -e 'text = File.read("dd-ai-refactor-workflow/SKILL.md"); abort "legacy parallel rule remains" if text.include?("每个 Commit 后执行 [dd-shared-subagent]"); abort "current-level rule missing" unless text.include?("当前 `review_level` 要求的三视角审查")'
```

预期：失败；当前文件强制每个 Commit 后执行三视角并行检查。

- [ ] **步骤 2：替换提交后审查句**

```markdown
每个 Commit 后按当前 `review_level` 执行 [dd-shared-subagent](../dd-shared-subagent/SKILL.md) 的三视角审查；无子 Agent 时主线程完成同义复核，不降低语义。随后按 [dd-shared-ci](../dd-shared-ci/SKILL.md) push 并等待 CI。
```

- [ ] **步骤 3：运行全量策略检查**

```bash
ruby -e 'shared = File.read("dd-shared-subagent/SKILL.md"); runtime = File.read("dd-shared-workflow-runtime/SKILL.md"); baseline = File.read("dd-brownfield-baseline/SKILL.md"); refactor = File.read("dd-ai-refactor-workflow/SKILL.md"); abort "shared default missing" unless shared.include?("默认等级：`low`"); abort "runtime invariant missing" unless runtime.include?("不删除验收条件"); abort "baseline default missing" unless baseline.include?("默认 `review_level=low`"); abort "refactor level rule missing" unless refactor.include?("当前 `review_level` 要求的三视角审查")'
git diff --check
```

预期：所有命令退出码 0；无空白错误。

- [ ] **步骤 4：提交实现**

```bash
git add dd-ai-refactor-workflow/SKILL.md
git commit -m "refactor(skills): make refactor review level-aware"
```

预期：创建只包含重构工作流审查契约的提交。
