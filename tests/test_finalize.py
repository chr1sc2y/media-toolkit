import importlib.util
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "finalize.py"
SPEC = importlib.util.spec_from_file_location("finalize", SCRIPT_PATH)
finalize = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(finalize)


class FinalizeTest(unittest.TestCase):
    def test_finalize_copies_hif_to_photo_directory_featured(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "featured"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "raw" / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "raw" / "DSC0001.xmp").write_text(
                """
<rdf:Description
 crs:CameraProfile="Camera ST"
 crs:WhiteBalance="Custom"
 crs:Temperature="5450"
 crs:Tint="+11"
 crs:Exposure2012="+0.51"
 crs:Highlights2012="-85"
 crs:Shadows2012="+81"
 crs:RedSaturation="+10"
 crs:GreenSaturation="+12"
 crs:BlueSaturation="+11"
 crs:PostCropVignetteAmount="-5" />
""",
                encoding="utf-8",
            )
            source_hif = root / "hif" / "DSC0001.HIF"
            source_hif.write_text("hif", encoding="utf-8")
            os.utime(source_hif, (1_600_000_000, 1_600_000_000))

            self.assertTrue(finalize.finalize_directory(root, scene="flower-field"))

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")
            self.assertEqual(
                int((destination / "DSC0001.HIF").stat().st_mtime),
                1_600_000_000,
            )
            self.assertFalse((root / "style_learning").exists())

    def test_finalize_copies_in_filename_order_to_photo_directory_featured(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "featured"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()

            for stem in ("DSC0002", "DSC0001"):
                (root / "raw" / "Export" / f"{stem}.jpg").write_text(
                    "export", encoding="utf-8"
                )
                hif = root / "hif" / f"{stem}.HIF"
                hif.write_text(stem, encoding="utf-8")

            self.assertTrue(finalize.finalize_directory(root, scene="ordering-test"))

            self.assertEqual(
                [path.name for path in sorted(destination.iterdir())],
                ["DSC0001.HIF", "DSC0002.HIF"],
            )

    def test_finalize_skips_existing_photo_directory_featured_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "featured"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            destination.mkdir(parents=True)
            existing = destination / "DSC0001.HIF"
            existing.write_text("existing", encoding="utf-8")

            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertFalse(finalize.finalize_directory(root, scene="ordering-test"))

            self.assertEqual(existing.read_text(encoding="utf-8"), "existing")

    def test_finalize_does_not_accept_sd_destination_option(self):
        with self.assertRaises(SystemExit):
            finalize.parse_args(["/tmp/photos", "--dest", "/Volumes/SD/DCIM/101MSDCF"])


if __name__ == "__main__":
    unittest.main()
