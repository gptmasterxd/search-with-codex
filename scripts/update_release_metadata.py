#!/usr/bin/env python3
"""Generate or verify MANIFEST.json and CHECKSUMS.sha256 reproducibly.

The checksum file covers every distributable file except itself. MANIFEST.json
covers every distributable payload file except MANIFEST.json and the checksum
file, avoiding circular hashes while still making additions/removals visible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_NAME = "MANIFEST.json"
CHECKSUMS_NAME = "CHECKSUMS.sha256"
IGNORED_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "RESEARCH",
    "venv",
}
IGNORED_FILES = {".coverage", ".DS_Store"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}
DEFAULT_UPSTREAM = {
    "repository": "fivetaku/insane-research",
    "version": "2.8.2",
    "commit": "68f7e59168a9c9b0a586bd4122cb7a229e119d9c",
    "license": "MIT",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, path)


def is_ignored(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    if any(part in IGNORED_DIRS for part in relative.parts[:-1]):
        return True
    if relative.name in IGNORED_FILES or relative.suffix in IGNORED_SUFFIXES:
        return True
    return False


def payload_paths(root: Path = ROOT) -> list[Path]:
    excluded = {MANIFEST_NAME, CHECKSUMS_NAME}
    return sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file()
            and path.relative_to(root).as_posix() not in excluded
            and not is_ignored(path, root)
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def release_paths(root: Path = ROOT) -> list[Path]:
    paths = payload_paths(root)
    manifest = root / MANIFEST_NAME
    if manifest.is_file():
        paths.append(manifest)
    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def load_version(root: Path = ROOT) -> str:
    plugin = load_json_object(root / ".codex-plugin" / "plugin.json")
    version = str(plugin.get("version") or "").strip()
    if not version:
        raise ValueError(".codex-plugin/plugin.json version missing")
    return version


def source_entry(path: Path, root: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def build_manifest(
    root: Path = ROOT,
    *,
    generated_at: Optional[str] = None,
    upstream: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    files = [source_entry(path, root) for path in payload_paths(root)]
    upstream_value = upstream or DEFAULT_UPSTREAM
    return {
        "name": "insane-research-codex",
        "version": load_version(root),
        "generated_at": generated_at or utc_now(),
        "upstream": upstream_value,
        "file_count_excluding_manifest_and_checksums": len(files),
        "total_bytes_excluding_manifest_and_checksums": sum(int(item["bytes"]) for item in files),
        "files": files,
    }


def checksum_text(paths: Iterable[Path], root: Path) -> str:
    lines = [f"{sha256_file(path)}  {path.relative_to(root).as_posix()}" for path in paths]
    return "\n".join(lines) + ("\n" if lines else "")


def write_release_metadata(root: Path = ROOT) -> tuple[dict[str, Any], int]:
    manifest_path = root / MANIFEST_NAME
    checksum_path = root / CHECKSUMS_NAME
    manifest = build_manifest(root)
    atomic_write_text(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    paths = release_paths(root)
    atomic_write_text(checksum_path, checksum_text(paths, root))
    return manifest, len(paths)


def parse_checksums(path: Path) -> tuple[dict[str, str], list[str]]:
    entries: dict[str, str] = {}
    errors: list[str] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return entries, [f"missing: {path.name}"]
    except (OSError, UnicodeError) as exc:
        return entries, [f"cannot read {path.name}: {exc}"]
    for line_no, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            expected, relative = raw.split("  ", 1)
        except ValueError:
            errors.append(f"line {line_no}: malformed checksum entry")
            continue
        relative = relative.strip()
        if len(expected) != 64 or any(char not in "0123456789abcdef" for char in expected):
            errors.append(f"line {line_no}: invalid sha256")
            continue
        if not relative or relative.startswith("/") or ".." in Path(relative).parts:
            errors.append(f"line {line_no}: unsafe path '{relative}'")
            continue
        if relative in entries:
            errors.append(f"line {line_no}: duplicate path '{relative}'")
            continue
        entries[relative] = expected
    return entries, errors


def _manifest_comparable(value: dict[str, Any]) -> dict[str, Any]:
    comparable = dict(value)
    comparable.pop("generated_at", None)
    return comparable


def check_release(root: Path = ROOT) -> tuple[list[str], int]:
    errors: list[str] = []
    manifest_path = root / MANIFEST_NAME
    checksum_path = root / CHECKSUMS_NAME
    manifest = load_json_object(manifest_path)
    if not manifest:
        errors.append(f"missing or invalid: {MANIFEST_NAME}")
    else:
        generated_at = str(manifest.get("generated_at") or "")
        expected_manifest = build_manifest(root, generated_at=generated_at)
        if _manifest_comparable(manifest) != _manifest_comparable(expected_manifest):
            errors.append("MANIFEST.json is stale; run scripts/update_release_metadata.py")
        if not generated_at:
            errors.append("MANIFEST.json generated_at missing")
        else:
            try:
                datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
            except ValueError:
                errors.append("MANIFEST.json generated_at is not ISO-8601")

    entries, parse_errors = parse_checksums(checksum_path)
    errors.extend(parse_errors)
    expected_paths = {
        path.relative_to(root).as_posix(): path
        for path in release_paths(root)
    }
    listed = set(entries)
    expected = set(expected_paths)
    for relative in sorted(expected - listed):
        errors.append(f"unlisted distributable file: {relative}")
    for relative in sorted(listed - expected):
        errors.append(f"checksum entry is not a distributable file: {relative}")
    checked = 0
    for relative in sorted(expected & listed):
        actual = sha256_file(expected_paths[relative])
        checked += 1
        if actual != entries[relative]:
            errors.append(f"checksum mismatch: {relative}")
    return errors, checked


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify metadata without modifying files")
    parser.add_argument("--json", action="store_true", help="Print a machine-readable result")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.check:
        errors, checked = check_release(ROOT)
        result = {"passed": not errors, "checked_files": checked, "errors": errors}
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif errors:
            print("RELEASE METADATA: FAIL", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
        else:
            print(f"RELEASE METADATA: PASS ({checked} files)")
        return 0 if not errors else 1

    manifest, checked = write_release_metadata(ROOT)
    result = {
        "written": True,
        "version": manifest["version"],
        "payload_files": manifest["file_count_excluding_manifest_and_checksums"],
        "checksummed_files": checked,
    }
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(
            f"release metadata updated: version={result['version']} "
            f"payload={result['payload_files']} checksums={checked}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
