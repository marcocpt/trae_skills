#!/usr/bin/env python3
"""DD-008 机械校验器：验证 agents/<host>/ 原生绑定文件与 model-bindings.yaml 等价。

canonical 源是 model-bindings.yaml；原生文件是产物。任何漂移以非零退出。
用法：python3 validate-bindings.py（默认校验脚本所在目录）
"""
import re
import sys
import tomllib
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent


def load_bindings(path: Path) -> dict:
    """解析 model-bindings.yaml 的 hosts 段（自用极简解析，不引 PyYAML 依赖）。
    结构约定：顶层段（0 缩进）→ 宿主（2）→ 角色（4）→ 键值（6）。"""
    bindings: dict = {}
    section = host = role = None
    for raw in path.read_text().splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0 and line.endswith(":"):
            section, host, role = line[:-1], None, None
            continue
        if section != "hosts":
            continue
        if indent == 2 and line.endswith(":"):
            host = line[:-1]
            bindings.setdefault(host, {})
            role = None
            continue
        if host and indent == 4 and line.endswith(":"):
            role = line[:-1]
            bindings[host][role] = {}
            continue
        if host and role and ":" in line:
            key, _, val = line.partition(":")
            val = val.split("#", 1)[0].strip()
            if val in ("", "null"):
                continue
            if key == "readonly_tools":
                val = [v.strip() for v in val.strip("[]").split(",") if v.strip()]
            bindings[host][role][key] = val
    return bindings


def check_native(bindings: dict) -> list[str]:
    errors = []
    for host, roles in bindings.items():
        for role, spec in roles.items():
            fpath = AGENTS_DIR / spec["file"]
            if not fpath.exists():
                errors.append(f"{host}/{role}: 缺少产物 {spec['file']}")
                continue
            content = fpath.read_text()
            if fpath.suffix == ".toml":
                data = tomllib.loads(content)
                if data.get("model") != spec["model"]:
                    errors.append(f"{host}/{role}: model 漂移 {data.get('model')!r} != {spec['model']!r}")
                ek = spec.get("effort_key")
                if ek and data.get(ek) != spec["effort"]:
                    errors.append(f"{host}/{role}: {ek} 漂移 {data.get(ek)!r} != {spec['effort']!r}")
                if "sandbox" in spec and data.get("sandbox_mode") != spec["sandbox"]:
                    errors.append(f"{host}/{role}: sandbox_mode 漂移")
                for req in ("name", "description"):
                    if req not in data:
                        errors.append(f"{host}/{role}: 缺必需字段 {req}")
            else:
                fm = content.split("---")[1]
                model_re = re.compile(rf"^model:\s*{re.escape(spec['model'])}\s*(#.*)?$", re.M)
                if not model_re.search(fm):
                    errors.append(f"{host}/{role}: model 漂移，未找到 'model: {spec['model']}'")
                tools = spec.get("readonly_tools")
                if tools:
                    for t in tools:
                        if f"- {t}" not in fm:
                            errors.append(f"{host}/{role}: 只读白名单缺 {t}")
    return errors


def main() -> int:
    bindings = load_bindings(AGENTS_DIR / "model-bindings.yaml")
    if not bindings.get("codex"):
        print("解析失败：未从 model-bindings.yaml 读到任何宿主")
        return 2
    errors = check_native(bindings)
    if errors:
        print("BINDINGS DRIFTED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    n = sum(len(r) for r in bindings.values())
    print(f"bindings OK：{len(bindings)} 宿主 / {n} 角色与 canonical 一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
