import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract_featured_raw.py"
SPEC = importlib.util.spec_from_file_location("extract_featured_raw", SCRIPT_PATH)
extract_featured_raw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extract_featured_raw)


class ExtractFeaturedRawTest(unittest.TestCase):
    def test_copies_hif_preview_matching_raw_stem(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertTrue(extract_featured_raw.process_files(root))

            featured = root / "featured"
            self.assertEqual((featured / "DSC0001.HIF").read_text(), "hif")

    def test_prefers_hif_over_raw_export_jpg(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertTrue(extract_featured_raw.process_files(root))

            featured = root / "featured"
            self.assertEqual((featured / "DSC0001.HIF").read_text(), "hif")
            self.assertFalse((featured / "DSC0001.jpg").exists())

    def test_fails_when_matching_hif_is_missing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")

            self.assertFalse(extract_featured_raw.process_files(root))
            self.assertFalse((root / "featured" / "DSC0001.HIF").exists())


if __name__ == "__main__":
    unittest.main()
