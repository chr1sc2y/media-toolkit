import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit.commands import verify_cull


class VerifyCullTest(unittest.TestCase):
    def test_verify_passes_for_paired_root_portrait_and_panorama(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._touch_pair(root / "raw", root / "hif", "DSC0001")
            self._touch_pair(root / "portrait/1/raw", root / "portrait/1/hif", "DSC0002")
            self._touch_pair(root / "panorama/1/raw", root / "panorama/1/hif", "DSC0003")
            (root / "_contact_sheet.jpg").write_text("sheet", encoding="utf-8")
            (root / "portrait/_contact_sheet.jpg").write_text("sheet", encoding="utf-8")
            (root / "panorama/_contact_sheet.jpg").write_text("sheet", encoding="utf-8")

            report = verify_cull.verify_directory(root)

        self.assertTrue(report.ok)
        self.assertEqual(report.counts["root"].raw, 1)
        self.assertEqual(report.counts["portrait/1"].hif, 1)
        self.assertEqual(report.counts["panorama/1"].raw, 1)

    def test_verify_fails_on_raw_hif_mismatch(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw/DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "_contact_sheet.jpg").write_text("sheet", encoding="utf-8")

            report = verify_cull.verify_directory(root)

        self.assertFalse(report.ok)
        self.assertTrue(any("missing HIF" in issue for issue in report.issues))

    def test_verify_allows_hif_only_backups(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._touch_pair(root / "raw", root / "hif", "DSC0001")
            (root / "hif/DSC0002.HIF").write_text("hif", encoding="utf-8")
            (root / "_contact_sheet.jpg").write_text("sheet", encoding="utf-8")

            report = verify_cull.verify_directory(root)

        self.assertTrue(report.ok)
        self.assertEqual(report.counts["root"].raw, 1)
        self.assertEqual(report.counts["root"].hif, 2)

    def test_verify_fails_when_portrait_sheet_missing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._touch_pair(root / "raw", root / "hif", "DSC0001")
            self._touch_pair(root / "portrait/1/raw", root / "portrait/1/hif", "DSC0002")
            (root / "_contact_sheet.jpg").write_text("sheet", encoding="utf-8")

            report = verify_cull.verify_directory(root)

        self.assertFalse(report.ok)
        self.assertTrue(any("portrait/_contact_sheet.jpg" in issue for issue in report.issues))

    def test_verify_fails_on_temporary_review_dirs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._touch_pair(root / "raw", root / "hif", "DSC0001")
            (root / "_contact_sheet.jpg").write_text("sheet", encoding="utf-8")
            (root / ".codex_contact_tmp").mkdir()

            report = verify_cull.verify_directory(root)

        self.assertFalse(report.ok)
        self.assertTrue(any("temporary artifact" in issue for issue in report.issues))

    def test_verify_fails_on_redundant_contact_sheet_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._touch_pair(root / "raw", root / "hif", "DSC0001")
            (root / "_contact_sheet.jpg").write_text("sheet", encoding="utf-8")
            (root / "_select_contact_sheet.jpg").write_text("old sheet", encoding="utf-8")

            report = verify_cull.verify_directory(root)

        self.assertFalse(report.ok)
        self.assertTrue(any("redundant contact sheet" in issue for issue in report.issues))

    def test_main_returns_nonzero_when_report_has_issues(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "raw/DSC0001.ARW").write_text("raw", encoding="utf-8")

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = verify_cull.main([str(root)])

        self.assertEqual(exit_code, 1)

    def test_verify_rawpy_reports_unreadable_raw_when_enabled(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._touch_pair(root / "raw", root / "hif", "DSC0001")
            (root / "_contact_sheet.jpg").write_text("sheet", encoding="utf-8")

            with patch.object(
                verify_cull.rawpy_tools,
                "analyze_raw",
                side_effect=RuntimeError("unsupported raw"),
            ):
                report = verify_cull.verify_directory(root, check_rawpy=True)

        self.assertFalse(report.ok)
        self.assertTrue(any("rawpy failed" in issue for issue in report.issues))

    def _touch_pair(self, raw_dir: Path, hif_dir: Path, stem: str):
        raw_dir.mkdir(parents=True, exist_ok=True)
        hif_dir.mkdir(parents=True, exist_ok=True)
        (raw_dir / f"{stem}.ARW").write_text("raw", encoding="utf-8")
        (hif_dir / f"{stem}.HIF").write_text("hif", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
