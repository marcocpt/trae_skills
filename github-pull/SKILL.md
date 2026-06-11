---
name: github-pull
description: 将本地分支提交并合并到 develop 分支
---

用 github CLI 先抓取本地分支的最新版本，然后提交本地修改的内容,检查 swiftlint 并修复
再在 github 看看有没有已有的 pull request
    没有就创建 New pull request
    有就更新 pull request
合并到 develop分支