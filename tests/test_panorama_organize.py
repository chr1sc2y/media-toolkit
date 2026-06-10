import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit.commands import panorama_organize


class PanoramaOrganizeTest(unittest.TestCase):
    def test_plan_moves_raw_hif_pairs_into_panorama_groups(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            for stem in ("DSC0001", "DSC0002"):
                (root / "raw" / f"{stem}.ARW").write_text("raw", encoding="utf-8")
                (root / "hif" / f"{stem}.HIF").write_text("hif", encoding="utf-8")
            entries = [
                panorama_organize.ManifestEntry("DSC0001", "1"),
                panorama_organize.ManifestEntry("DSC0002", "1"),
            ]

            operations = panorama_organize.build_move_plan(root, entries)

            self.assertEqual(len(operations), 4)
            panorama_organize.apply_move_plan(operations)
            self.assertTrue((root / "panorama/1/raw/DSC0001.ARW").exists())
            self.assertTrue((root / "panorama/1/hif/DSC0001.HIF").exists())
            self.assertTrue((root / "panorama/1/raw/DSC0002.ARW").exists())
            self.assertTrue((root / "panorama/1/hif/DSC0002.HIF").exists())

    def test_rebuild_contact_sheets_rebuilds_root_and_panorama_overviews(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "panorama/1/hif").mkdir(parents=True)

            with patch.object(panorama_organize, "run_command") as run_command:
                panorama_organize.rebuild_contact_sheets(root)

            commands = [call.args[0] for call in run_command.call_args_list]
            self.assertEqual(len(commands), 2)
            self.assertIn("--exclude-dir", commands[0])
            self.assertIn("portrait", commands[0])
            self.assertIn("panorama", commands[0])
            self.assertIn(str(root / "_contact_sheet.jpg"), commands[0])
            self.assertIn("--section-by-numbered-dir", commands[1])
            self.assertIn("--section-prefix", commands[1])
            self.assertIn("Panorama", commands[1])
            self.assertIn(str(root / "panorama/_contact_sheet.jpg"), commands[1])

    def test_dry_run_does_not_move_files_or_rebuild_sheets(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            manifest = root / "panorama_manifest.tsv"
            manifest.write_text("stem\tgroup\nDSC0001\t1\n", encoding="utf-8")
            args = panorama_organize.parse_args(
                [str(root), "--manifest", str(manifest), "--dry-run"]
            )

            with (
                patch.object(panorama_organize, "run_command") as run_command,
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                exit_code = panorama_organize.organize_panoramas(args)

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "raw/DSC0001.ARW").exists())
            self.assertFalse((root / "panorama/1/raw/DSC0001.ARW").exists())
            run_command.assert_not_called()

    def test_default_manifest_lives_under_panorama_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "panorama").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "panorama" / "panorama_manifest.tsv").write_text(
                "stem\tgroup\nDSC0001\t1\n", encoding="utf-8"
            )
            args = panorama_organize.parse_args([str(root), "--dry-run"])

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = panorama_organize.organize_panoramas(args)

            self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
