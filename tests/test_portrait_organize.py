import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "portrait_organize.py"
SPEC = importlib.util.spec_from_file_location("portrait_organize", SCRIPT_PATH)
portrait_organize = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(portrait_organize)


class PortraitOrganizeTest(unittest.TestCase):
    def test_read_manifest_accepts_header_and_groups_stems(self):
        with TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "portraits.tsv"
            manifest.write_text(
                "stem\tgroup\nDSC0001\t1\nDSC_SKIP\t\nDSC0002\t2\nDSC0003,2\n",
                encoding="utf-8",
            )

            entries = portrait_organize.read_manifest(manifest)

        self.assertEqual(
            [(entry.stem, entry.group) for entry in entries],
            [("DSC0001", "1"), ("DSC0002", "2"), ("DSC0003", "2")],
        )

    def test_read_manifest_rejects_duplicate_stems(self):
        with TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "portraits.tsv"
            manifest.write_text("stem\tgroup\nDSC0001\t1\nDSC0001\t2\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "duplicate stem"):
                portrait_organize.read_manifest(manifest)

    def test_plan_moves_raw_hif_pairs_into_portrait_groups(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            for stem in ("DSC0001", "DSC0002"):
                (root / "raw" / f"{stem}.ARW").write_text("raw", encoding="utf-8")
                (root / "hif" / f"{stem}.HIF").write_text("hif", encoding="utf-8")
            entries = [
                portrait_organize.ManifestEntry("DSC0001", "1"),
                portrait_organize.ManifestEntry("DSC0002", "2"),
            ]

            operations = portrait_organize.build_move_plan(root, entries)

            self.assertEqual(len(operations), 4)
            portrait_organize.apply_move_plan(operations)
            self.assertTrue((root / "portrait/1/raw/DSC0001.ARW").exists())
            self.assertTrue((root / "portrait/1/hif/DSC0001.HIF").exists())
            self.assertTrue((root / "portrait/2/raw/DSC0002.ARW").exists())
            self.assertTrue((root / "portrait/2/hif/DSC0002.HIF").exists())
            self.assertFalse((root / "raw/DSC0001.ARW").exists())
            self.assertFalse((root / "hif/DSC0002.HIF").exists())

    def test_build_move_plan_rejects_missing_pair(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")

            with self.assertRaisesRegex(FileNotFoundError, "missing HIF"):
                portrait_organize.build_move_plan(
                    root, [portrait_organize.ManifestEntry("DSC0001", "1")]
                )

    def test_generate_contact_sheets_rebuilds_root_and_portrait_overviews(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "portrait/1/hif").mkdir(parents=True)

            with patch.object(portrait_organize, "run_command") as run_command:
                portrait_organize.rebuild_contact_sheets(root)

            commands = [call.args[0] for call in run_command.call_args_list]
            self.assertEqual(len(commands), 2)
            self.assertIn("--exclude-dir", commands[0])
            self.assertIn("portrait", commands[0])
            self.assertIn("panorama", commands[0])
            self.assertIn("--final-overview", commands[0])
            self.assertIn(str(root / "_contact_sheet.jpg"), commands[0])
            self.assertIn("--section-by-numbered-dir", commands[1])
            self.assertIn("--section-prefix", commands[1])
            self.assertIn("Portrait", commands[1])

    def test_dry_run_does_not_move_files_or_rebuild_sheets(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            manifest = root / "portraits.tsv"
            manifest.write_text("stem\tgroup\nDSC0001\t1\n", encoding="utf-8")
            args = portrait_organize.parse_args(
                [str(root), "--manifest", str(manifest), "--dry-run"]
            )

            with patch.object(portrait_organize, "run_command") as run_command:
                exit_code = portrait_organize.organize_portraits(args)

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "raw/DSC0001.ARW").exists())
            self.assertFalse((root / "portrait/1/raw/DSC0001.ARW").exists())
            run_command.assert_not_called()

    def test_default_manifest_lives_under_portrait_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "portrait").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "portrait" / "portrait_manifest.tsv").write_text(
                "stem\tgroup\nDSC0001\t1\n", encoding="utf-8"
            )
            args = portrait_organize.parse_args([str(root), "--dry-run"])

            exit_code = portrait_organize.organize_portraits(args)

            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
