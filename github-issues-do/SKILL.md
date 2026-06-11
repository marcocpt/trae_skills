---
name: github-issues-do
description: 执行 github 上指定的 issues
---

用 github CLI 读取指定的 issues
- 如果是bug
  - 使用 using-git-worktrees 创建 worktree
  - 使用 systematic-debugging 定位问题。
  - 然后使用 test-derivn-develop，执行