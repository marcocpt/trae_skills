#!/usr/bin/env bash
# 同步 AI-test 工作树到指定分支
# 用法：bash scripts/sync-ai-test-worktree.sh <目标分支> <worktree_dir>
# 返回码：
#   0 = 同步成功
#   1 = 参数错误
#   2 = AI-test 工作树存在未提交变更（需用户处理）
#   3 = git 命令执行失败

set -euo pipefail

TARGET_BRANCH="${1:?用法: sync-ai-test-worktree.sh <目标分支> <worktree_dir>}"
WORKTREE_DIR="${2:?缺少 worktree_dir 参数}"

AI_TEST_PATH="$WORKTREE_DIR/AI-test"

if [ ! -d "$AI_TEST_PATH" ]; then
    # 不存在则创建
    git worktree add "$AI_TEST_PATH" -b AI/test "$TARGET_BRANCH"
else
    # 已存在：检查是否有未提交变更
    if [ -n "$(git -C "$AI_TEST_PATH" status --porcelain)" ]; then
        echo "错误：AI-test 工作树存在未提交变更，需用户处理（保留并跳过 / 用户自行处理后重试 / 明确丢弃后同步）" >&2
        exit 2
    fi
    # 干净则 reset --hard 复位
    git -C "$AI_TEST_PATH" reset --hard "$TARGET_BRANCH"
fi

echo "AI-test 工作树已同步到 $TARGET_BRANCH"
