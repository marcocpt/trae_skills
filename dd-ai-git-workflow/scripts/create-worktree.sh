#!/usr/bin/env bash
set -euo pipefail

# 全局技能 dd-ai-git-workflow 配套脚本
# 用法: ./create-worktree.sh <branch-type> <id> <description>
# 示例: ./create-worktree.sh feature F3.1 ocr-acceleration
#       ./create-worktree.sh fix F3.1 hotkey-conflict
#       ./create-worktree.sh docs ai-git-workflow
#       ./create-worktree.sh refactor core-state-machine

BRANCH_TYPE="${1:?missing branch type: feature|fix|docs|refactor}"
ID="${2:-}"
DESCRIPTION="${3:-}"

case "$BRANCH_TYPE" in
  feature|fix)
    [ -z "$ID" ] && { echo "ERROR: feature/fix requires <id> (F编号)" >&2; exit 1; }
    [ -z "$DESCRIPTION" ] && { echo "ERROR: feature/fix requires <description>" >&2; exit 1; }
    BRANCH_NAME="${BRANCH_TYPE}/${ID}-${DESCRIPTION}"
    ;;
  docs|refactor)
    [ -z "$DESCRIPTION" ] && { echo "ERROR: docs/refactor requires <description>" >&2; exit 1; }
    BRANCH_NAME="${BRANCH_TYPE}/${DESCRIPTION}"
    ;;
  *)
    echo "ERROR: invalid branch type '$BRANCH_TYPE'. Use feature|fix|docs|refactor" >&2
    exit 1
    ;;
esac

# worktree 目录名：保留分支名中的斜杠，按分支类型分子目录
# 示例：fix/F3.1-hotkey-conflict → worktrees/fix/F3.1-hotkey-conflict/
# 示例：feature/F3.1-ocr-acceleration → worktrees/feature/F3.1-ocr-acceleration/

# 基于主仓库位置计算（避免在 worktree 内调用时项目名识别错误）
# 使用 git-common-dir 定位主仓库，而非 show-toplevel（后者在 worktree 内返回 worktree 根）
COMMON_DIR="$(git rev-parse --git-common-dir)"
MAIN_ROOT="$(cd "$(dirname "$COMMON_DIR")" && pwd)"
PROJECT="$(basename "$MAIN_ROOT")"
WORKTREE_DIR="$(dirname "$MAIN_ROOT")/${PROJECT}-worktrees"

# 自动创建 worktrees 子目录（不存在时创建，已存在时不报错）
mkdir -p "$WORKTREE_DIR/$BRANCH_TYPE"

WORKTREE_PATH="${WORKTREE_DIR}/${BRANCH_NAME}"

if [ -d "$WORKTREE_PATH" ]; then
  echo "ERROR: worktree path already exists: $WORKTREE_PATH" >&2
  exit 1
fi

# 确认基线最新
git fetch origin develop

# 基于 origin/develop 创建分支并添加 worktree
git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" origin/develop

echo "✓ worktree created"
echo "  path:   $WORKTREE_PATH"
echo "  branch: $BRANCH_NAME"
echo "  base:   origin/develop"
echo ""
echo "worktree list:"
git worktree list
