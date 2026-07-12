import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from media_toolkit.commands import doctor, status
from media_toolkit.workflow_doctor import inspect_directory


class WorkflowDoctorTest(unittest.TestCase):
    def test_detects_new_import_with_loose_media(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "DSC0001.HIF").write_text("hif", encoding="utf-8")

            report = inspect_directory(root)

        self.assertTrue(report.ok)
        self.assertEqual(report.inferred_stage, "new-import")
        self.assertEqual(report.status, "needs-organize")
        self.assertTrue(any("mt organize" in item for item in report.recommendations))
        self.assertTrue(any(finding.code == "unorganized-media" for finding in report.findings))

    def test_detects_new_import_for_all_supported_raw_extensions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "SIGMA0001.X3F").write_text("raw", encoding="utf-8")

            report = inspect_directory(root)

        self.assertEqual(report.inferred_stage, "new-import")
        self.assertEqual(report.summary["loose_raw"], 1)
        self.assertEqual(report.status, "needs-organize")

    def test_finalize_requires_explicit_copy_to(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._touch_exported_pair(root, "DSC0001")

            report = inspect_directory(root, workflow="finalize")

        self.assertFalse(report.ok)
        self.assertEqual(report.status, "blocked")
        self.assertTrue(any("--copy-to" in item for item in report.recommendations))
        self.assertTrue(any(finding.code == "missing-copy-to" for finding in report.findings))

    def test_finalize_rejects_copy_to_inside_source(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._touch_exported_pair(root, "DSC0001")

            report = inspect_directory(
                root,
                workflow="finalize",
                copy_to=root / "featured",
            )

        self.assertFalse(report.ok)
        self.assertEqual(report.status, "blocked")
        self.assertTrue(
            any(finding.code == "copy-to-inside-source" for finding in report.findings)
        )

    def test_finalize_reports_missing_hif_for_export_as_warning(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "photos"
            (root / "raw/Export").mkdir(parents=True)
            (root / "raw/Export/DSC0001.jpg").write_text("export", encoding="utf-8")

            report = inspect_directory(
                root,
                workflow="finalize",
                copy_to=Path(tmp) / "sdcard",
            )

        self.assertTrue(report.ok)
        self.assertEqual(report.status, "ready")
        self.assertTrue(
            any(finding.code == "missing-hif-for-export" for finding in report.findings)
        )

    def test_doctor_json_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = doctor.main([str(root), "--json"])

            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["inferred_stage"], "new-import")
        self.assertEqual(payload["status"], "needs-organize")
        self.assertTrue(payload["recommendations"])
        self.assertTrue(payload["ok"])

    def test_status_command_summarizes_counts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw/DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif/DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "portrait/1/raw").mkdir(parents=True)
            (root / "portrait/1/hif").mkdir(parents=True)
            (root / "portrait/1/raw/DSC0002.ARW").write_text("raw", encoding="utf-8")
            (root / "portrait/1/hif/DSC0002.HIF").write_text("hif", encoding="utf-8")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = status.main([str(root)])

            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn("Photo status:", output)
        self.assertIn("raw=1", output)
        self.assertIn("hif=1", output)
        self.assertIn("portrait=1", output)

    def test_status_output_includes_recommendations(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            stdout = StringIO()

            with redirect_stdout(stdout):
                status.main([str(root)])

            output = stdout.getvalue()

        self.assertIn("recommendations:", output)
        self.assertIn("mt organize", output)

    def test_incomplete_cull_structure_is_blocked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw/DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif/DSC0001.HIF").write_text("hif", encoding="utf-8")

            report = inspect_directory(root)

        self.assertTrue(report.ok)
        self.assertEqual(report.status, "blocked")

    def test_finalize_without_exports_needs_lightroom_export(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()

            report = inspect_directory(
                root,
                workflow="finalize",
                copy_to=Path(tmp).parent / "sdcard",
            )

        self.assertFalse(report.ok)
        self.assertEqual(report.status, "needs-lightroom-export")

    def test_ready_for_finalize_recommends_finalize_dry_run(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._touch_exported_pair(root, "DSC0001")

            report = inspect_directory(root)

        self.assertEqual(report.inferred_stage, "ready-for-finalize")
        self.assertTrue(any("mt finalize" in item and "--dry-run" in item for item in report.recommendations))

    def _touch_exported_pair(self, root: Path, stem: str) -> None:
        (root / "raw/Export").mkdir(parents=True)
        (root / "hif").mkdir()
        (root / "raw/Export" / f"{stem}.jpg").write_text("export", encoding="utf-8")
        (root / "hif" / f"{stem}.HIF").write_text("hif", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
