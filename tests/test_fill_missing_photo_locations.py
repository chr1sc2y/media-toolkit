import csv
import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fill_missing_photo_locations.py"
SPEC = importlib.util.spec_from_file_location("fill_missing_photo_locations", SCRIPT_PATH)
fill_locations = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = fill_locations
SPEC.loader.exec_module(fill_locations)


class FillMissingPhotoLocationsTest(unittest.TestCase):
    def write_csv(self, path, fieldnames, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_plan_prefers_previous_within_threshold_else_next(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            timeline = root / "timeline.csv"
            missing = root / "missing.csv"
            self.write_csv(
                timeline,
                ["photos_id", "filename", "taken_at"],
                [
                    {"photos_id": "p1", "filename": "prev.jpg", "taken_at": "2026-01-01 10:00:00"},
                    {"photos_id": "m1", "filename": "missing1.jpg", "taken_at": "2026-01-01 10:05:00"},
                    {"photos_id": "m2", "filename": "missing2.jpg", "taken_at": "2026-01-01 11:00:00"},
                    {"photos_id": "n1", "filename": "next.jpg", "taken_at": "2026-01-01 11:30:00"},
                ],
            )
            self.write_csv(
                missing,
                ["photos_id", "filename", "taken_at", "location_status"],
                [
                    {"photos_id": "m1", "filename": "missing1.jpg", "taken_at": "2026-01-01 10:05:00", "location_status": "missing"},
                    {"photos_id": "m2", "filename": "missing2.jpg", "taken_at": "2026-01-01 11:00:00", "location_status": "missing"},
                ],
            )

            plans = fill_locations.build_plan(timeline, missing, 10, False, None, None)

            self.assertEqual(plans[0].source_id, "p1")
            self.assertTrue(plans[0].source_rule.startswith("previous"))
            self.assertEqual(plans[1].source_id, "n1")
            self.assertEqual(plans[1].source_rule, "next fallback")

    def test_plan_can_be_limited_to_time_range(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            timeline = root / "timeline.csv"
            missing = root / "missing.csv"
            self.write_csv(
                timeline,
                ["photos_id", "filename", "taken_at"],
                [
                    {"photos_id": "p1", "filename": "prev.jpg", "taken_at": "2026-01-01 10:00:00"},
                    {"photos_id": "m1", "filename": "missing1.jpg", "taken_at": "2026-01-01 10:05:00"},
                    {"photos_id": "p2", "filename": "prev2.jpg", "taken_at": "2026-02-01 10:00:00"},
                    {"photos_id": "m2", "filename": "missing2.jpg", "taken_at": "2026-02-01 10:03:00"},
                ],
            )
            self.write_csv(
                missing,
                ["photos_id", "filename", "taken_at", "location_status"],
                [
                    {"photos_id": "m1", "filename": "missing1.jpg", "taken_at": "2026-01-01 10:05:00", "location_status": "missing"},
                    {"photos_id": "m2", "filename": "missing2.jpg", "taken_at": "2026-02-01 10:03:00", "location_status": "missing"},
                ],
            )

            plans = fill_locations.build_plan(
                timeline,
                missing,
                10,
                False,
                fill_locations.parse_date_arg("2026-02-01"),
                fill_locations.parse_date_arg("2026-02-02"),
            )

            self.assertEqual([plan.target_id for plan in plans], ["m2"])
            self.assertEqual(plans[0].source_id, "p2")

    def test_format_duration_is_human_readable(self):
        self.assertEqual(fill_locations.format_duration(0.65), "0.65 seconds")
        self.assertEqual(fill_locations.format_duration(75.4), "1 minute 15.40 seconds")
        self.assertEqual(fill_locations.format_duration(3725.0), "1 hour 2 minutes 5.00 seconds")

    def test_summary_includes_functionality_and_run_timing(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "outputs"
            plans = [
                fill_locations.PlanRow(
                    target_id="m1",
                    target_filename="missing.jpg",
                    target_taken_at="2026-01-01 10:05:00",
                    source_rule="previous <= 10 min",
                    source_id="p1",
                    source_filename="prev.jpg",
                    source_taken_at="2026-01-01 10:00:00",
                    delta_minutes=5.0,
                    latitude="42.0",
                    longitude="89.0",
                )
            ]
            timing = fill_locations.RunTiming(
                started_at="2026-06-06 10:00:00",
                finished_at="2026-06-06 10:00:01",
                elapsed_seconds=1.25,
                cache_mode="reused cache",
                applied_result="applied=1",
            )

            _, _, summary_path = fill_locations.write_outputs(plans, output_dir, "", timing)

            summary = summary_path.read_text(encoding="utf-8")
            self.assertIn("What this script does:", summary)
            self.assertIn("Run timing", summary)
            self.assertIn("Started: 2026-06-06 10:00:00", summary)
            self.assertIn("Duration: 1.25 seconds", summary)
            self.assertIn("Cache mode: reused cache", summary)
            self.assertIn("Apply result: applied=1", summary)


if __name__ == "__main__":
    unittest.main()
