import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from media_toolkit import final_hif_archive


class ExtractFeaturedRawTest(unittest.TestCase):
    def quiet_process(self, root: Path, destination: Path) -> bool:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            return final_hif_archive.process_files(root, destination)

    def test_copies_hif_preview_matching_export_stem(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sdcard"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "DSC0002.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "Export" / "DSC0001.jpg").write_text("export", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "hif" / "DSC0002.HIF").write_text("not exported", encoding="utf-8")

            self.assertTrue(self.quiet_process(root, destination))

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")
            self.assertFalse((destination / "DSC0002.HIF").exists())
            self.assertFalse((root / "featured").exists())

    def test_uses_export_jpg_as_selection_source_but_copies_hif_only(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sdcard"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertTrue(self.quiet_process(root, destination))

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")
            self.assertFalse((destination / "DSC0001.jpg").exists())

    def test_pixcake_export_can_select_hif_for_archive(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sdcard"
            (root / "raw" / "Export" / "Pixcake").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "raw" / "Export" / "Pixcake" / "DSC0001.jpg").write_text(
                "pixcake", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertTrue(self.quiet_process(root, destination))

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")

    def test_fails_when_exported_file_matching_hif_is_missing(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sdcard"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "Export" / "DSC0001.jpg").write_text("export", encoding="utf-8")

            self.assertFalse(self.quiet_process(root, destination))
            self.assertFalse((destination / "DSC0001.HIF").exists())

    def test_copies_grouped_portrait_hif_previews_from_portrait_exports_but_skips_panorama_sources(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sdcard"
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

            self.assertTrue(self.quiet_process(root, destination))

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif1")
            self.assertEqual((destination / "DSC0002.HIF").read_text(), "hif2")
            self.assertFalse((destination / "DSC0003.HIF").exists())

    def test_fails_when_no_lightroom_exports_exist(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sdcard"
            (root / "raw").mkdir(parents=True)
            (root / "hif").mkdir(parents=True)
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertFalse(self.quiet_process(root, destination))
            self.assertFalse((destination / "DSC0001.HIF").exists())

    def test_skips_panorama_raw_directories(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sdcard"
            (root / "panorama" / "1" / "raw").mkdir(parents=True)
            (root / "panorama" / "1" / "hif").mkdir(parents=True)
            (root / "panorama" / "1" / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "panorama" / "1" / "raw" / "DSC0001-Pano.dng").write_text("dng", encoding="utf-8")
            (root / "panorama" / "1" / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertFalse(self.quiet_process(root, destination))

            self.assertFalse((root / "featured").exists())

    def test_rejects_destination_inside_source_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "featured"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "raw" / "Export" / "DSC0001.jpg").write_text("export", encoding="utf-8")
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertFalse(self.quiet_process(root, destination))
            self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
