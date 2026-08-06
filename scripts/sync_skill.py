#!/usr/bin/env python3
"""Mirror the canonical plugin skill into the repository-scoped Codex path."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "skills" / "insane-research"
TARGET = ROOT / ".agents" / "skills" / "insane-research"


def main() -> int:
    if not SOURCE.is_dir():
        raise SystemExit(f"canonical skill missing: {SOURCE}")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, TARGET, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print(f"synced {SOURCE} -> {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
