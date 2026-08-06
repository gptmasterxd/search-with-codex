from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class PackageTests(unittest.TestCase):
    def test_plugin_manifest_points_to_skill_directory(self):
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["skills"], "./skills/")
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
