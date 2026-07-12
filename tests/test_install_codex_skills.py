from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALLER = REPO_ROOT / "scripts" / "install-codex-skills.sh"
SKILL_NAMES = (
    "initial-cull",
    "extract-feature",
    "learn-color-style",
    "apple-photos-location-fill",
)


class InstallCodexSkillsTests(unittest.TestCase):
    def run_installer(
        self, home: Path, *args: str
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["HOME"] = str(home)
        env.pop("CODEX_HOME", None)
        return subprocess.run(
            ["sh", str(INSTALLER), *args],
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

    def test_preflight_failure_does_not_partially_install_other_skills(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            blocked = home / ".codex" / "skills" / "learn-color-style"
            blocked.mkdir(parents=True)
            (blocked / "SKILL.md").write_text("local", encoding="utf-8")

            result = self.run_installer(home)

            self.assertNotEqual(result.returncode, 0)
            for name in SKILL_NAMES:
                destination = home / ".codex" / "skills" / name
                if name == "learn-color-style":
                    self.assertTrue(destination.is_dir())
                else:
                    self.assertFalse(destination.exists(), name)
                    self.assertFalse(destination.is_symlink(), name)

    def test_installer_is_idempotent_and_check_mode_verifies_links(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)

            first = self.run_installer(home)
            second = self.run_installer(home)
            checked = self.run_installer(home, "--check")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertIn("All 4 Codex skill links are current", checked.stdout)

    def test_check_mode_reports_missing_without_changing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)

            result = self.run_installer(home, "--check")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing", result.stderr)
            self.assertFalse((home / ".codex").exists())

    def test_installer_rejects_unrelated_symlink_without_replacing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            skills_root = home / ".codex" / "skills"
            skills_root.mkdir(parents=True)
            other = home / "other-skill"
            other.mkdir()
            destination = skills_root / "extract-feature"
            destination.symlink_to(other, target_is_directory=True)

            result = self.run_installer(home)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("points somewhere else", result.stderr)
            self.assertEqual(destination.resolve(), other.resolve())


if __name__ == "__main__":
    unittest.main()
