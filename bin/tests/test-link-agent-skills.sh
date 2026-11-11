#!/usr/bin/env bash
# 负向测试：同名第三方链接 / 伪 AGENT/skills 目录 / .. 路径越界
# 全部在临时 HOME 中运行，不接触真实用户目录。
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)"
SCRIPT="$ROOT/bin/link-agent-skills.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

pass=0; fail=0
ok()   { pass=$((pass+1)); echo "PASS $*"; }
bad()  { fail=$((fail+1)); echo "FAIL $*"; }

T="$TMP/.claude/skills"
mkdir -p "$T"

# 1) 第三方 git 仓库里的同名 skill
FOREIGN_REPO="$TMP/foreign-repo"
mkdir -p "$FOREIGN_REPO/git"
git -C "$FOREIGN_REPO" init -q
ln -s "$FOREIGN_REPO/git" "$T/git"

# 2) 伪 AGENT/skills 目录（不是同一个 git 仓库）
FAKE="$TMP/AGENT/skills/fake"
mkdir -p "$FAKE"
ln -s "$FAKE" "$T/mcp"

# 3) .. 路径越界
ln -s "$ROOT/../foreign-skill" "$T/bug"

HOME="$TMP" "$SCRIPT" --quiet >/dev/null 2>&1
code=$?
[ "$code" -ne 0 ] && ok "冲突时返回非零（${code}）" || bad "冲突时仍返回 0"

for pair in "git:$FOREIGN_REPO/git" "mcp:$FAKE" "bug:$ROOT/../foreign-skill"; do
  name="${pair%%:*}"; expect="${pair#*:}"
  got="$(readlink "$T/$name")"
  [ "$got" = "$expect" ] && ok "$name 链接未被覆盖" || bad "$name 链接被改为 $got"
done

# 清除冲突后应成功接管
rm -f "$T/git" "$T/mcp" "$T/bug"
HOME="$TMP" "$SCRIPT" --quiet >/dev/null 2>&1
code=$?
[ "$code" -eq 0 ] && ok "无冲突时返回 0" || bad "无冲突时返回 $code"
for n in git mcp bug; do
  [ "$(readlink "$T/$n")" = "$ROOT/$n" ] && ok "$n 已指向本仓库" || bad "$n 未指向本仓库"
done

echo "TOTAL: $pass passed, $fail failed"
[ "$fail" -eq 0 ]
