#!/usr/bin/env python3
"""Verify release completeness, manifest freshness, and every SHA-256 entry."""

from __future__ import annotations

import sys

from update_release_metadata import ROOT, check_release


def main() -> int:
    failures, checked = check_release(ROOT)
    if failures:
        print("RELEASE CHECK: FAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print(f"RELEASE CHECK: PASS ({checked} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
