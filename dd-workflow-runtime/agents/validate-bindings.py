#!/usr/bin/env python3
"""DD-008 机械校验器：验证 agents/<host>/ 原生绑定文件与 model-bindings.yaml 等价。

canonical 源是 model-bindings.yaml；原生文件是产物。任何漂移以非零退出。
用法：
  python3 validate-bindings.py
  python3 validate-bindings.py --check-codex-install
"""
import argparse
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
            if val.startswith("["):
                val = [v.strip() for v in val.strip("[]").split(",") if v.strip()]
            bindings[host][role][key] = val
    return bindings


EXPECTED_HOSTS = {"codex", "zcode", "qoder", "opencode", "codebuddy", "trae"}


def check_native(bindings: dict) -> list[str]:
    errors = []
    missing = EXPECTED_HOSTS - set(bindings)
    extra = set(bindings) - EXPECTED_HOSTS
    if missing:
        errors.append(f"canonical 缺少目标宿主: {sorted(missing)}")
    if extra:
        errors.append(f"canonical 出现未知宿主: {sorted(extra)}")
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

                def fm_has(key: str, value: str, what: str) -> None:
                    pat = re.compile(rf"^{re.escape(key)}:\s*{re.escape(value)}\s*(#.*)?$", re.M)
                    if not pat.search(fm):
                        errors.append(f"{host}/{role}: {what} 漂移，未找到 '{key}: {value}'")

                fm_has("model", str(spec["model"]), "model")
                ek = spec.get("effort_key")
                if ek and spec.get("effort"):
                    fm_has(ek, str(spec["effort"]), ek)
                tl = spec.get("thought_level")
                if tl:
                    fm_has("thoughtLevel", str(tl), "thoughtLevel")
                if str(spec.get("permission_default_deny", "")).lower() == "true":
                    if not re.search(r'^\s*"\*":\s*deny\s*$', fm, re.M):
                        errors.append(f'{host}/{role}: 缺默认拒绝 "*" deny')
                allows = spec.get("readonly_allows")
                if allows:
                    for a in allows:
                        if not re.search(rf"^\s*{re.escape(a)}:\s*allow\s*$", fm, re.M):
                            errors.append(f"{host}/{role}: 只读放行缺 '{a}: allow'")
                tools = spec.get("readonly_tools")
                if tools:
                    for t in tools:
                        if f"- {t}" not in fm:
                            errors.append(f"{host}/{role}: 只读白名单缺 {t}")
    return errors


def check_codex_install(bindings: dict, config_path: Path) -> list[str]:
    """验证 Codex 注册直接引用 canonical 普通文件，不经过 symlink。

    Codex 0.149.0 的角色加载器读取 symlink config_file 时返回 ELOOP，外层会将其
    模糊为 "agent type is currently not available"。因此这里不仅验证最终目标存在，
    还明确拒绝 config_file 路径本身是符号链接。
    """
    errors = []
    config_path = config_path.expanduser()
    if not config_path.is_file():
        return [f"Codex 安装配置不存在或不是普通文件: {config_path}"]

    try:
        config = tomllib.loads(config_path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"Codex 安装配置无法解析: {config_path}: {exc}"]

    registered = config.get("agents", {})
    if not isinstance(registered, dict):
        return [f"Codex 安装配置的 [agents] 不是 table: {config_path}"]
    for role, spec in bindings["codex"].items():
        if "file" not in spec:
            continue
        canonical = AGENTS_DIR / spec["file"]
        if not canonical.is_file():
            errors.append(f"codex/{role}: canonical 不存在或不是普通文件: {canonical}")
            continue
        try:
            native = tomllib.loads(canonical.read_text())
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"codex/{role}: canonical 无法解析: {canonical}: {exc}")
            continue
        agent_name = native.get("name")
        if not isinstance(agent_name, str) or not agent_name:
            errors.append(f"codex/{role}: canonical 缺少有效 name: {canonical}")
            continue
        entry = registered.get(agent_name)
        if not isinstance(entry, dict):
            errors.append(f"codex/{role}: config.toml 缺少 [agents.{agent_name}]")
            continue

        raw_config_file = entry.get("config_file")
        if not isinstance(raw_config_file, str) or not raw_config_file:
            errors.append(f"codex/{role}: [agents.{agent_name}] 缺少 config_file")
            continue

        installed = Path(raw_config_file).expanduser()
        if not installed.is_absolute():
            errors.append(f"codex/{role}: config_file 必须是 canonical 绝对路径: {installed}")
            continue
        if installed.is_symlink():
            errors.append(
                f"codex/{role}: config_file 不得指向 symlink（Codex 角色加载会返回 ELOOP）: {installed}"
            )
            continue
        if not installed.is_file():
            errors.append(f"codex/{role}: config_file 不存在或不是普通文件: {installed}")
            continue
        if not installed.samefile(canonical):
            errors.append(
                f"codex/{role}: config_file 未直连 canonical: {installed} != {canonical}"
            )
        duplicate = config_path.parent / "agents" / f"{agent_name}.toml"
        if duplicate.exists() or duplicate.is_symlink():
            errors.append(
                f"codex/{role}: 删除同名自动发现副本，避免 duplicate agent role: {duplicate}"
            )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-codex-install",
        action="store_true",
        help="同时检查 ~/.codex/config.toml 的 agent config_file 安装引用",
    )
    parser.add_argument(
        "--codex-config",
        type=Path,
        default=Path.home() / ".codex" / "config.toml",
        help="Codex config.toml 路径（默认 ~/.codex/config.toml）",
    )
    args = parser.parse_args()

    bindings = load_bindings(AGENTS_DIR / "model-bindings.yaml")
    if not bindings.get("codex"):
        print("解析失败：未从 model-bindings.yaml 读到任何宿主")
        return 2
    errors = check_native(bindings)
    if args.check_codex_install:
        errors.extend(check_codex_install(bindings, args.codex_config))
    if errors:
        print("BINDINGS DRIFTED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    n = sum(len(r) for r in bindings.values())
    print(f"bindings OK：{len(bindings)} 宿主 / {n} 角色与 canonical 一致")
    if args.check_codex_install:
        print(f"Codex install OK：{args.codex_config.expanduser()} 直连 canonical 普通文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
