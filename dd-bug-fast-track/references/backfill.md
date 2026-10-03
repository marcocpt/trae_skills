# Bug 补齐阶段（Backfill / Closure）

补齐顺序、基准与关闭规则见 [fast-track-contract](../../dd-workflow-runtime/references/fast-track-contract.md) §5；本文件只写 Bug 领域补什么、怎么补、什么时候交接。

## 1. 补复现测试与红绿对照（第一步，不可跳过）

1. 写一个能稳定触发原症状的测试；测试位置遵循 [test-location](../../dd-workflow-runtime/references/test-location.md)；
2. **红**：把修复回退（`git stash`、临时 revert 或切到修复前提交）后跑该测试，必须失败，保存失败输出；
3. **绿**：恢复修复后跑同一测试，必须通过；
4. 速通阶段一次改了多处时，还要做单变量对照实验：分别只回退其中一处，确认每一处是否都是必要条件，把结论写入欠账证据；
5. 确定性验证：同一份修复重复执行结论一致，运行记录绑到当前实现指纹。

关闭欠账 `regression` 与 `determinism`，`evidence` 填红绿运行记录与指纹。

**没有红绿对照的复现测试无效**——只在新代码上跑绿的测试无法证明它覆盖了这个 Bug。

## 2. 补根因证据（第二步）

用下列至少一种把"最可能的那一处"变成可追溯结论：

- 日志/崩溃栈/错误码与修复点的对应关系；
- 数据流追踪：从触发点到症状点的实际取值变化；
- 最小实验：改一个变量、观察症状是否随之出现或消失（多变量修改时必做）。

证据要能回答"为什么是这里"和"修复为什么有效"。关闭欠账 `root-cause`。

**证明不了就交接**：补齐阶段仍无法取得根因证据时，不得关闭该欠账，交接 `dd-bug-fix-workflow` 重新诊断，带上已确认症状、当前修复、红绿记录与失败尝试。

## 3. 补回归 CI（第三步）

1. 冻结最终候选 SHA——补齐完成后锁定，后续验证与交付都绑定这一个 SHA；
2. 在该 SHA 上跑完整回归 CI，遵循 [ci](../../dd-workflow-runtime/references/ci.md)；CI 结果与修复 SHA 必须一致；
3. 用户可见 Bug 按 [ui-evidence](../../dd-workflow-runtime/references/ui-evidence.md) 复核真实路径证据的新鲜度。

关闭欠账 `ci` 与 `ui-evidence`，`evidence` 填运行记录与 `head_sha`。

## 4. 补文档（第四步）

按调用关系、数据流、共享模型和用户流程检查需要同步的长期文档，遵循 [artifact-lifecycle](../../dd-workflow-runtime/references/artifact-lifecycle.md) 的生命周期结论；无需更新的要有明确结论，不是"忘了"。关闭欠账 `docs`。

## 5. 逐条关闭与豁免

- 每条欠账关闭时必须写 `evidence`，没有证据的关闭无效；
- 用户要求某条不补时，改为 `waived` 并写 `waive_reason`，**逐条确认**，不接受"都别补了"的一次性豁免；
- `root-cause` 不接受"症状没了所以不用证明"式的豁免；
- 台账全清后，把最终 `debts` 与状态一起持久化。

## 6. Closure 与交接

**直接收尾**：全部欠账 `closed` 或经确认 `waived`、回归 CI 绑定同一 SHA 且通过 → 写 Completion Receipt，按 `dd-workflow-runtime` 的宿主结束合同收尾（Trae 用结构化 ASK，不得直接结束会话）。

**交接正式流程**（命中任一即交接，不在速通内降级）：

- 根因无法证明；
- 修复需要改变既有行为或既有回归预期；
- 触及持久化格式、并发模型、兼容性、安全或权限；
- 出现复述范围外的新症状。

交接内容：已确认症状与期望、最终修复与 SHA、红绿记录、已有根因线索、剩余 `open` 欠账。按 [delivery-and-closure](../dd-bug-fix-workflow/references/delivery-and-closure.md) 的正式规则继续，交接后本 Skill 不再拥有会话。

## 7. 红线

- 只跑绿不跑红就宣称复现测试已补；
- 一次改多处却不做单变量对照；
- 证明不了根因仍关闭 `root-cause` 欠账；
- 为了绿灯修改既有测试预期；
- 一次性豁免全部欠账而非逐条确认；
- 在 fix 分支夹带无关公共文件修改；
- 把补齐完成解释为 push／merge／发布授权。
