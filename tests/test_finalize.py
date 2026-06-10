import os
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from media_toolkit.commands import finalize


class FinalizeTest(unittest.TestCase):
    def quiet_call(self, func, *args, **kwargs):
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            return func(*args, **kwargs)

    def test_finalize_copies_hif_to_explicit_destination(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "archive"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir(parents=True)
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

            self.assertTrue(
                self.quiet_call(
                    finalize.finalize_directory,
                    root, copy_to=destination, scene="flower-field"
                )
            )

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")
            self.assertEqual(
                int((destination / "DSC0001.HIF").stat().st_mtime),
                1_600_000_000,
            )
            self.assertFalse((root / "featured").exists())
            self.assertFalse((root / "style_learning").exists())

    def test_finalize_copies_in_filename_order_to_explicit_destination(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "archive"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir(parents=True)

            for stem in ("DSC0002", "DSC0001"):
                (root / "raw" / "Export" / f"{stem}.jpg").write_text(
                    "export", encoding="utf-8"
                )
                hif = root / "hif" / f"{stem}.HIF"
                hif.write_text(stem, encoding="utf-8")

            self.assertTrue(
                self.quiet_call(
                    finalize.finalize_directory,
                    root, copy_to=destination, scene="ordering-test"
                )
            )

            self.assertEqual(
                [path.name for path in sorted(destination.iterdir())],
                ["DSC0001.HIF", "DSC0002.HIF"],
            )

    def test_finalize_skips_existing_explicit_destination_files(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "archive"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir(parents=True)
            destination.mkdir(parents=True)
            existing = destination / "DSC0001.HIF"
            existing.write_text("existing", encoding="utf-8")

            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertFalse(
                self.quiet_call(
                    finalize.finalize_directory,
                    root, copy_to=destination, scene="ordering-test"
                )
            )

            self.assertEqual(existing.read_text(encoding="utf-8"), "existing")

    def test_finalize_does_not_accept_legacy_sd_destination_option(self):
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            finalize.parse_args(["/tmp/photos", "--dest", "/Volumes/SD/DCIM/101MSDCF"])

    def test_finalize_requires_copy_destination(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(self.quiet_call(finalize.main, [str(root)]), 2)
            self.assertEqual(
                self.quiet_call(
                    finalize.main,
                    [str(root), "--photos-album", "Sony", "--photos-dry-run"],
                ),
                2,
            )

    def test_finalize_hif_only_copies_without_photos_import(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sdcard"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir(parents=True)
            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertEqual(
                self.quiet_call(
                    finalize.main,
                    [str(root), "--copy-to", str(destination), "--hif-only"]
                ),
                0,
            )

            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")

    def test_finalize_rejects_copy_destination_inside_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "archive"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir()
            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertEqual(
                self.quiet_call(
                    finalize.main,
                    [str(root), "--copy-to", str(destination), "--hif-only"]
                ),
                2,
            )

            self.assertFalse(destination.exists())

    def test_collect_photos_exports_includes_root_portrait_and_panorama(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in (
                root / "raw" / "Export" / "DSC0001.jpg",
                root / "portrait" / "1" / "raw" / "Export" / "DSC0002.JPG",
                root / "panorama" / "1" / "raw" / "Export" / "DSC0003.jpeg",
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("jpg", encoding="utf-8")

            exports = finalize.collect_photos_export_files(root)

            self.assertEqual(
                [path.name for path in exports],
                ["DSC0001.jpg", "DSC0002.JPG", "DSC0003.jpeg"],
            )

    def test_photos_dry_run_lists_exports_without_osascript(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            export = root / "raw" / "Export" / "DSC0001.jpg"
            export.parent.mkdir(parents=True)
            export.write_text("jpg", encoding="utf-8")
            runner = Mock()

            self.assertTrue(
                self.quiet_call(
                    finalize.import_exports_to_photos,
                    root,
                    album="Sony",
                    dry_run=True,
                    runner=runner,
                )
            )
            runner.assert_not_called()

    def test_photos_import_invokes_osascript_with_exports_and_album(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for path in (
                root / "raw" / "Export" / "DSC0001.jpg",
                root / "portrait" / "1" / "raw" / "Export" / "DSC0002.jpg",
                root / "panorama" / "1" / "raw" / "Export" / "DSC0003.jpg",
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("jpg", encoding="utf-8")
            runner = Mock(return_value=subprocess.CompletedProcess(["osascript"], 0))

            self.assertTrue(
                self.quiet_call(
                    finalize.import_exports_to_photos,
                    root,
                    album="Sony",
                    runner=runner,
                )
            )

            args, kwargs = runner.call_args
            self.assertEqual(args[0][0], "osascript")
            script = args[0][2]
            self.assertIn('album "Sony"', script)
            self.assertIn("DSC0001.jpg", script)
            self.assertIn("DSC0002.jpg", script)
            self.assertIn("DSC0003.jpg", script)
            self.assertTrue(kwargs["check"])
            self.assertTrue(kwargs["capture_output"])

    def test_finalize_can_copy_hif_and_import_exports_in_one_run(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sd" / "DCIM" / "101MSDCF"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir(parents=True)
            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertTrue(
                self.quiet_call(
                    finalize.finalize_directory,
                    root,
                    copy_to=destination,
                    scene="grassland",
                    photos_album="Sony",
                    photos_dry_run=True,
                )
            )
            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")

    def test_finalize_dry_run_does_not_copy_hif_or_import_photos(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sd" / "DCIM" / "101MSDCF"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir(parents=True)
            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertEqual(
                self.quiet_call(
                    finalize.main,
                    [str(root), "--copy-to", str(destination), "--dry-run"],
                ),
                0,
            )

            self.assertFalse(destination.exists())

    def test_main_defaults_photos_album_to_sony(self):
        with TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            root = tmp_root / "photos"
            destination = tmp_root / "sd" / "DCIM" / "101MSDCF"
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "hif").mkdir(parents=True)
            (root / "raw" / "Export" / "DSC0001.jpg").write_text(
                "export", encoding="utf-8"
            )
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            self.assertEqual(
                self.quiet_call(
                    finalize.main,
                    [str(root), "--copy-to", str(destination), "--photos-dry-run"]
                ),
                0,
            )
            self.assertEqual((destination / "DSC0001.HIF").read_text(), "hif")


if __name__ == "__main__":
    unittest.main()
