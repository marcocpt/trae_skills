#!/usr/bin/env bash
set -euo pipefail

# 全局技能 dd-ai-git-workflow 配套脚本
# 用法: ./daily-sync.sh
# 拉取 develop 最新改动并合并到当前 feature 分支
# 冲突时输出冲突文件清单并以退出码 2 退出

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [ "$CURRENT_BRANCH" = "develop" ] || [ "$CURRENT_BRANCH" = "main" ]; then
  echo "ERROR: do not run daily-sync on $CURRENT_BRANCH" >&2
  exit 1
fi

echo "→ fetching origin/develop"
git fetch origin develop

echo "→ merging origin/develop into $CURRENT_BRANCH"
if ! git merge --no-ff origin/develop -m "chore: sync develop into $CURRENT_BRANCH"; then
  echo "✗ conflict detected, listing conflicted files:" >&2
  git diff --name-only --diff-filter=U | while IFS= read -r f; do
    echo "  - $f"
  done
  exit 2
fi

echo "✓ sync complete"
git log --oneline -3
