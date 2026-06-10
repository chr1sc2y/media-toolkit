import unittest
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit.commands.organize import main, organize_directory


class OrganizeSonyMediaTest(unittest.TestCase):
    def test_moves_hif_and_raw_files_into_per_directory_buckets(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            child = root / "nested"
            child.mkdir()

            (root / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "notes.txt").write_text("text", encoding="utf-8")
            (child / "DSC0002.HEIF").write_text("heif", encoding="utf-8")
            (child / "DSC0002.RAW").write_text("raw", encoding="utf-8")

            summary = organize_directory(root, verbose=False)

            self.assertEqual(summary.moved, 4)
            self.assertEqual(summary.moved_by_type["hif"], 2)
            self.assertEqual(summary.moved_by_type["raw"], 2)
            self.assertEqual(
                summary.destination_dirs_by_type["hif"],
                {root / "hif", child / "hif"},
            )
            self.assertTrue((root / "hif" / "DSC0001.HIF").exists())
            self.assertTrue((root / "raw" / "DSC0001.ARW").exists())
            self.assertTrue((root / "notes.txt").exists())
            self.assertTrue((child / "hif" / "DSC0002.HEIF").exists())
            self.assertTrue((child / "raw" / "DSC0002.RAW").exists())

    def test_skips_existing_output_directories(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            existing_hif = root / "hif"
            existing_raw = root / "raw"
            existing_hif.mkdir()
            existing_raw.mkdir()
            (existing_hif / "already.HIF").write_text("hif", encoding="utf-8")
            (existing_raw / "already.ARW").write_text("raw", encoding="utf-8")

            summary = organize_directory(root, verbose=False)

            self.assertEqual(summary.moved, 0)
            self.assertTrue((existing_hif / "already.HIF").exists())
            self.assertTrue((existing_raw / "already.ARW").exists())
            self.assertFalse((existing_hif / "hif").exists())
            self.assertFalse((existing_raw / "raw").exists())

    def test_moves_sidecar_files_into_raw_bucket(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "DSC0001.xmp").write_text("xmp", encoding="utf-8")
            (root / "DSC0001.acr").write_text("acr", encoding="utf-8")

            summary = organize_directory(root, verbose=False)

            self.assertEqual(summary.moved, 3)
            self.assertEqual(summary.moved_by_type["raw"], 3)
            self.assertTrue((root / "raw" / "DSC0001.ARW").exists())
            self.assertTrue((root / "raw" / "DSC0001.xmp").exists())
            self.assertTrue((root / "raw" / "DSC0001.acr").exists())

    def test_supports_other_camera_raw_extensions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "FUJI0001.RAF").write_text("fuji raw", encoding="utf-8")
            (root / "IPHONE0001.DNG").write_text("iphone raw", encoding="utf-8")

            summary = organize_directory(root, verbose=False)

            self.assertEqual(summary.moved, 2)
            self.assertEqual(summary.moved_by_type["raw"], 2)
            self.assertTrue((root / "raw" / "FUJI0001.RAF").exists())
            self.assertTrue((root / "raw" / "IPHONE0001.DNG").exists())

    def test_summary_does_not_print_each_move_by_default(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            (root / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "DSC0001.ARW").write_text("raw", encoding="utf-8")

            stdout = StringIO()
            with patch("sys.stdout", stdout):
                exit_code = main([str(root)])

            output = stdout.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertNotIn("MOVED ", output)
            self.assertIn("Moved files: 2", output)
            self.assertIn("hif: 1 file", output)
            self.assertIn("raw: 1 file", output)
            self.assertIn(str(root / "hif"), output)
            self.assertIn(str(root / "raw"), output)


if __name__ == "__main__":
    unittest.main()
