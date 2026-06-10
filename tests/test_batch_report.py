import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from media_toolkit.commands import batch_report


class BatchReportTest(unittest.TestCase):
    def test_batch_report_summarizes_root_and_groups(self):
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
                exit_code = batch_report.main([str(root)])

            output = stdout.getvalue()

        self.assertEqual(exit_code, 0)
        self.assertIn("Batch report:", output)
        self.assertIn("total media: raw=2, hif=2", output)
        self.assertIn("portrait: groups=1", output)

    def test_batch_report_json_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "DSC0001.ARW").write_text("raw", encoding="utf-8")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = batch_report.main([str(root), "--json"])

            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["status"], "needs-organize")


if __name__ == "__main__":
    unittest.main()
