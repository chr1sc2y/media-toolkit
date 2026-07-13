from __future__ import annotations

import csv
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit import rawpy_tools, subject_lift


class SubjectApplyTest(unittest.TestCase):
    def test_command_dry_run_then_applies_only_after_full_validation(self):
        from media_toolkit.commands import subject_apply

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._candidate(root, "1", "DSC0001", 3)
            second = self._candidate(root, "1", "DSC0002", 4)
            plan = root / "reviewed.tsv"
            self._write_plan(
                plan,
                root,
                [
                    self._row(first, 3, "apply", "0.2", "5", "-5", "4", "0", "-4", "needs lift"),
                    self._row(second, 4, "skip", "0", "0", "0", "0", "0", "0", "already bright"),
                ],
            )

            with patch.object(subject_apply.subject_lift, "write_subject_adjustment") as writer:
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    dry_exit = subject_apply.main(
                        [str(root), "--plan", str(plan), "--dry-run"]
                    )
                writer.assert_not_called()
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    apply_exit = subject_apply.main([str(root), "--plan", str(plan)])
                self.assertEqual(writer.call_count, 2)

        self.assertEqual(dry_exit, 0)
        self.assertEqual(apply_exit, 0)

    def test_command_invalid_final_row_causes_zero_writes(self):
        from media_toolkit.commands import subject_apply

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._candidate(root, "1", "DSC0001", 3)
            second = self._candidate(root, "1", "DSC0002", 4)
            plan = root / "reviewed.tsv"
            self._write_plan(
                plan,
                root,
                [
                    self._row(first, 3, "apply", "0.2", "5", "-5", "4", "0", "-4", "needs lift"),
                    self._row(second, 4, "apply", "0.9", "5", "-5", "4", "0", "-4", "invalid"),
                ],
            )
            with patch.object(subject_apply.subject_lift, "write_subject_adjustment") as writer:
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    exit_code = subject_apply.main([str(root), "--plan", str(plan)])
                writer.assert_not_called()

        self.assertEqual(exit_code, 2)

    def test_reads_and_validates_distinct_apply_and_zero_skip_rows(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._candidate(root, "1", "DSC0001", 3)
            second = self._candidate(root, "1", "DSC0002", 4)
            third = self._candidate(root, "2", "DSC0003", 5)
            plan = root / "reviewed.tsv"
            self._write_plan(
                plan,
                root,
                [
                    self._row(first, 3, "apply", "0.12", "4", "-4", "3", "0", "-3", "already balanced"),
                    self._row(second, 4, "apply", "0.38", "10", "-18", "12", "-5", "-8", "backlit subject"),
                    self._row(third, 5, "skip", "0", "0", "0", "0", "0", "0", "subject already bright"),
                ],
            )

            adjustments = subject_lift.read_reviewed_plan(plan, root)
            pairs = subject_lift.validate_reviewed_plan(root, adjustments)

        self.assertEqual(len(pairs), 3)
        self.assertEqual(pairs[0][1].exposure, 0.12)
        self.assertEqual(pairs[1][1].contrast, 10)
        self.assertEqual(pairs[2][1].action, "skip")

    def test_rejects_duplicate_and_missing_paths(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._candidate(root, "1", "DSC0001", 3)
            self._candidate(root, "1", "DSC0002", 3)
            plan = root / "reviewed.tsv"
            row = self._row(first, 3, "skip", "0", "0", "0", "0", "0", "0", "reviewed")
            self._write_plan(plan, root, [row, row])

            with self.assertRaisesRegex(ValueError, "duplicate plan path"):
                subject_lift.read_reviewed_plan(plan, root)

            self._write_plan(plan, root, [row])
            adjustments = subject_lift.read_reviewed_plan(plan, root)
            with self.assertRaisesRegex(ValueError, "missing eligible path"):
                subject_lift.validate_reviewed_plan(root, adjustments)

    def test_rejects_stale_rating_and_out_of_range_values(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = self._candidate(root, "1", "DSC0001", 4)
            plan = root / "reviewed.tsv"
            self._write_plan(
                plan,
                root,
                [self._row(raw, 3, "apply", "0.61", "4", "-4", "3", "0", "-3", "reviewed")],
            )
            with self.assertRaisesRegex(ValueError, "out of range"):
                subject_lift.read_reviewed_plan(plan, root)

            self._write_plan(
                plan,
                root,
                [self._row(raw, 3, "apply", "0.20", "4", "-4", "3", "0", "-3", "reviewed")],
            )
            adjustments = subject_lift.read_reviewed_plan(plan, root)
            with self.assertRaisesRegex(ValueError, "rating changed"):
                subject_lift.validate_reviewed_plan(root, adjustments)

    def test_rejects_nonzero_skip_and_blank_rationale(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = self._candidate(root, "1", "DSC0001", 3)
            plan = root / "reviewed.tsv"
            self._write_plan(
                plan,
                root,
                [self._row(raw, 3, "skip", "0.1", "0", "0", "0", "0", "0", "")],
            )
            with self.assertRaisesRegex(ValueError, "rationale"):
                subject_lift.read_reviewed_plan(plan, root)

            self._write_plan(
                plan,
                root,
                [self._row(raw, 3, "skip", "0.1", "0", "0", "0", "0", "0", "reviewed")],
            )
            with self.assertRaisesRegex(ValueError, "skip row"):
                subject_lift.read_reviewed_plan(plan, root)

    def test_writes_distinct_select_subject_values_and_preserves_existing_xmp(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = self._candidate(root, "1", "DSC0001", 3)
            second = self._candidate(root, "1", "DSC0002", 4)
            self._seed_existing_xmp(first)
            self._seed_existing_xmp(second)
            ids = iter(("A" * 32, "B" * 32, "C" * 32, "D" * 32))

            subject_lift.write_subject_adjustment(
                first,
                self._adjustment(first, 3, 0.12, 4, -4, 3, 0, -3),
                id_factory=lambda: next(ids),
            )
            subject_lift.write_subject_adjustment(
                second,
                self._adjustment(second, 4, 0.38, 10, -18, 12, -5, -8),
                id_factory=lambda: next(ids),
            )

            first_owned = self._owned_correction(first)
            second_owned = self._owned_correction(second)
            text = first.with_suffix(".xmp").read_text(encoding="utf-8")

        self.assertEqual(first_owned.get(self._crs("LocalExposure2012")), "0.12")
        self.assertEqual(second_owned.get(self._crs("LocalExposure2012")), "0.38")
        self.assertEqual(first_owned.get(self._crs("LocalContrast2012")), "0.04")
        self.assertEqual(second_owned.get(self._crs("LocalHighlights2012")), "-0.18")
        mask = first_owned.find(
            f"{{{rawpy_tools.CRS_NS}}}CorrectionMasks/"
            f"{{{rawpy_tools.RDF_NS}}}Seq/{{{rawpy_tools.RDF_NS}}}li"
        )
        self.assertIsNotNone(mask)
        self.assertEqual(mask.get(self._crs("What")), "Mask/Image")
        self.assertEqual(mask.get(self._crs("MaskSubType")), "1")
        self.assertEqual(mask.get(self._crs("MaskInverted")), "false")
        self.assertNotEqual(
            first_owned.get(self._crs("CorrectionSyncID")),
            second_owned.get(self._crs("CorrectionSyncID")),
        )
        self.assertIn("Manual Dodge", text)
        self.assertIn("+0.42", text)
        self.assertIn("private-value", text)

    def test_reapply_replaces_owned_correction_and_skip_removes_only_owned(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw = self._candidate(root, "1", "DSC0001", 3)
            self._seed_existing_xmp(raw)
            subject_lift.write_subject_adjustment(
                raw,
                self._adjustment(raw, 3, 0.12, 4, -4, 3, 0, -3),
                id_factory=lambda: "A" * 32,
            )
            subject_lift.write_subject_adjustment(
                raw,
                self._adjustment(raw, 3, 0.25, 8, -10, 6, -2, -6),
                id_factory=lambda: "B" * 32,
            )

            corrections = self._corrections(raw)
            owned = [item for item in corrections if item.get(self._crs("CorrectionName")) == subject_lift.CORRECTION_NAME]
            self.assertEqual(len(owned), 1)
            self.assertEqual(owned[0].get(self._crs("LocalExposure2012")), "0.25")

            skip = subject_lift.SubjectAdjustment(
                raw, 3, "skip", 0.0, 0, 0, 0, 0, 0, "already bright"
            )
            subject_lift.write_subject_adjustment(raw, skip)
            corrections = self._corrections(raw)

        self.assertFalse(any(item.get(self._crs("CorrectionName")) == subject_lift.CORRECTION_NAME for item in corrections))
        self.assertTrue(any(item.get(self._crs("CorrectionName")) == "Manual Dodge" for item in corrections))

    def _candidate(self, root: Path, group: str, stem: str, rating: int) -> Path:
        raw_dir = root / "portrait" / group / "raw"
        hif_dir = root / "portrait" / group / "hif"
        raw_dir.mkdir(parents=True, exist_ok=True)
        hif_dir.mkdir(parents=True, exist_ok=True)
        raw = raw_dir / f"{stem}.ARW"
        raw.write_text("raw", encoding="utf-8")
        (hif_dir / f"{stem}.HIF").write_text("hif", encoding="utf-8")
        rawpy_tools.write_rating_xmp_sidecar(raw, rating)
        return raw

    def _adjustment(
        self,
        raw: Path,
        rating: int,
        exposure: float,
        contrast: int,
        highlights: int,
        shadows: int,
        whites: int,
        blacks: int,
    ) -> subject_lift.SubjectAdjustment:
        return subject_lift.SubjectAdjustment(
            raw,
            rating,
            "apply",
            exposure,
            contrast,
            highlights,
            shadows,
            whites,
            blacks,
            "per-image visual review",
        )

    def _crs(self, name: str) -> str:
        return f"{{{rawpy_tools.CRS_NS}}}{name}"

    def _seed_existing_xmp(self, raw: Path) -> None:
        rawpy_tools.write_lr_xmp_sidecar(
            raw,
            {"Exposure2012": "+0.42"},
            rating=rawpy_tools.read_xmp_rating_strict(raw.with_suffix(".xmp")),
        )
        prefix, root, suffix = rawpy_tools._parse_xmp(
            raw.with_suffix(".xmp").read_text(encoding="utf-8")
        )
        description = rawpy_tools._xmp_description(root)
        description.set("{urn:test-private}Marker", "private-value")
        group = ET.SubElement(description, self._crs("MaskGroupBasedCorrections"))
        sequence = ET.SubElement(group, f"{{{rawpy_tools.RDF_NS}}}Seq")
        item = ET.SubElement(sequence, f"{{{rawpy_tools.RDF_NS}}}li")
        ET.SubElement(
            item,
            f"{{{rawpy_tools.RDF_NS}}}Description",
            {
                self._crs("What"): "Correction",
                self._crs("CorrectionName"): "Manual Dodge",
            },
        )
        xml = ET.tostring(root, encoding="unicode", short_empty_elements=True)
        rawpy_tools._atomic_write_text(raw.with_suffix(".xmp"), f"{prefix}{xml}{suffix}")

    def _corrections(self, raw: Path) -> list[ET.Element]:
        _prefix, root, _suffix = rawpy_tools._parse_xmp(
            raw.with_suffix(".xmp").read_text(encoding="utf-8")
        )
        description = rawpy_tools._xmp_description(root)
        group = description.find(self._crs("MaskGroupBasedCorrections"))
        if group is None:
            return []
        sequence = group.find(f"{{{rawpy_tools.RDF_NS}}}Seq")
        if sequence is None:
            return []
        return [
            child
            for item in sequence
            for child in item
            if child.tag == f"{{{rawpy_tools.RDF_NS}}}Description"
        ]

    def _owned_correction(self, raw: Path) -> ET.Element:
        matches = [
            item
            for item in self._corrections(raw)
            if item.get(self._crs("CorrectionName")) == subject_lift.CORRECTION_NAME
        ]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def _row(
        self,
        raw: Path,
        rating: int,
        action: str,
        exposure: str,
        contrast: str,
        highlights: str,
        shadows: str,
        whites: str,
        blacks: str,
        rationale: str,
    ) -> dict[str, str]:
        return {
            "path": raw.as_posix(),
            "rating": str(rating),
            "preview": f"{raw.stem}.jpg",
            "p01": "0.01",
            "p50": "0.25",
            "p95": "0.75",
            "p99": "0.9",
            "p999": "0.98",
            "clip_ratio": "0.001",
            "shadow_ratio": "0.02",
            "action": action,
            "subject_exposure": exposure,
            "subject_contrast": contrast,
            "subject_highlights": highlights,
            "subject_shadows": shadows,
            "subject_whites": whites,
            "subject_blacks": blacks,
            "rationale": rationale,
        }

    def _write_plan(
        self,
        path: Path,
        root: Path,
        rows: list[dict[str, str]],
    ) -> None:
        normalized = []
        for row in rows:
            copied = dict(row)
            copied["path"] = Path(copied["path"]).relative_to(root).as_posix()
            normalized.append(copied)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=subject_lift.PLAN_FIELDS,
                delimiter="\t",
            )
            writer.writeheader()
            writer.writerows(normalized)


if __name__ == "__main__":
    unittest.main()
