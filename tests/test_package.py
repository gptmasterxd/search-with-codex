from __future__ import annotations

import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RELEASE_SCRIPT = ROOT / "scripts" / "update_release_metadata.py"

release_spec = importlib.util.spec_from_file_location("release_metadata_test", RELEASE_SCRIPT)
assert release_spec is not None and release_spec.loader is not None
release_metadata = importlib.util.module_from_spec(release_spec)
release_spec.loader.exec_module(release_metadata)


class PackageTests(unittest.TestCase):
    def test_plugin_manifest_points_to_skill_directory(self):
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertEqual(manifest["author"]["name"], "gptmasterxd")
        self.assertTrue(manifest["interface"]["displayName"])
        self.assertTrue(manifest["interface"]["defaultPrompt"])
        self.assertTrue(manifest["interface"]["capabilities"])
        self.assertTrue((ROOT / "skills" / "insane-research" / "SKILL.md").exists())

    def test_repository_skill_mirror_is_current(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "verify_package.py")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PACKAGE CHECK: PASS", result.stdout)

    def test_release_metadata_is_current(self):
        for command in (
            [sys.executable, str(ROOT / "scripts" / "update_release_metadata.py"), "--check"],
            [sys.executable, str(ROOT / "scripts" / "verify_release.py")],
        ):
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_release_check_detects_unlisted_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".codex-plugin").mkdir()
            (root / ".codex-plugin" / "plugin.json").write_text(
                json.dumps({"version": "1.2.3"}), encoding="utf-8"
            )
            (root / "payload.txt").write_text("tracked\n", encoding="utf-8")
            release_metadata.write_release_metadata(root)
            errors, _ = release_metadata.check_release(root)
            self.assertEqual(errors, [])
            (root / "unexpected.txt").write_text("new\n", encoding="utf-8")
            errors, _ = release_metadata.check_release(root)
            self.assertTrue(any("unlisted distributable file" in error for error in errors))

    def test_release_check_detects_manifest_provenance_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / ".codex-plugin").mkdir()
            (root / ".codex-plugin" / "plugin.json").write_text(
                json.dumps({"version": "1.2.3"}), encoding="utf-8"
            )
            (root / "payload.txt").write_text("tracked\n", encoding="utf-8")
            release_metadata.write_release_metadata(root)
            manifest_path = root / "MANIFEST.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["upstream"]["commit"] = "tampered"
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
            errors, _ = release_metadata.check_release(root)
            self.assertTrue(any("MANIFEST.json is stale" in error for error in errors))

    def test_installer_dry_run_has_no_target_side_effect(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "install.py"),
                    "--scope",
                    "project",
                    "--project-root",
                    str(project),
                    "--dry-run",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((project / ".agents").exists())
            self.assertFalse((project / ".codex").exists())

    def test_installer_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            first = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "install.py"),
                    "--scope",
                    "project",
                    "--project-root",
                    str(project),
                    "--skill-only",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            second = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "install.py"),
                    "--scope",
                    "project",
                    "--project-root",
                    str(project),
                    "--skill-only",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(second.returncode, 2)
            self.assertIn("already exists", second.stderr)


if __name__ == "__main__":
    unittest.main()
