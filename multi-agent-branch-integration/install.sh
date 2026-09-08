#!/usr/bin/env bash
#
# install.sh — 把 multi-agent-branch-integration 安装到目标项目。
#
# 用法：
#     /path/to/multi-agent-branch-integration/install.sh [目标目录]
#
# 行为：
#   - 确认目标是 Git 仓库；
#   - 安装 scripts/branchctl 与 .githooks/pre-push；
#   - 缺失时才创建 .agent/branch-policy.yaml（已有绝不覆盖）；
#   - 以稳定 marker 向 AGENTS.md 追加接入片段（幂等，不碰 marker 外内容）；
#   - 设置 core.hooksPath=.githooks（已有其它值时告警且不覆盖）；
#   - 缺失时才安装 GitHub workflow（已有未知文件绝不覆盖，marker 管理的才更新）；
#   - 记录受管文件指纹到 .agent/.branchctl-managed，供 update.sh 做冲突检测。
#
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MARKER_START="<!-- multi-agent-branch-integration:start -->"
MARKER_END="<!-- multi-agent-branch-integration:end -->"
WORKFLOW_MARKER="managed by multi-agent-branch-integration"
MANIFEST=".agent/.branchctl-managed"

log() { printf 'install: %s\n' "$*"; }
fail() {
  printf 'install: ERROR: %s\n' "$*" >&2
  exit 1
}

sha_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    fail "找不到 sha256sum / shasum，无法记录受管文件指纹。"
  fi
}

policy_integration_branch() {
  # policy_integration_branch <策略文件>：只读顶层 integration_branch 标量。
  local v=""
  v="$(sed -n 's/^integration_branch:[[:space:]]*//p' "$1" 2>/dev/null | head -n 1 || true)"
  v="$(printf '%s' "$v" | tr -d '[:space:]' | tr -d "\"'")"
  case "$v" in
    ''|*[[:space:]]*) printf 'develop' ;;
    *) printf '%s' "$v" ;;
  esac
}

render_workflow() {
  # render_workflow <输出路径> <集成分支>：按项目策略生成 workflow（F-MABI-007）。
  local out="$1" ib="$2" tmp="" ib_esc=""
  tmp="$(mktemp 2>/dev/null || printf '')"
  [ -n "$tmp" ] || fail "无法创建临时文件。"
  ib_esc="$(printf '%s' "$ib" | sed 's/[&|\\]/\\&/g')"
  sed "s|__INTEGRATION_BRANCH__|$ib_esc|g" "$SKILL_DIR/templates/github/branch-policy-check.yml" >"$tmp"
  if grep -q "__INTEGRATION_BRANCH__" "$tmp"; then
    rm -f "$tmp"
    fail "workflow 模板渲染失败：占位符未被替换。"
  fi
  install -m 0644 "$tmp" "$out"
  rm -f "$tmp"
}

TARGET="${1:-.}"
# 归一化目标目录（兼容传入相对路径与空格路径）。
TARGET="$(cd "$TARGET" 2>/dev/null && pwd || fail "目标目录不存在：$1")"

[ -f "$SKILL_DIR/runtime/branchctl" ] || fail "Skill 目录不完整：缺少 runtime/branchctl。"
[ -f "$SKILL_DIR/runtime/pre-push" ] || fail "Skill 目录不完整：缺少 runtime/pre-push。"
[ -f "$SKILL_DIR/templates/branch-policy.yaml" ] || fail "Skill 目录不完整：缺少 templates/branch-policy.yaml."
[ -f "$SKILL_DIR/templates/AGENTS.fragment.md" ] || fail "Skill 目录不完整：缺少 templates/AGENTS.fragment.md。"

git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1 \
  || fail "目标不是 Git 仓库：${TARGET}。"
git -C "$TARGET" rev-parse --is-inside-work-tree >/dev/null 2>&1 \
  || fail "目标不在有效 worktree 内：${TARGET}。"

mkdir -p "$TARGET/scripts" "$TARGET/.githooks" "$TARGET/.agent" "$TARGET/.github/workflows"

recorded_sha() {
  local rel="$1"
  local line=""
  [ -f "$TARGET/$MANIFEST" ] || return 0
  line="$(grep -F "  $rel" "$TARGET/$MANIFEST" | head -n 1 || true)"
  [ -n "$line" ] || return 0
  printf '%s' "${line%% *}"
}

install_managed() {
  # install_managed <来源> <相对路径> <模式>：只在三种安全情形下写入，
  # 否则 fail-closed，绝不覆盖来源未知的项目自有文件（F-MABI-002）。
  local src="$1"
  local rel="$2"
  local mode="$3"
  local dst="$TARGET/$rel"
  local cur fresh want
  if [ ! -e "$dst" ]; then
    install -m "$mode" "$src" "$dst"
    log "已安装 ${rel}。"
    return 0
  fi
  cur="$(sha_file "$dst")"
  fresh="$(sha_file "$src")"
  if [ "$cur" = "$fresh" ]; then
    log "$rel 与 Skill 一致，保持幂等。"
    return 0
  fi
  want="$(recorded_sha "$rel")"
  if [ -n "$want" ] && [ "$cur" = "$want" ]; then
    install -m "$mode" "$src" "$dst"
    log "已更新受管文件 ${rel}。"
    return 0
  fi
  fail "拒绝覆盖 ${rel}：该文件已存在且来源未知（非本 Skill 安装）。请手工确认后移走或合并，再重跑安装器。"
}

# --- 1. runtime（受管文件，可被 update.sh 更新） ---
install_managed "$SKILL_DIR/runtime/branchctl" "scripts/branchctl" "0755"
install_managed "$SKILL_DIR/runtime/pre-push" ".githooks/pre-push" "0755"

# --- 2. 项目策略（仅缺失时创建，已有绝不覆盖） ---
if [ -f "$TARGET/.agent/branch-policy.yaml" ]; then
  log "已存在 .agent/branch-policy.yaml，保持不动。"
else
  install -m 0644 "$SKILL_DIR/templates/branch-policy.yaml" "$TARGET/.agent/branch-policy.yaml"
  log "已创建 .agent/branch-policy.yaml（来自模板）。"
fi

# --- 3. AGENTS.md（只追加 marker 片段，幂等） ---
if [ ! -f "$TARGET/AGENTS.md" ]; then
  {
    printf '# AGENTS.md\n\n'
    printf '%s\n' "$MARKER_START"
    cat "$SKILL_DIR/templates/AGENTS.fragment.md"
    printf '%s\n' "$MARKER_END"
  } >"$TARGET/AGENTS.md"
  log "已创建 AGENTS.md（含接入片段）。"
elif grep -qF "$MARKER_START" "$TARGET/AGENTS.md"; then
  log "AGENTS.md 已包含接入片段，保持幂等，不重复追加。"
else
  {
    # 确保原文件以空行结尾后再追加。
    cat "$TARGET/AGENTS.md"
    printf '\n%s\n' "$MARKER_START"
    cat "$SKILL_DIR/templates/AGENTS.fragment.md"
    printf '%s\n' "$MARKER_END"
  } >"$TARGET/AGENTS.md.tmp"
  mv "$TARGET/AGENTS.md.tmp" "$TARGET/AGENTS.md"
  log "已向 AGENTS.md 追加接入片段（marker 外内容未动）。"
fi

# --- 4. Git hook 路径（worktree 共享同一本地配置，只设一次） ---
existing_hooks="$(git -C "$TARGET" config --get core.hooksPath || true)"
if [ -z "$existing_hooks" ]; then
  git -C "$TARGET" config core.hooksPath .githooks
  log "已设置 core.hooksPath=.githooks。"
elif [ "$existing_hooks" = ".githooks" ]; then
  log "core.hooksPath 已是 .githooks，保持不动。"
else
  printf 'install: WARN: core.hooksPath 已有自定义值（%s），为避免破坏现有 hook 配置，本次不覆盖。\n' "$existing_hooks" >&2
  printf 'install: WARN: 请手工把 .githooks/pre-push 链入现有 hook 流程，或确认后再执行：git config core.hooksPath .githooks\n' >&2
fi

# --- 5. GitHub workflow（已有未知文件绝不覆盖） ---
WORKFLOW="$TARGET/.github/workflows/branch-policy-check.yml"
MANAGED_WORKFLOW="false"
if [ ! -f "$WORKFLOW" ]; then
  render_workflow "$WORKFLOW" "$(policy_integration_branch "$TARGET/.agent/branch-policy.yaml")"
  log "已安装 .github/workflows/branch-policy-check.yml。"
  MANAGED_WORKFLOW="true"
elif grep -qF "$WORKFLOW_MARKER" "$WORKFLOW"; then
  render_workflow "$WORKFLOW" "$(policy_integration_branch "$TARGET/.agent/branch-policy.yaml")"
  log "已更新 marker 管理的 branch-policy-check.yml。"
  MANAGED_WORKFLOW="true"
else
  log "已存在未知来源的 branch-policy-check.yml，跳过（不覆盖）。"
fi

# --- 6. 受管文件指纹（供 update.sh 冲突检测） ---
{
  printf '%s  %s\n' "$(sha_file "$TARGET/scripts/branchctl")" "scripts/branchctl"
  printf '%s  %s\n' "$(sha_file "$TARGET/.githooks/pre-push")" ".githooks/pre-push"
  if [ "$MANAGED_WORKFLOW" = "true" ]; then
    printf '%s  %s\n' "$(sha_file "$WORKFLOW")" ".github/workflows/branch-policy-check.yml"
  fi
} >"$TARGET/$MANIFEST"
log "已记录受管文件指纹（${MANIFEST}）。"

log "安装完成。下一步：在 feature 分支执行 ./scripts/branchctl init --private（或 --shared）。"
