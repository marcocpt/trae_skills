> 路由文件：按需分发到三个内聚合同；每个语义只在一处定义，禁止重复。

# Artifact Contract — Router

仅作路由与全局不变量，不重复分文件正文。按 Stage 按需读取对应分文件，避免每次加载 10KB。

| 语义 | 唯一属主文件 | 典型消费者 |
|---|---|---|
| 事实/视图、source_manifest、执行包、最小化 (§1/§2/§5) | [artifact-source-and-packet.md](artifact-source-and-packet.md) | Planning、Implementation 组包 |
| 验证证据 compact plan+result、coverage/runs/bindings/validity (§4) | [artifact-verification.md](artifact-verification.md) | Implementation Local Gate、Final Candidate |
| 生命周期、同步影响、ledger、retention (§3) | [artifact-lifecycle.md](artifact-lifecycle.md) | Documentation、项目级文档同步 |

**全局不变量：** 规范事实用稳定 ID + 版本 + 内容指纹 + `approval` 四元绑定；派生视图不得独立维护；`derived` 失效即 `stale` 须重派生；`closed-change` 保持冻结。调用方只补领域检查，不复制通用字段。详见各分文件唯一定义，禁止在多文件重复同一规则。
