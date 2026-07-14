---
name: "dd-ai-refactor-workflow"
description: "在重构遗留/屎山代码、用户提到 AI 重构/refactoring、或工作到达需要人类确认的刹车点时调用。涉及 Characterization Test、解依赖、God Object 拆分、行为漂移检测等场景。"
---

# AI 重构工作流

> 完整方法论见项目内的 `docs/AI/Refactor with AI.md`。本 skill 是该文档的可执行版本，强制执行以下操作规则。

## 概述

核心原则：**先理解，再锁定行为，最后小步重构。** AI 最大的风险是不知道哪些「看起来像 Bug」其实是业务逻辑，因此不允许一次性重写，必须持续、小步、安全地重构。

## 何时使用

- 重构遗留/屎山代码
- 用户提到 AI 重构、refactor、重构流程
- 工作到达需要人类确认的刹车点（Characterization Test 锁定、解依赖合并、Commit Review 等）
- 涉及 God Object 拆分、行为漂移检测、解依赖改造

**不适用：** bug 修复（用 dd-bug-fix-workflow）、新功能开发（用 dd-feature-development-workflow）、纯文档修改

## 全局会话规则（强制）

**通用询问规则**（结构化询问、null 输入重问）遵循 [dd-shared-ask](../dd-shared-ask/SKILL.md)。

1. **默认推荐执行，仅特定场景必须 ASK**——除非遇到下方「硬性刹车点」中列出的场景，否则 AI 按推荐方案自动推进，不问人类。推荐方案基于 skill 规则而非用户倾向——即使用户表达「赶时间」等倾向，推荐项仍应是符合 skill 规则的选项。
2. **必须 ASK 的场景（穷举）**：
   - 重大架构变更（如模块化、状态机引入、架构演进启动）
   - AI 无法判断是 Bug 还是业务逻辑（Feature）
   - 硬性刹车点表中列出的 4 个节点（见下方）
   - 3 子代理重试 3 次仍未通过
   - 事实层结论已出但仍需业务判断（如「即便非 Bug 是否仍需调整」）
3. **无需 ASK、直接执行的场景**：
   - 阶段间自动推进（阶段一完成 → 自动进阶段二，无需确认）
   - 3 子代理均通过 → 记录审核通过，自动进入下一步
   - 「必须修复」类发现 → 自动采纳并修复
   - 「建议修复」/「可选优化」类 → 自动跳过并记录（除非涉及重大架构变化）
   - CI 失败 → 按推荐方案（拉取日志分析+修复）自动执行
   - 每步完成后选择下一步 → 自动进入推荐的下一步
4. **不得终止对话**——完成所有步骤后，必须用 `AskUserQuestion` 给出后续选项（如「查看重构报告 / 继续优化 / 终止本次重构」），禁止直接结束。
5. **给出代码链接位置**——每个问题必须附文件路径 + 行号，让人类能直接跳转查看。**提问前必须先核实代码位置**：用 Glob/Grep 确认文件存在、定位到具体行号，不得在未读文件的情况下凭用户描述附行号。若用户描述的文件名与代码不符（如用户说 `GridOverlayViewController` 但项目里实际是 `OverlayWindowController`），先 Glob/Grep 自查给出候选文件，在选项中让用户确认文件身份后再推进。若自查无任何候选文件，用 `AskUserQuestion` 给出选项：用户提供准确路径 / 先扫描相关模块列出文件清单 / 终止本次重构。用户拒绝确认文件身份时不得推进——必须再次确认，选项包含「提供准确路径让我核实 / 终止本次重构」，不得在未核实文件身份的情况下凭用户描述附行号或推进。
6. **能查官方资料的不问人类**——涉及 API 行为、系统约定、框架规范等可验证的事实，先开子代理查阅官方文档核对，记录结论即可。只有查不到权威依据的业务判断，才问人类。
7. **附查证结论摘要**——若提问前已有子代理查证结论，必须把结论摘要写进 `AskUserQuestion` 的问题上下文，让用户在知情下决策，避免信息不对称。

### 事实查证 vs 业务判断判定流程

遇到「这看起来像 Bug」时，按以下流程判定，不得跳过：

1. **是否属于系统/API 约定？**（如虚拟键码、系统常量、框架规范）→ 是则开子代理查官方资料
2. **查证结果是否定论？**（如官方文档明确 keycode 22 = `kVK_ANSI_6`）→ 定论则 AI 可得出**事实层结论**（「与官方一致，非 Bug」或「与官方不一致，可能是 Bug」），记录结论，不问人类。**查证结果无权威依据或多源冲突时，视为非定论，按业务判断问人类。**
3. **事实层结论是否充分？**（即便确认是 Bug，是否仍需调整属于业务判断）→ 「是否仍需调整」「何时调整」「如何调整」是业务判断，必须问人类

**关键边界**：AI 可基于权威资料得出「事实层结论」（与官方一致即非 Bug），这不违反「AI 不得自行判定 Bug/Feature」红线——该红线禁止的是 AI 在**无权威依据**时自行下结论。只有「即便非 Bug 是否仍需调整」的业务判断才必须问人类。

## Git 工作流合规（强制）

本技能涉及 Git 操作，必须遵循 dd-ai-git-workflow 系列子技能：

| 子技能 | 职责 | 本技能相关 |
|--------|------|-----------|
| [dd-git-workflow](../dd-git-workflow/SKILL.md) | 入口导航、分支模型 | 总览 |
| [dd-git-branch](../dd-git-branch/SKILL.md) | 分支命名、创建 | `refactor/{模块}` 分支命名 |
| [dd-git-merge](../dd-git-merge/SKILL.md) | merge-only、Commit 规范 | merge-only，禁止 rebase |
| [dd-git-conflict](../dd-git-conflict/SKILL.md) | 冲突处理、公共文件锁 | PublicFile tag |
| [dd-git-worktree](../dd-git-worktree/SKILL.md) | worktree 管理 | 隔离环境 |
| [dd-git-health](../dd-git-health/SKILL.md) | 健康度、每日同步 | 24h 合并窗口 |
| [dd-git-cleanup](../dd-git-cleanup/SKILL.md) | 废弃清理 | 合并后清理 |
| [dd-git-ci](../dd-git-ci/SKILL.md) | 合并前检查、CI | 5 步检查脚本 |

**本技能特有约束**：
- 禁止使用 `git rebase`（必须 merge-only）
- 禁止在 refactor 分支夹带公共文件修改
- 禁止跳过合并前检查

## 四阶段流程（线性执行，不得跳序）

### 阶段一：理解与文档化（禁止改代码）

- 产出 `Architecture.md`（目录结构、模块职责、依赖方向）+ `Build.md`（编译、CI 验证方法、度量方法）——测试方法必须以 CI 为准，不得记录「本地 `swift test`/`xcodebuild test`」作为验证手段
- 盘点已有文档，标注时效性（当前 / 历史 / 过期）
- 退出标准：两份文档存在且与代码核对一致、缺口清单已列出

### 阶段二：锁定现有行为（Characterization Test）

- 测试范围 = 本次重构涉及的模块，不给整个项目加测试
- 按可测性分级：高（AI 直接生成）→ 中（注入 Stub）→ 低（先解依赖）→ 极低（跳过记报告）。AI 生成测试后必须 push 走 CI 验证测试**在 CI 环境中**可运行（「可运行」指 CI 中能跑通且断言通过，**不是本地能编译执行**），不得用本地 `swift test`/`xcodebuild test`/`test-macos.sh` 替代——本地环境 ≠ CI 环境，测试是否能在 CI 中跑通是 CI 说了算
- 锁定前人类确认：测试描述的是真实行为还是 AI 误解
- 已有测试不重写，只补缺口。已有测试仍需人类确认「描述的是真实行为」，但确认粒度可粗——可按模块批量确认（如「`OverlayWindowController*Tests.swift` 这批都描述真实行为吗？」），不必逐条确认

### 阶段三：生成重构报告（诊断）

- 扫描维度：重复代码、God Object、Long Method、循环依赖、违反 SOLID 等
- 每个问题一张诊断卡片：模块、症状、分类、严重度、初步方向
- 优先级：A（风险高 + 多模块依赖）→ B（价值高）→ C（难度低 + 独立）
- 只诊断，不展开方案

### 阶段四：制定路线图（编排）

- 产出依赖图 + 批次表
- 编排维度：依赖关系、批次划分、风险控制、难度
- 每个模块补充：重构手法、验收标准、回滚策略、里程碑
- 每次只改一个模块

## 硬性刹车点

到达以下节点必须停下等人类决策，不得自行通过。**未列出的场景均自动执行，不 ASK。**

| 节点 | 人类要回答的问题 | 为什么必须人工 |
|------|----------------|---------------|
| AI 无法判断 Bug vs Feature 时 | 这是 Bug 还是业务逻辑？ | AI 没有业务上下文，自行判定会锁错基线或误删功能 |
| 架构演进启动前 | 真的需要架构升级，还是行为保持型重构就够？ | 架构变更影响全局，一旦启动难以回退 |
| 解依赖改造合并前（且 3 子代理发现行为漂移风险） | 这次解依赖是否改变了可观察行为？ | 解依赖可能隐藏行为变化，3 子代理发现风险时必须人工判定 |
| Characterization Test 锁了疑似 Bug 的行为 | 锁 Bug 还是修正？ | 锁 Bug = 基线包含错误行为，修正 = 基线描述正确行为，影响后续所有重构 |

**不再作为刹车点的场景（改为自动执行）：**
- ~~重构报告确认前~~ → AI 按规则自动排序优先级（A→B→C），无需人类确认
- ~~路线图启动执行前~~ → AI 按依赖关系自动编排，无需人类确认
- ~~每个 Commit 合并前~~ → 3 子代理并行检查 + CI 验证即可，无需逐 Commit 人工确认
- ~~Characterization Test 锁定前（常规行为）~~ → 常规行为 AI 可判定真实性，仅疑似 Bug 时需人工

## 三子代理并行检查规则

三子代理并行检查规则遵循 [dd-shared-subagent](../dd-shared-subagent/SKILL.md)。

## 重构原则

### 一次只解决一种问题

- **第一组（行为保持型）**：Rename、Extract Method、Move Method——CI 测试全绿 + 命名自解释
- **第二组（结构性）**：Extract Class、Extract Protocol、DI——CI 测试全绿 + 单一职责
- **第三组（架构演进，可选）**：模块化、状态机——CI 测试全绿 + 依赖方向单向
- 每组内部一次只做一种，不混

### 行为保持判定标准

「行为是否保持不变」必须同时满足以下三项，三者全过才算行为保持，缺一不可：

1. **CI 中 Characterization Test 全绿**——阶段二锁定的所有测试在 CI 中（非本地）全绿，重构后仍通过。本地 `swift test`/`xcodebuild test`/`test-macos.sh` 通过不算数——CI 是跨环境验证的唯一保障
2. **3 子代理 A 方向（行为保持性）通过**——A 方向未发现行为漂移
3. **CI 通过**——远端 CI 全绿，跨环境验证行为不变

**优先级**：三者结论冲突时以最严格结论优先。3 子代理通过 ≠ 可合并——仍需 CI 通过。CI 失败即视为行为未保持，必须按「CI 失败处理」流程排查。

**「行为肯定没变」不成立的情况**：
- Extract Method 看似纯结构改动，但若被提取方法引用了共享状态、闭包捕获、隐式 self，可能改变执行顺序或可观察行为
- 解依赖改造可能隐藏行为变化，必须走 CI 验证（不得用本地 `swift test`/`test-macos.sh` 替代）
- 任何「改动很小所以行为肯定不变」的判断都是合理化借口，必须以三项标准验证

### 小 Commit

遵循 dd-ai-git-workflow 的 Commit 规范（conventional commits + scope）：

```text
refactor(ocr): extract OCRService from VisionManager
refactor(ui): rename OverlayController to OverlayWindowController
refactor(vision): split VisionManager into pipeline stages
```

不要 `Refactor Whole Project`。

**公共文件修改**：触及公共文件（见 dd-ai-git-workflow 公共文件清单）时，必须开独立分支 `refactor/public-file-{描述}`，commit message 必须包含 `PublicFile: <文件路径>` tag，且分支生命周期 <1 天优先合并：

```text
refactor(core): extract shared OCR protocol

PublicFile: Sources/MacimCore/OCR/OCREngine.swift
```

### Commit 后 Code Review

**必须由 3 个子代理并行检查**（见「三子代理并行检查规则」），不得由单个子代理独断。

必查项（不通过必须 revert）：

| 风险 | 检查手段 |
|------|---------|
| 行为变化 | 在 CI 中跑完整测试 + 对比输出（不得用本地 `swift test`/`test-macos.sh` 替代） |
| 幻觉 API | 编译必须通过 |
| 测试假绿 | 检查是否覆盖边界 |
| 隐私泄漏 | diff 无密钥/用户数据 |

Review 通过后，必须执行 CI 验证（见下方「CI 验证规则」）。

**3 子代理通过 ≠ 可合并**：3 子代理 Review 通过只是必要条件，不是充分条件。CI 是最终保障——3 子代理可能漏掉跨环境差异（签名、SDK、runner），只有 CI 全绿才算真正通过。3 子代理通过但 CI 失败时，以 CI 为准，按「CI 失败处理」流程排查。

### CI 验证规则（每次 Commit 后强制）

每次 Commit 后必须 push 到远端并等待 CI 通过，不得用本地测试替代 CI 验证。重构的核心风险是行为漂移，CI 是跨环境验证的唯一保障。

#### 验证流程

1. **检查分支是否已 push**：
   ```bash
   CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
   git ls-remote --exit-code --heads origin "$CURRENT_BRANCH" >/dev/null 2>&1
   ```
   - 远端无此分支 → `git push -u origin "$CURRENT_BRANCH"`

2. **检查 CI 已有结果**：
   ```bash
   gh run list --workflow macos-ci.yml --branch <当前分支> --limit 1
   ```
   - `conclusion=success` 且 `headSha` == 当前 HEAD → 复用 CI 结果
   - `conclusion=failure` 且 `headSha` == 当前 HEAD → 进入「CI 失败处理」流程，不得复用
   - `conclusion=failure` 但 `headSha` != 当前 HEAD（已有新 Commit）→ 旧 failure 可忽略，触发新 CI
   - `status=in_progress` → 等待 CI 完成，不重复触发

3. **触发 CI**（无可用结果时）：
   ```bash
   gh workflow run macos-ci.yml --ref <当前分支>
   gh run watch <run-id> --exit-status
   ```

#### 红线

- **禁止用 `swift test` 替代 CI**——本项目是 Xcode 工程，`swift test` 只覆盖 SwiftPM 子集。「只覆盖子集」是 swift test 的缺陷说明而非禁用前提；`xcodebuild test` 虽覆盖完整 scheme，仍因「本地环境 ≠ CI 环境」被同条红线禁止（见行为保持判定标准第 1 项及红线列表）
- **禁止跳过 CI 验证**——重构必须验证行为不变，CI 是跨环境验证的唯一保障
- **本地测试仅用于理解 CI 失败原因**——`bash scripts/ci/test-macos.sh` 可本地复现，但修复后必须重新走 CI
- **分支未 push 时必须先 push 再等 CI**——禁止以 push 失败为由落到本地测试

#### CI 失败处理

CI 失败时**自动按推荐方案执行**，无需 ASK：

1. **推荐方案（自动执行）**：拉取 CI 日志分析失败原因（`gh run view <run-id> --log-failed`），修复后重新走 CI
2. 若修复后 CI 仍失败，重复步骤 1（最多 3 次）
3. 3 次修复后 CI 仍失败 → `AskUserQuestion` 升级处理，给出选项：
   - 本地复现排查（`bash scripts/ci/test-macos.sh`，**仅用于复现/理解 CI 报错的具体原因**——修复后再次本地运行即视为「验证修复是否成功」；任何修复都必须重新走 CI 才算验证通过）
   - `git revert` 本次 Commit，回到上一个绿色基线后重新拆分（对应回滚策略一级）
   - 继续重试修复 + CI（再给 3 次机会）
   - 终止本次重构

**跳过 CI 的条件（严格限制）**：仅限 CI 临时故障——如 runner 宕机、GitHub 平台故障。**「CI 尚未触发」「CI 排队中」「CI 尚未完成运行」均不属于 CI 临时故障，不得以此为跳过理由**。判定依据：CI 日志中失败 step 属于 infra/runner 类，如 `runner cancelled`、`GitHub Actions is temporarily unavailable`。测试断言失败、编译错误、**签名/配置/entitlements/构建脚本/Info.plist 等项目内任何文件修改导致的失败**均属代码失败，不允许跳过，会触发红线「跳过 CI 验证直接合并」

### 功能 Commit 与重构 Commit 分开

功能 Commit 只改行为，重构 Commit 只动结构，不混在一个 Commit。

## 回滚策略

| 级别 | 触发 | 操作 |
|------|------|------|
| 一级 | 单 Commit CI 红 | `git revert` |
| 二级 | 跨 Commit 方向错 | 新开修正 Commit，标注修正 #XXX |
| 三级 | 测试基线锁了 Bug | 行为修正 Commit（人类单独 Review） |
| 四级 | 红灯信号持续 | 保留分支写失败回顾，主分支回退 |

## 合理化借口表

| 借口 | 现实 |
|------|------|
| "测试看起来很怪，我改一下" | 怪行为可能是真实业务逻辑。锁了再说，改了就丢了基线。 |
| "这个改动很小，不需要 CI" | 小改动的回归风险不一定小。CI 正是捕获意外回归。 |
| "本地测试通过了，CI 肯定也通过" | 本地环境 ≠ CI 环境。签名、SDK、runner 差异都可能掩盖问题。 |
| "一次性重写更高效" | 上下文不够、风险不可控，永远不要做。 |
| "这是 Bug 不是 Feature，我直接修" | AI 不知道是 Bug 还是 Feature，必须 ASK 人类。 |
| "AI 说已经没问题了" | CI 没全绿就不算没问题——本地跑过不算数。 |
| "解依赖只改了结构，行为肯定不变" | 解依赖可能隐藏行为变化，必须走 CI 验证——本地测试不算数。 |
| "swift test 通过了就行" | `swift test` 只覆盖 SwiftPM 子集，本项目是 Xcode 工程，必须走 CI。 |
| "CI 失败了，我在本地 test-macos.sh 跑过修复后没问题" | 本地复现仅用于理解 CI 报错，**不得在本地验证修复是否成功**。修复必须重新走 CI 才算验证通过——本地跑过 ≠ CI 通过。 |
| "测试只覆盖 happy path 就够了" | 必须覆盖边界、异常、空数据、非法输入。 |
| "审查太慢了，跳过 3 子代理直接合并" | 单代理独断会漏掉幻觉 API 和行为漂移。3 子代理是底线。 |
| "赶时间，跳过测试/CI 直接推进" | 排期紧不代表可以接受行为漂移。重构返工成本远高于测试编写成本，一次行为漂移事故足以抵消所有节省的时间。 |
| "每步都应该问用户确认，更安全" | 过度 ASK 降低效率且用户容易疲劳点击；3 子代理 + CI 已是安全保障，无需额外人工确认 |
| "重构报告优先级应该让用户确认" | AI 按规则自动排序（A→B→C），除非涉及重大架构变更，否则无需人工确认 |
| "每个 Commit 都应该让人审核" | 3 子代理并行检查 + CI 验证已覆盖所有必查项，逐 Commit 人工审核是冗余 |

## 红线 — 停下来重新开始

- 没有锁定行为（Characterization Test）就开始改代码
- 一次性重写整个项目
- 跳过 CI 验证直接合并
- 用 `swift test` 替代完整测试
- 用本地 `xcodebuild test`/`test-macos.sh` 替代 CI 验证（包括「修复后本地跑过就认为可以合并」）
- CI 失败后在本地验证修复是否成功（修复必须重新走 CI 才算验证通过）
- AI 自行判定「这是 Bug 还是 Feature」（必须 ASK 人类）
- 测试只覆盖 happy path 就声称通过
- 解依赖改造不走 CI 验证就合并
- 跳过 3 子代理并行检查直接进入下一步
- 用纯文本提问而非 `AskUserQuestion` 中断会话（仅在刹车点场景 ASK 时适用）
- 所有重构步骤完成后直接结束对话而不给出后续选项

**以上任一情况发生时，停止当前步骤，回到违规步骤重新执行。**

### 用户书面覆盖红线

当用户在 `AskUserQuestion` 中明确选择违反红线的选项（如「坚持跳过测试直接重构」）时，按以下规则处理：

**不可覆盖的红线**（即使用户书面确认也不允许，必须拒绝并停止——「停止」指按红线章节末尾规则：停止当前步骤，回到违规步骤重新执行；用 `AskUserQuestion` 给出「按规则执行 / 终止本次重构」选项）：
- 没有锁定行为就开始改代码
- 跳过 CI 验证直接合并（项目内任何文件——源码、配置、entitlements、Info.plist、构建脚本、签名设置等——修改导致的 CI 失败）
- 用 `swift test` 替代完整测试
- 用本地 `xcodebuild test`/`test-macos.sh` 替代 CI 验证（包括「修复后本地跑过就认为可以合并」）
- CI 失败后在本地验证修复是否成功

**可书面覆盖的红线**（用户明确书面确认 + 记录到 history 后可执行）：
- 跳过 3 子代理并行检查（仅限低风险纯重命名场景）
- 测试只覆盖 happy path（仅限临时验证，后续必须补全）

**覆盖流程**：
1. 用 `AskUserQuestion` 再次确认用户是否理解风险——给出「确认覆盖并记录风险 / 改为按规则执行 / 终止本次重构」三选项
2. 用户确认覆盖后，在重构工作流对应的 `historys/` 目录（路径模式按项目 `.trae/rules/docs.md` 规则确定，如 `docs/planning/.../historys/` 或独立 `docs/AI/historys/`）追加 `YYYY-MM-DD-红线覆盖记录.md`，写明：覆盖的红线、用户确认内容、剩余风险、后续补偿计划
3. 继续执行，但在后续每个 Commit 的 Code Review 中标注「本次重构存在红线覆盖」

## 何时停止

满足以下任一即可停（用 `AskUserQuestion` 给出后续选项）：

- 硬性指标全达成：CI 全绿（包含所有测试在 CI 中通过）、无新增 Warning
- 红灯信号出现：改动超 2 倍、测试被迫弱化、推理链断裂

## 完成后的提问模式

**阶段间自动推进，无需每步 ASK。** 仅在以下两种情况用 `AskUserQuestion`：

1. **碰到硬性刹车点** → 问刹车点对应的问题
2. **所有重构步骤完成** → 给出汇总选项：查看重构报告 / 继续优化 / 终止本次重构

**不再在每步完成后 ASK**。阶段一完成 → 自动进阶段二，阶段二完成 → 自动进阶段三，以此类推。
