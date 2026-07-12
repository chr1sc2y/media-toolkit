import csv
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit import rawpy_tools
from media_toolkit.commands import lr_apply


class LrApplyTest(unittest.TestCase):
    def test_applies_reviewed_plan_without_reanalyzing_raw(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_file = root / "raw" / "DSC0001.ARW"
            raw_file.parent.mkdir()
            raw_file.write_text("raw", encoding="utf-8")
            rawpy_tools.write_lr_xmp_sidecar(
                raw_file,
                {"HasSettings": "True", "AlreadyApplied": "False"},
                rating=4,
            )
            plan = root / "lr_plan.tsv"
            self._write_plan(plan, rating="4", exposure="0.42")

            with patch.object(
                rawpy_tools,
                "analyze_raw",
                side_effect=AssertionError("reviewed plan must not reanalyze RAW"),
            ), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = lr_apply.main([str(root), "--plan", str(plan)])

            xmp_text = raw_file.with_suffix(".xmp").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 0)
        self.assertIn('crs:Exposure2012="+0.42"', xmp_text)

    def test_rejects_stale_reviewed_plan_before_updating_any_sidecar(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            raws = []
            before = []
            for stem, rating in (("DSC0001", 4), ("DSC0002", 3)):
                raw_file = raw_dir / f"{stem}.ARW"
                raw_file.write_text("raw", encoding="utf-8")
                rawpy_tools.write_lr_xmp_sidecar(
                    raw_file,
                    {"HasSettings": "True", "AlreadyApplied": "False"},
                    rating=rating,
                )
                raws.append(raw_file)
                before.append(raw_file.with_suffix(".xmp").read_text(encoding="utf-8"))
            plan = root / "lr_plan.tsv"
            self._write_plan(plan, rating="4", exposure="0.42")
            self._append_plan_row(plan, "raw/DSC0002.ARW", "DSC0002", "4", "0.25")

            stderr = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                exit_code = lr_apply.main([str(root), "--plan", str(plan)])

            after = [raw.with_suffix(".xmp").read_text(encoding="utf-8") for raw in raws]

        self.assertEqual(exit_code, 2)
        self.assertEqual(after, before)
        self.assertIn("rating changed since plan review", stderr.getvalue())

    def test_rejects_invalid_existing_xmp_before_updating_other_planned_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            first = raw_dir / "DSC0001.ARW"
            second = raw_dir / "DSC0002.ARW"
            for raw_file in (first, second):
                raw_file.write_text("raw", encoding="utf-8")
            rawpy_tools.write_rating_xmp_sidecar(first, 4)
            first_before = first.with_suffix(".xmp").read_text(encoding="utf-8")
            second.with_suffix(".xmp").write_text(
                '<rdf:Description xmp:Rating="4" />',
                encoding="utf-8",
            )
            plan = root / "lr_plan.tsv"
            self._write_plan(plan, rating="4", exposure="0.42")
            self._append_plan_row(plan, "raw/DSC0002.ARW", "DSC0002", "4", "0.25")

            stderr = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                exit_code = lr_apply.main([str(root), "--plan", str(plan)])

            first_after = first.with_suffix(".xmp").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 2)
        self.assertEqual(first_after, first_before)
        self.assertIn("invalid XMP", stderr.getvalue())

    def test_rejects_empty_reviewed_plan_instead_of_reporting_zero_writes(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan = root / "lr_plan.tsv"
            self._write_plan(plan, rating="4", exposure="0.42")
            lines = plan.read_text(encoding="utf-8").splitlines()
            plan.write_text(lines[0] + "\n", encoding="utf-8")

            stderr = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                exit_code = lr_apply.main([str(root), "--plan", str(plan)])

        self.assertEqual(exit_code, 2)
        self.assertIn("contains no rows", stderr.getvalue())

    def test_rejects_plan_style_incompatible_with_xmp_profile_before_writing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_file = root / "raw" / "DSC0001.ARW"
            raw_file.parent.mkdir()
            raw_file.write_text("raw", encoding="utf-8")
            rawpy_tools.write_rating_xmp_sidecar(raw_file, 4)
            before = raw_file.with_suffix(".xmp").read_text(encoding="utf-8")
            plan = root / "lr_plan.tsv"
            self._write_plan(
                plan,
                rating="4",
                exposure="0.42",
                plan_style="flower",
            )
            stderr = StringIO()

            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                exit_code = lr_apply.main(
                    [
                        str(root),
                        "--plan",
                        str(plan),
                        "--style",
                        "travel-rich",
                    ]
                )

            after = raw_file.with_suffix(".xmp").read_text(encoding="utf-8")

        self.assertEqual(exit_code, 2)
        self.assertEqual(after, before)
        self.assertIn("plan style", stderr.getvalue())
        self.assertIn("travel-rich", stderr.getvalue())

    def _write_plan(
        self,
        path: Path,
        *,
        rating: str,
        exposure: str,
        plan_style: str = "travel",
    ) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(
                [
                    "path",
                    "stem",
                    "rating",
                    "plan_style",
                    "Exposure2012",
                    "Highlights2012",
                    "Shadows2012",
                    "Whites2012",
                    "Blacks2012",
                    "Contrast2012",
                    "rationale",
                ]
            )
            writer.writerow(
                [
                    "raw/DSC0001.ARW",
                    "DSC0001",
                    rating,
                    plan_style,
                    exposure,
                    "-70",
                    "24",
                    "0",
                    "0",
                    "0",
                    "reviewed",
                ]
            )

    def _append_plan_row(
        self,
        path: Path,
        raw_path: str,
        stem: str,
        rating: str,
        exposure: str,
    ) -> None:
        with path.open("a", encoding="utf-8", newline="") as handle:
            csv.writer(handle, delimiter="\t").writerow(
                [
                    raw_path,
                    stem,
                    rating,
                    "travel",
                    exposure,
                    "-70",
                    "24",
                    "0",
                    "0",
                    "0",
                    "reviewed",
                ]
            )


if __name__ == "__main__":
    unittest.main()
