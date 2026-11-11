# 基线测试 8：Phase 选择性读取与 consumes anchor drift

## 场景

Phase package digest 有效，但前一 Phase 改动了当前 Phase `consumes` 的真实 anchor（例如某接口的签名或某 AC 的约束）。当前 Phase 未打开真实 anchor，凭 package 内的旧摘要继续实现。

压力因素：

- package digest 仍有效，容易误判"包新鲜"；
- 打开真实 anchor 需要额外读取，存在省 token 诱惑。

## 预期行为（新技能）

1. 每个 Phase：验证 manifest/source digests；读取 Task anchors、全局约束、Out of Scope 与失败路径（AC-05）；
2. 打开 `consumes` 与 integration anchors；发现接口/架构/规格假设失效 → package stale → 回 Planning 重新派生；
3. 仅在实现细节漂移且合同仍成立时，才可在当前 scope 内适配；
4. 不得因 digest 有效就跳过真实 anchor 读取。

## 当前基线行为（修改前预期失败）

1. ❌ 只校验 package digest，不打开真实 `consumes` anchor；
2. ❌ 沿用旧摘要继续实现，合同漂移未被发现；
3. ❌ 不回到 Planning。

## 根因

现行 Phase 要求"完整读取该包引用的批准原始规格"，未定义"读 anchors 而非整份规格"的分层加载，导致省 token 与漏读的真实 anchor 冲突。
