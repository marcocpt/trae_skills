# TODO/LATER 记录、类别小结与最终输出

## TODO 与 LATER 记录要求

加入 TODO 时，至少记录：

- 唯一编号
- 测试类别
- 测试函数或文件位置
- 风险说明
- 规则依据
- 建议修复
- 优先级
- 验证方式
- 来源为本次 grilling 审核

加入 LATER 时，除上述内容外，还要写入（对应条目 frontmatter 与正文字段）：

- 为什么不在当前阶段处理（`延后理由` 分节）
- 什么条件下应重新启用（frontmatter `trigger`，必填）
- 建议在哪个阶段处理（frontmatter `target_phase`，必填）
- 长期搁置可能造成的影响（正文分条说明）

不得只写一句模糊的“后续优化”。

LATER 的文件位置、条目格式与去重遵循 [dd-later-tracking](../../dd-later-tracking/SKILL.md)（项目根 `docs/AI/later/` 一项一文件，frontmatter + 分节正文，先查后写；项目有 INDEX 生成脚本时，改动条目的同一 commit 必须刷新 INDEX）。TODO 文件位置参照 [dd-docreview-grilling](../../dd-docreview-grilling/SKILL.md) 约定，默认 `docs/AI/doc-review-todo/` 下按测试文件名命名；如项目已有 TODO 文件则追加。

## 每类测试结束时的小结

当前类别所有风险点完成裁决后，输出：

- 这类测试主要验证什么
- 已确认覆盖
- 尚未覆盖
- 已加入 TODO 的项目
- 已加入 LATER 的项目
- 已立即修复的项目
- 未采纳项目
- 当前类别结论：PASS / PASS_WITH_TODO / PASS_WITH_LATER / NEEDS_FIX / BLOCKED

结论判定：

- BLOCKED：缺少关键文件、工具或证据，无法完成有效审核。
- NEEDS_FIX：存在尚未处置的阻塞性风险，或立即修复后验证失败。
- PASS_WITH_TODO：不存在未处置阻塞项，但至少有一个 TODO。
- PASS_WITH_LATER：没有 TODO，仅存在已接受的非阻塞 LATER。
- PASS：没有 TODO、LATER 或未解决风险。

优先级：BLOCKED > NEEDS_FIX > PASS_WITH_TODO > PASS_WITH_LATER > PASS。TODO 与 LATER 同时存在时取更高优先级（PASS_WITH_TODO）。

然后自动进入下一类测试，不需要再次询问是否继续。

## 最终输出

所有测试类别审核结束后，给出：

1. 测试类别总览。
2. 面向新手的整体解释。
3. 已确认的有效覆盖。
4. 主要覆盖缺口。
5. TODO 清单。
6. LATER 清单。
7. 已更新的 `xctest-rules.md` 规则。
8. 未采纳项及理由。
9. 每类测试的结论。
10. 整体结论。
11. 建议的下一步执行顺序。

最终结论不得只写“总体不错”或“建议加强测试”，必须有证据支撑。
