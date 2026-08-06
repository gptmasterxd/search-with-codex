#!/usr/bin/env python3
"""Verify every file listed in CHECKSUMS.sha256 using the standard library."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKSUMS = ROOT / "CHECKSUMS.sha256"


def main() -> int:
    if not CHECKSUMS.exists():
        print(f"missing: {CHECKSUMS}", file=sys.stderr)
        return 2
    failures: list[str] = []
    checked = 0
    for line_no, raw in enumerate(CHECKSUMS.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            expected, relative = raw.split("  ", 1)
        except ValueError:
            failures.append(f"line {line_no}: malformed checksum entry")
            continue
        path = ROOT / relative
        if not path.is_file():
            failures.append(f"missing: {relative}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        checked += 1
        if actual != expected:
            failures.append(f"mismatch: {relative}")
    if failures:
        print("RELEASE CHECK: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"RELEASE CHECK: PASS ({checked} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
