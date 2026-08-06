#!/usr/bin/env python3
"""Explicit, side-effect-limited installer for the Codex skill and custom agents."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILL_SOURCE = ROOT / "skills" / "insane-research"
AGENT_SOURCE = ROOT / ".codex" / "agents"


def backup_path(path: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    candidate = path.with_name(f"{path.name}.backup-{stamp}")
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}.backup-{stamp}-{counter}")
        counter += 1
    return candidate


def copy_skill(target: Path, force: bool, dry_run: bool) -> list[str]:
    actions: list[str] = []
    if target.exists():
        if not force:
            raise RuntimeError(f"skill target already exists: {target} (use --force to back it up and replace it)")
        backup = backup_path(target)
        actions.append(f"backup {target} -> {backup}")
        if not dry_run:
            target.rename(backup)
    actions.append(f"copy skill {SKILL_SOURCE} -> {target}")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(SKILL_SOURCE, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return actions


def copy_agents(target_dir: Path, force: bool, dry_run: bool) -> list[str]:
    actions: list[str] = []
    target_dir.mkdir(parents=True, exist_ok=True) if not dry_run else None
    conflicts = [target_dir / source.name for source in AGENT_SOURCE.glob("*.toml") if (target_dir / source.name).exists()]
    if conflicts and not force:
        joined = ", ".join(str(path) for path in conflicts)
        raise RuntimeError(f"custom agent target exists: {joined} (use --force to back up and replace)")
    for source in sorted(AGENT_SOURCE.glob("*.toml")):
        target = target_dir / source.name
        if target.exists():
            backup = backup_path(target)
            actions.append(f"backup {target} -> {backup}")
            if not dry_run:
                target.rename(backup)
        actions.append(f"copy agent {source.name} -> {target}")
        if not dry_run:
            shutil.copy2(source, target)
    return actions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Install insane-research for Codex")
    parser.add_argument("--scope", choices=("user", "project"), default="user")
    parser.add_argument("--project-root", default=".", help="Used when --scope project")
    parser.add_argument("--skill-only", action="store_true", help="Do not install custom subagent TOML files")
    parser.add_argument("--force", action="store_true", help="Back up and replace existing files")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not SKILL_SOURCE.is_dir():
        print(f"source skill missing: {SKILL_SOURCE}", file=sys.stderr)
        return 2
    if args.scope == "user":
        home = Path.home()
        skill_target = home / ".agents" / "skills" / "insane-research"
        agent_target = home / ".codex" / "agents"
    else:
        project = Path(args.project_root).expanduser().resolve()
        skill_target = project / ".agents" / "skills" / "insane-research"
        agent_target = project / ".codex" / "agents"
    try:
        # Preflight every target before making any change, so a later custom-agent
        # conflict cannot leave a partially installed package.
        if skill_target.exists() and not args.force:
            raise RuntimeError(
                f"skill target already exists: {skill_target} "
                "(use --force to back it up and replace it)"
            )
        if not args.skill_only and not args.force:
            conflicts = [
                agent_target / source.name
                for source in AGENT_SOURCE.glob("*.toml")
                if (agent_target / source.name).exists()
            ]
            if conflicts:
                joined = ", ".join(str(conflict) for conflict in conflicts)
                raise RuntimeError(
                    f"custom agent target exists: {joined} "
                    "(use --force to back up and replace)"
                )
        actions = copy_skill(skill_target, force=args.force, dry_run=args.dry_run)
        if not args.skill_only:
            actions.extend(copy_agents(agent_target, force=args.force, dry_run=args.dry_run))
    except (OSError, RuntimeError) as exc:
        print(f"install failed: {exc}", file=sys.stderr)
        return 2
    for action in actions:
        print(action)
    print("dry run complete" if args.dry_run else "installation complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
