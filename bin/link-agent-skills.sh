#!/usr/bin/env bash
#
# link-agent-skills.sh — 把本仓库的 skill 软链安装到本机各 Agent 的用户级 skills 目录
#
# 幂等：可重复执行。只增不删，同名真实目录先备份再替换，非本仓库的自有 skill 一律不动。
#
# 用法：
#   ./bin/link-agent-skills.sh            # 执行同步，输出摘要
#   ./bin/link-agent-skills.sh --quiet    # 仅在发生变更时输出（给 git hook / launchd 用）
#   ./bin/link-agent-skills.sh --check    # 只检查不同步，全部就位返回 0，否则返回 1
#   ./bin/link-agent-skills.sh --dry-run  # 只报告将要做什么
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && /bin/pwd -P)"
SRC="$(cd "$SCRIPT_DIR/.." && /bin/pwd -P)"   # 仓库根；/bin/pwd -P 才会规范化大小写
BACKUP_ROOT="$HOME/.skill-link-backups"

QUIET=0; CHECK=0; DRY=0; NORM=0
for a in "$@"; do
  case "$a" in
    --quiet|-q) QUIET=1 ;;
    --check|-c) CHECK=1; DRY=1 ;;   # --check 必须严格只读
    --dry-run|-n) DRY=1 ;;
    --normalize) NORM=1 ;;          # 把写法/大小写不一致的链接统一成规范路径
    -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "未知参数: $a" >&2; exit 2 ;;
  esac
done

# 判断两个路径是否指向同一个目录（bash 内建 -ef 按 dev+inode 比较，跟随软链；
# 规避大小写/写法差异导致的伪变更，且无子进程开销）
same_dir() {
  [ "$1" -ef "$2" ]
}

# 目标：本机各 Agent app / CLI 的用户级 skills 目录
TARGETS=(
  "$HOME/.workbuddy-ai/skills"       # WorkBuddy AI
  "$HOME/.workbuddy/skills"          # WorkBuddy (legacy)
  "$HOME/.codex/skills"              # Codex CLI
  "$HOME/.config/opencode/skills"    # OpenCode
  "$HOME/.agents/skills"             # 通用 agents 目录
  "$HOME/.claude/skills"             # Claude Code
  "$HOME/.cursor/skills"             # Cursor
  "$HOME/.trae/skills"               # Trae CLI
  "$HOME/.trae-cn/skills"            # Trae CN
  "$HOME/.grok/skills"               # Grok CLI
  "$HOME/.openclaw-autoclaw/skills"  # AutoClaw / OpenClaw
)

# 收集源 skill：含 SKILL.md 的目录（docs/ 之类无 SKILL.md 的自动排除）
SKILLS=()
for d in "$SRC"/*/; do
  [ -f "${d}SKILL.md" ] && SKILLS+=("$(basename "$d")")
done
if [ ${#SKILLS[@]} -eq 0 ]; then
  echo "错误：$SRC 下没有找到任何含 SKILL.md 的 skill" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_ROOT/$STAMP"
BACKED_UP=0
CREATED=0; REPOINTED=0; REPLACED=0; PRUNED=0; ALREADY=0; CHANGED_DIRS=0

log() { [ "$QUIET" -eq 1 ] || echo "$@"; }

for T in "${TARGETS[@]}"; do
  [ "$DRY" -eq 1 ] || mkdir -p "$T" 2>/dev/null
  c_new=0; c_fix=0; c_rep=0; c_prune=0

  for s in "${SKILLS[@]}"; do
    src="$SRC/$s"; dst="$T/$s"
    if [ -L "$dst" ]; then
      cur="$(readlink "$dst")"
      if same_dir "$dst" "$src" && { [ "$NORM" -eq 0 ] || [ "$cur" = "$src" ]; }; then
        ALREADY=$((ALREADY+1)); continue
      fi
      [ "$DRY" -eq 1 ] || ln -sfn "$src" "$dst"
      REPOINTED=$((REPOINTED+1)); c_fix=$((c_fix+1))
      log "  [重指] ${dst/#$HOME/~}  ($cur -> $src)"
    elif [ -e "$dst" ]; then
      if [ "$DRY" -eq 1 ]; then
        log "  [将备份替换] ${dst/#$HOME/~}"
      else
        mkdir -p "$BACKUP/$T"; mv "$dst" "$BACKUP/$T/$s"; ln -sfn "$src" "$dst"
        BACKED_UP=1
        log "  [备份替换] ${dst/#$HOME/~} -> ${BACKUP/#$HOME/~}/$T/$s"
      fi
      REPLACED=$((REPLACED+1)); c_rep=$((c_rep+1))
    else
      [ "$DRY" -eq 1 ] || ln -sfn "$src" "$dst"
      CREATED=$((CREATED+1)); c_new=$((c_new+1))
    fi
  done

  # 清理：指向本仓库但目标已不存在的断链（源 skill 被删/改名）
  for e in "$T"/*; do
    [ -L "$e" ] || continue
    [ -e "$e" ] && continue                       # 有效链接，跳过
    tgt="$(readlink "$e")"
    case "$tgt" in "$SRC"/*) ;; *) continue ;; esac
    if [ "$DRY" -eq 1 ]; then
      log "  [将清理断链] ${e/#$HOME/~} -> $tgt"
    else
      mkdir -p "$BACKUP/dangling"; mv "$e" "$BACKUP/dangling/"
      BACKED_UP=1
      log "  [清理断链] ${e/#$HOME/~} (源已删除: $tgt)"
    fi
    PRUNED=$((PRUNED+1)); c_prune=$((c_prune+1))
  done

  if [ $((c_new+c_fix+c_rep+c_prune)) -gt 0 ]; then
    CHANGED_DIRS=$((CHANGED_DIRS+1))
    log "$(printf '%-42s 新增 %2d | 重指 %2d | 替换 %2d | 清理 %2d' "${T/#$HOME/~}" "$c_new" "$c_fix" "$c_rep" "$c_prune")"
  else
    log "$(printf '%-42s 已就位 (%d)' "${T/#$HOME/~}" "${#SKILLS[@]}")"
  fi
done

TOTAL=$((CREATED+REPOINTED+REPLACED+PRUNED))
EXPECT=$(( ${#SKILLS[@]} * ${#TARGETS[@]} ))

if [ "$CHECK" -eq 1 ]; then
  if [ "$TOTAL" -gt 0 ]; then
    echo "不同步：$TOTAL 处需要处理（源 ${#SKILLS[@]} 个 skill × ${#TARGETS[@]} 个目标 = 期望 $EXPECT 条）" >&2
    exit 1
  fi
  echo "已同步：$EXPECT/$EXPECT 条链接全部就位"
  exit 0
fi

if [ "$TOTAL" -gt 0 ]; then
  echo "同步完成：新增 $CREATED | 重指 $REPOINTED | 替换 $REPLACED | 清理 $PRUNED | 涉及 $CHANGED_DIRS 个目录（源 ${#SKILLS[@]} 个 skill）"
  [ "$BACKED_UP" -eq 1 ] && echo "备份：${BACKUP/#$HOME/~}"
else
  [ "$QUIET" -eq 1 ] || echo "无需变更：$EXPECT/$EXPECT 条链接全部就位"
fi
exit 0
