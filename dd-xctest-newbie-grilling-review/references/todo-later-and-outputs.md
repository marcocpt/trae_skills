# TODO/LATER 记录与最终输出

## TODO 与 LATER 记录要求

加入 TODO 时，至少记录：

- 唯一编号
- 测试类别
- 测试函数或文件位置
- 风险说明（写证据：行号、输入、断言，不写感受）
- 规则依据
- 建议修复（用户已选定的单一方案，达到可执行粒度）
- 优先级
- 验证方式（可判定的完成标准）
- 来源为本次 grilling 审核

排版遵循 [dd-docreview-grilling](../../dd-docreview-grilling/references/todo-later-and-batch-repair.md) TODO Schema 的可读性硬规则：多事实字段分条硬换行（一条事实一行）、条目间留空行、代码标识符与行号用反引号、禁止数百字不换行长段。

**强制规则：** 凡审核中发现、但当前阶段不立即实现的事项（后续实现/延后/暂缓），一律必须记入 LATER 持久化，避免遗忘。不得只在会话里口头延后或停留在记忆里；不得因为"不主动建文档"而跳过写入。

加入 LATER 时，除上述内容外，还要写入（对应条目 frontmatter 与正文字段）：

- 为什么不在当前阶段处理（`延后理由` 分节）
- 什么条件下应重新启用（frontmatter `trigger`，必填）
- 建议在哪个阶段处理（frontmatter `target_phase`，必填）
- 长期搁置可能造成的影响（正文分条说明）

不得只写一句模糊的“后续优化”。

LATER 的文件位置、条目格式与去重遵循 [dd-later-tracking](../../dd-later-tracking/SKILL.md)（项目根 `docs/AI/later/` 一项一文件，frontmatter + 分节正文，先查后写；项目有 INDEX 生成脚本时，改动条目的同一 commit 必须刷新 INDEX）。TODO 文件位置参照 [dd-docreview-grilling](../../dd-docreview-grilling/SKILL.md) 约定，默认 `docs/AI/doc-review-todo/` 下按测试文件名命名；如项目已有 TODO 文件则追加。

然后停止当前类别，不输出类别小结；询问用户是否进入下一类测试（不得自动进入，需用户明确说才执行）。

## 最终输出

仅当用户明确要求收尾时才输出（不自动输出）。所有测试类别审核结束后，给出：

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
