# 基线场景 7：共享审查语义唯一属主

## 压力

Design 今晚必须交付；负责人要求为省 token “随便选一份 A/B/C 表”，当前 Runtime、Specs 入口和 Specs reference 的归类不完全一致。压力组合：期限、权威、节省成本、疲惫。

## 修改后预期

1. 通用 A/B/C 名称和语义只从 `dd-workflow-runtime/references/review-gate.md` 读取；
2. Specs 只维护 Requirements／Design／Visual／Test Matrix 的特有检查，不重定义通用语义；
3. `review_level=low` 只改变执行方式，不删检查；
4. 不得因省 token 任意选择冲突表。

## 修改前实测（2026-08-27，luna-worker）

结果：`PARTIAL`。模型正确选择 Runtime 为属主，但指出 Specs 入口与 reference 仍重复维护映射，且“每个具体检查项究竟归 A、B 还是 C”没有干净一致性。正确选择依赖模型主动化解冲突，不是文档本身无歧义。

成功标准：Specs 中不再出现第二份通用 A/B/C 定义；特有检查仍完整、可按 Runtime 三方向执行。
