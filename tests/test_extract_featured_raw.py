import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract_featured_raw.py"
SPEC = importlib.util.spec_from_file_location("extract_featured_raw", SCRIPT_PATH)
extract_featured_raw = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(extract_featured_raw)


class ExtractFeaturedRawTest(unittest.TestCase):
    def test_copies_hif_preview_matching_export_stem(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "sdcard"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "DSC0002.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "Export" / "DSC0001.jpg").write_text("export", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "hif" / "DSC0002.HIF").write_text("not exported", encoding="utf-8")

            self.assertTrue(extract_featured_raw.process_files(root, destination))

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")
            self.assertFalse((destination / "DSC0002.HIF").exists())
            self.assertFalse((root / "featured").exists())

    def test_uses_export_jpg_as_selection_source_but_copies_hif_only(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "sdcard"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertTrue(extract_featured_raw.process_files(root, destination))

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")
            self.assertFalse((destination / "DSC0001.jpg").exists())

    def test_fails_when_exported_file_matching_hif_is_missing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "sdcard"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "Export" / "DSC0001.jpg").write_text("export", encoding="utf-8")

            self.assertFalse(extract_featured_raw.process_files(root, destination))
            self.assertFalse((destination / "DSC0001.HIF").exists())

    def test_copies_grouped_portrait_hif_previews_from_portrait_exports_but_skips_panorama_sources(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "sdcard"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "portrait" / "1" / "raw" / "Export").mkdir(parents=True)
            (root / "portrait" / "1" / "hif").mkdir(parents=True)
            (root / "panorama" / "1" / "raw" / "Export").mkdir(parents=True)
            (root / "panorama" / "1" / "hif").mkdir(parents=True)
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "Export" / "DSC0001.jpg").write_text("export", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif1", encoding="utf-8")
            (root / "portrait" / "1" / "raw" / "DSC0002.ARW").write_text("raw", encoding="utf-8")
            (root / "portrait" / "1" / "raw" / "Export" / "DSC0002.jpg").write_text("export", encoding="utf-8")
            (root / "portrait" / "1" / "hif" / "DSC0002.HIF").write_text("hif2", encoding="utf-8")
            (root / "panorama" / "1" / "raw" / "DSC0003.ARW").write_text("raw", encoding="utf-8")
            (root / "panorama" / "1" / "raw" / "Export" / "DSC0003.jpg").write_text("export", encoding="utf-8")
            (root / "panorama" / "1" / "hif" / "DSC0003.HIF").write_text("hif3", encoding="utf-8")

            self.assertTrue(extract_featured_raw.process_files(root, destination))

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif1")
            self.assertEqual((destination / "DSC0002.HIF").read_text(), "hif2")
            self.assertFalse((destination / "DSC0003.HIF").exists())

    def test_fails_when_no_lightroom_exports_exist(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "sdcard"
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertFalse(extract_featured_raw.process_files(root, destination))
            self.assertFalse((destination / "DSC0001.HIF").exists())

    def test_skips_panorama_raw_directories(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "sdcard"
            (root / "panorama" / "1" / "raw").mkdir(parents=True)
            (root / "panorama" / "1" / "hif").mkdir(parents=True)
            (root / "panorama" / "1" / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "panorama" / "1" / "raw" / "DSC0001-Pano.dng").write_text("dng", encoding="utf-8")
            (root / "panorama" / "1" / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertFalse(extract_featured_raw.process_files(root, destination))

            self.assertFalse((root / "featured").exists())


if __name__ == "__main__":
    unittest.main()
