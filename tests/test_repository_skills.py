from __future__ import annotations

import json
from pathlib import Path
import re
import unittest

from media_toolkit.command_registry import resolve_command


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = REPO_ROOT / "skills"


class RepositorySkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = json.loads(
            (SKILLS_ROOT / "manifest.json").read_text(encoding="utf-8")
        )

    def test_manifest_skills_have_matching_frontmatter_and_agent_metadata(self) -> None:
        self.assertEqual(self.manifest["version"], 1)
        names = [entry["name"] for entry in self.manifest["skills"]]
        self.assertEqual(
            names,
            [
                "initial-cull",
                "extract-feature",
                "learn-color-style",
                "apple-photos-location-fill",
            ],
        )
        for entry in self.manifest["skills"]:
            name = entry["name"]
            directory = REPO_ROOT / entry["path"]
            skill_text = (directory / "SKILL.md").read_text(encoding="utf-8")
            self.assertTrue(skill_text.startswith("---\n"), name)
            self.assertIn(f"\nname: {name}\n", skill_text, name)
            self.assertRegex(skill_text, r"\ndescription: .+\n---\n")
            self.assertTrue((directory / "agents/openai.yaml").is_file(), name)

    def test_skills_are_checkout_portable(self) -> None:
        for skill_file in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
            text = skill_file.read_text(encoding="utf-8")
            self.assertNotIn("/Users/", text, skill_file.name)
            self.assertNotIn("~/.codex", text, skill_file.name)

    def test_every_documented_mt_command_exists(self) -> None:
        referenced: set[str] = set()
        for skill_file in sorted(SKILLS_ROOT.glob("*/SKILL.md")):
            text = skill_file.read_text(encoding="utf-8")
            referenced.update(re.findall(r"\bmt ([a-z][a-z0-9-]+)", text))

        failures: list[str] = []
        for command_name in sorted(referenced):
            try:
                resolve_command(command_name)
            except ValueError as exc:
                failures.append(str(exc))
        self.assertEqual(failures, [])

    def test_initial_cull_contains_executable_rating_and_plan_pipeline(self) -> None:
        text = (SKILLS_ROOT / "initial-cull/SKILL.md").read_text(encoding="utf-8")
        for snippet in (
            'mt ratings-apply "<photo-dir>" --manifest ratings.tsv --dry-run',
            'mt lr-plan "<photo-dir>"',
            'mt lr-apply "<photo-dir>"',
            'mt verify-cull "<photo-dir>"',
        ):
            self.assertIn(snippet, text)
        self.assertNotIn("ISO, shutter speed, aperture, lens model", text)
        self.assertIn("Leave\nordinary scenes in the root", text)
        self.assertIn("do not hand-move", text)
        self.assertNotIn("4-5 broad top-level scene categories", text)

    def test_initial_cull_documents_group_local_contact_sheets(self) -> None:
        text = (SKILLS_ROOT / "initial-cull/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('portrait/<group>/_contact_sheet.jpg', text)
        self.assertIn('panorama/<group>/_contact_sheet.jpg', text)
        self.assertNotIn('portrait/_contact_sheet.jpg', text)
        self.assertNotIn('panorama/_contact_sheet.jpg', text)

    def test_extract_skill_has_safe_plan_apply_and_separate_delete_gate(self) -> None:
        text = (SKILLS_ROOT / "extract-feature/SKILL.md").read_text(encoding="utf-8")
        self.assertIn('mt preflight-run finalize "<photo-dir>"', text)
        self.assertIn('mt finalize "<photo-dir>"', text)
        self.assertIn('--mode aggressive --apply-plan', text)
        self.assertIn('--confirm-delete', text)
        self.assertIn("cannot reliably report", " ".join(text.split()))
        self.assertNotIn("Use the normal finalize path", text)

    def test_learning_skill_uses_stable_name_and_real_analysis_command(self) -> None:
        text = (SKILLS_ROOT / "learn-color-style/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("name: learn-color-style", text)
        self.assertIn('mt learn-style "<photo-dir>" --scene "<scene>" --json', text)
        self.assertIn("minimum/median/maximum", text)
        self.assertNotIn("name: 学习", text)


if __name__ == "__main__":
    unittest.main()
