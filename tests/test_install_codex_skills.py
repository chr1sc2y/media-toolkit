from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install-codex-skills.sh"
SKILL_NAMES = ("initial-cull", "extract-feature", "learn-color-style")


class InstallCodexSkillsTests(unittest.TestCase):
    def run_installer(self, home: Path) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home)
        env.pop("CODEX_HOME", None)
        return subprocess.run(
            ["sh", str(INSTALLER)],
            cwd=REPO_ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_installer_links_all_repository_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            result = self.run_installer(home)

            self.assertEqual(result.returncode, 0, result.stderr)
            for name in SKILL_NAMES:
                link = home / ".codex" / "skills" / name
                self.assertTrue(link.is_symlink(), name)
                self.assertEqual(link.resolve(), (REPO_ROOT / "skills" / name).resolve())

    def test_installer_preserves_existing_real_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            existing = home / ".codex" / "skills" / "initial-cull"
            existing.mkdir(parents=True)
            marker = existing / "local-edit.txt"
            marker.write_text("keep me", encoding="utf-8")

            result = self.run_installer(home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not a symlink", result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep me")


if __name__ == "__main__":
    unittest.main()
