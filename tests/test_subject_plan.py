from __future__ import annotations

import csv
import unittest
from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit import rawpy_tools


class SubjectPlanTest(unittest.TestCase):
    def test_default_preview_directory_is_outside_shoot(self):
        from media_toolkit.commands import subject_plan

        root = Path("/tmp/example-shoot").resolve()
        preview_dir = subject_plan.default_preview_dir(root)

        self.assertFalse(preview_dir.is_relative_to(root))
        self.assertIn("example-shoot", preview_dir.name)

    def test_discovers_only_rated_portraits_with_matching_hif_previews(self):
        from media_toolkit import subject_lift

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._candidate(root, "portrait/10", "DSC0010", 3, ".HEIC")
            self._candidate(root, "portrait/2", "DSC0002", 4, ".HEIF")
            self._candidate(root, "portrait/2", "DSC0001", 5, ".HIF")
            self._candidate(root, "portrait/1", "DSC_SKIP", 2, ".HIF")
            self._candidate(root, "panorama/1", "PANO", 5, ".HIF")
            self._candidate(root, "", "ROOT", 5, ".HIF")

            candidates = subject_lift.discover_candidates(root)

        self.assertEqual(
            [(item.raw_path.name, item.preview_path.suffix, item.rating) for item in candidates],
            [
                ("DSC0001.ARW", ".HIF", 5),
                ("DSC0002.ARW", ".HEIF", 4),
                ("DSC0010.ARW", ".HEIC", 3),
            ],
        )

    def test_rejects_eligible_portrait_without_matching_preview(self):
        from media_toolkit import subject_lift

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "portrait/1/raw"
            raw_dir.mkdir(parents=True)
            raw = raw_dir / "DSC0001.ARW"
            raw.write_text("raw", encoding="utf-8")
            rawpy_tools.write_rating_xmp_sidecar(raw, 3)

            with self.assertRaisesRegex(ValueError, "missing HIF/HEIF/HEIC"):
                subject_lift.discover_candidates(root)

    def test_command_converts_each_preview_and_writes_blank_review_plan(self):
        from media_toolkit.commands import subject_plan

        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "shoot"
            self._candidate(root, "portrait/1", "DSC0001", 3, ".HIF")
            self._candidate(root, "portrait/2", "DSC0002", 5, ".HEIF")
            output = Path(tmp) / "subject_plan.tsv"
            preview_dir = Path(tmp) / "previews"

            def fake_convert(source: Path, destination: Path) -> None:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(source.name, encoding="utf-8")

            def fake_analyze(path: Path):
                return SimpleNamespace(
                    path=path,
                    p01=0.01,
                    p50=0.25,
                    p95=0.75,
                    p99=0.90,
                    p999=0.98,
                    clip_ratio=0.001,
                    shadow_ratio=0.02,
                )

            with (
                patch.object(subject_plan, "convert_preview", side_effect=fake_convert),
                patch.object(subject_plan.rawpy_tools, "analyze_raw", side_effect=fake_analyze),
            ):
                exit_code = subject_plan.main(
                    [
                        str(root),
                        "--output",
                        str(output),
                        "--preview-dir",
                        str(preview_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                sorted(path.name for path in preview_dir.glob("*.jpg")),
                ["portrait-1-DSC0001.jpg", "portrait-2-DSC0002.jpg"],
            )
            with output.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle, delimiter="\t"))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["path"], "portrait/1/raw/DSC0001.ARW")
        self.assertEqual(rows[0]["rating"], "3")
        self.assertEqual(rows[0]["preview"], "portrait-1-DSC0001.jpg")
        for field in (
            "action",
            "subject_exposure",
            "subject_contrast",
            "subject_highlights",
            "subject_shadows",
            "subject_whites",
            "subject_blacks",
            "rationale",
        ):
            self.assertEqual(rows[0][field], "")

    def _candidate(
        self,
        root: Path,
        base: str,
        stem: str,
        rating: int,
        preview_suffix: str,
    ) -> None:
        base_dir = root / base if base else root
        raw_dir = base_dir / "raw"
        hif_dir = base_dir / "hif"
        raw_dir.mkdir(parents=True, exist_ok=True)
        hif_dir.mkdir(parents=True, exist_ok=True)
        raw = raw_dir / f"{stem}.ARW"
        raw.write_text("raw", encoding="utf-8")
        (hif_dir / f"{stem}{preview_suffix}").write_text("preview", encoding="utf-8")
        rawpy_tools.write_rating_xmp_sidecar(raw, rating)


if __name__ == "__main__":
    unittest.main()
