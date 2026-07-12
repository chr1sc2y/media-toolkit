import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from media_toolkit.commands import preflight_run
from media_toolkit.preflight import preflight_finalize


class PreflightTest(unittest.TestCase):
    def test_finalize_preflight_go_runs_dry_run_without_copying(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "photos"
            destination = Path(tmp) / "sd" / "DCIM" / "101MSDCF"
            self._touch_exported_pair(root, "DSC0001")

            report = preflight_finalize(
                root,
                copy_to=destination,
                scene="grassland",
                hif_only=True,
            )

        self.assertTrue(report.ok)
        self.assertEqual(report.decision, "GO")
        self.assertEqual(report.dry_run_exit_code, 0)
        self.assertIn("Would copy", report.dry_run_output)
        self.assertFalse(destination.exists())

    def test_finalize_preflight_no_go_when_copy_to_missing_from_cli(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "photos"
            self._touch_exported_pair(root, "DSC0001")

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                preflight_run.parse_args(["finalize", str(root)])

    def test_finalize_preflight_no_go_for_inside_destination(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "photos"
            self._touch_exported_pair(root, "DSC0001")

            report = preflight_finalize(
                root,
                copy_to=root / "featured",
                scene="grassland",
            )

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, "NO-GO")
        self.assertTrue(any("copy-to-inside-source" in reason for reason in report.reasons))

    def test_preflight_run_json_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "photos"
            destination = Path(tmp) / "sd"
            self._touch_exported_pair(root, "DSC0001")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = preflight_run.main(
                    [
                        "finalize",
                        str(root),
                        "--copy-to",
                        str(destination),
                        "--scene",
                        "grassland",
                        "--hif-only",
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["decision"], "GO")
        self.assertEqual(payload["workflow"], "finalize")

    def test_finalize_preflight_recursive_checks_scene_subdirectories(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "photos"
            destination = Path(tmp) / "sd" / "DCIM" / "101MSDCF"
            self._touch_exported_pair(root / "lake-valley", "DSC0001")
            self._touch_exported_pair(root / "snow-top", "DSC0002")

            report = preflight_finalize(
                root,
                copy_to=destination,
                scene="snow-mountain",
                hif_only=True,
                recursive=True,
            )

        self.assertTrue(report.ok)
        self.assertEqual(report.dry_run_exit_code, 0)
        self.assertIn("lake-valley", report.dry_run_output)
        self.assertIn("snow-top", report.dry_run_output)
        self.assertIn("Would copy: 2 files", report.dry_run_output)

    def test_finalize_preflight_defaults_to_recursive_subdirectories(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "photos"
            destination = Path(tmp) / "sd" / "DCIM" / "101MSDCF"
            self._touch_exported_pair(root / "lake-valley", "DSC0001")

            report = preflight_finalize(
                root,
                copy_to=destination,
                scene="overcast-travel",
                hif_only=True,
            )

        self.assertTrue(report.ok)
        self.assertIn("lake-valley", report.dry_run_output)

    def test_preflight_run_recursive_cli_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "photos"
            destination = Path(tmp) / "sd"
            self._touch_exported_pair(root / "lake-valley", "DSC0001")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = preflight_run.main(
                    [
                        "finalize",
                        str(root),
                        "--copy-to",
                        str(destination),
                        "--scene",
                        "overcast-travel",
                        "--hif-only",
                        "--recursive",
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["decision"], "GO")
        self.assertEqual(payload["doctor"]["summary"]["finalize_directories"], 1)

    def test_recursive_preflight_allows_panorama_only_photos_import(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "photos"
            destination = Path(tmp) / "sd"
            export = root / "panorama" / "1" / "raw" / "Export" / "final.jpg"
            export.parent.mkdir(parents=True)
            export.write_text("stitched panorama", encoding="utf-8")

            report = preflight_finalize(
                root,
                copy_to=destination,
                scene="panorama",
                hif_only=False,
                recursive=True,
            )

        self.assertTrue(report.ok)
        self.assertEqual(report.decision, "GO")
        self.assertEqual(report.dry_run_exit_code, 0)
        self.assertIn("Would import", report.dry_run_output)
        self.assertEqual(report.doctor["summary"]["finalize_directories"], 0)
        self.assertEqual(report.doctor["summary"]["photos_import_directories"], 1)

    def _touch_exported_pair(self, root: Path, stem: str) -> None:
        (root / "raw" / "Export").mkdir(parents=True)
        (root / "hif").mkdir()
        (root / "raw" / "Export" / f"{stem}.jpg").write_text("export", encoding="utf-8")
        (root / "hif" / f"{stem}.HIF").write_text("hif", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
