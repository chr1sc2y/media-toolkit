import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from media_toolkit.commands import learn_style
from media_toolkit.style_learning import learn_style_from_directory


class StyleLearningTest(unittest.TestCase):
    def test_learns_fields_from_root_and_portrait_exports(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_export_and_xmp(root / "raw", "DSC0001", "Camera ST", "-85")
            self._write_export_and_xmp(root / "portrait/1/raw", "DSC0002", "Camera PT", "-70")

            report = learn_style_from_directory(root, scene="flower-field")

        self.assertEqual(report.sample_count, 2)
        self.assertEqual(report.field_values["CameraProfile"], ["Camera PT", "Camera ST"])
        self.assertEqual(report.field_values["Highlights2012"], ["-70", "-85"])

    def test_reports_missing_xmp_for_export(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw/Export").mkdir(parents=True)
            (root / "raw/Export/DSC0001.jpg").write_text("export", encoding="utf-8")

            report = learn_style_from_directory(root, scene="grassland")

        self.assertEqual(report.sample_count, 0)
        self.assertEqual(report.missing_xmp, ["raw/Export/DSC0001.jpg"])

    def test_learn_style_json_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_export_and_xmp(root / "raw", "DSC0001", "Camera ST", "-85")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = learn_style.main([str(root), "--scene", "flower-field", "--json"])

            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["scene"], "flower-field")
        self.assertEqual(payload["sample_count"], 1)

    def _write_export_and_xmp(self, raw_dir: Path, stem: str, profile: str, highlights: str) -> None:
        (raw_dir / "Export").mkdir(parents=True)
        (raw_dir / "Export" / f"{stem}.jpg").write_text("export", encoding="utf-8")
        (raw_dir / f"{stem}.xmp").write_text(
            f'<rdf:Description crs:CameraProfile="{profile}" crs:Highlights2012="{highlights}" />',
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
