#!/usr/bin/env python3
"""Static integrity checks for the distributable Codex port."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import py_compile
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.9/3.10: development check only
    tomllib = None

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "skills" / "insane-research"
MIRROR = ROOT / ".agents" / "skills" / "insane-research"


def tree_hashes(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            result[str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def load_runtime_version() -> str:
    path = CANONICAL / "scripts" / "researchctl.py"
    spec = importlib.util.spec_from_file_location("researchctl_verify", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load researchctl")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return str(module.VERSION)


def main() -> int:
    errors: list[str] = []
    required = [
        ROOT / ".codex-plugin" / "plugin.json",
        CANONICAL / "SKILL.md",
        CANONICAL / "agents" / "openai.yaml",
        CANONICAL / "scripts" / "researchctl.py",
        ROOT / "LICENSE",
        ROOT / "NOTICE",
        ROOT / "README.md",
        ROOT / "README.ko.md",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing: {path.relative_to(ROOT)}")

    try:
        plugin = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        if plugin.get("skills") != "./skills/":
            errors.append("plugin skills path must be ./skills/")
        if plugin.get("version") != load_runtime_version():
            errors.append("plugin version and researchctl VERSION differ")
    except Exception as exc:  # noqa: BLE001 - integrity tool should aggregate
        errors.append(f"plugin/runtime parse failure: {exc}")

    skill_text = (CANONICAL / "SKILL.md").read_text(encoding="utf-8") if (CANONICAL / "SKILL.md").exists() else ""
    frontmatter = re.match(r"^---\n(.*?)\n---\n", skill_text, flags=re.DOTALL)
    if not frontmatter:
        errors.append("SKILL.md YAML frontmatter missing")
    else:
        meta = frontmatter.group(1)
        if not re.search(r"^name:\s*insane-research\s*$", meta, flags=re.MULTILINE):
            errors.append("SKILL.md name must be insane-research")
        if not re.search(r"^description:\s*\S", meta, flags=re.MULTILINE):
            errors.append("SKILL.md description missing")
    for forbidden in ("${CLAUDE_PLUGIN_ROOT}", "AskUserQuestion", "bypassPermissions"):
        if forbidden in skill_text:
            errors.append(f"Claude-specific token remains in canonical SKILL.md: {forbidden}")

    try:
        runtime_path = CANONICAL / "scripts" / "researchctl.py"
        source = runtime_path.read_text(encoding="utf-8")
        py_compile.compile(str(runtime_path), doraise=True)
        ast.parse(source, filename=str(runtime_path), feature_version=(3, 9))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"researchctl Python 3.9 syntax/compile failure: {exc}")

    if tomllib is not None:
        for path in sorted((ROOT / ".codex" / "agents").glob("*.toml")):
            try:
                data = tomllib.loads(path.read_text(encoding="utf-8"))
                for key in ("name", "description", "developer_instructions"):
                    if not data.get(key):
                        errors.append(f"{path.name}: missing {key}")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{path.name}: TOML parse failure: {exc}")

    if not MIRROR.is_dir():
        errors.append("repository-scoped mirror missing; run scripts/sync_skill.py")
    elif tree_hashes(CANONICAL) != tree_hashes(MIRROR):
        errors.append("canonical skill and .agents/skills mirror differ; run scripts/sync_skill.py")

    if errors:
        print("PACKAGE CHECK: FAIL", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print("PACKAGE CHECK: PASS")
    print(f"version: {load_runtime_version()}")
    print(f"skill files: {len(tree_hashes(CANONICAL))}")
    print(f"custom agents: {len(list((ROOT / '.codex' / 'agents').glob('*.toml')))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
