import csv
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from media_toolkit.commands import fill_locations


class FillMissingPhotoLocationsTest(unittest.TestCase):
    def write_csv(self, path, fieldnames, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def test_plan_chooses_closer_previous_or_next(self):
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

            plans = fill_locations.build_plan(timeline, missing, None, None)

            self.assertEqual(plans[0].source_id, "p1")
            self.assertTrue(plans[0].source_rule.startswith("previous"))
            self.assertEqual(plans[1].source_id, "n1")
            self.assertEqual(plans[1].source_rule, "next closer")
            self.assertEqual(plans[1].note, "")

    def test_plan_chooses_closer_next_candidate_over_previous(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            timeline = root / "timeline.csv"
            missing = root / "missing.csv"
            self.write_csv(
                timeline,
                ["photos_id", "filename", "taken_at"],
                [
                    {"photos_id": "p1", "filename": "prev.jpg", "taken_at": "2026-01-01 10:00:00"},
                    {"photos_id": "m1", "filename": "missing.jpg", "taken_at": "2026-01-01 10:09:00"},
                    {"photos_id": "n1", "filename": "next.jpg", "taken_at": "2026-01-01 10:10:00"},
                ],
            )
            self.write_csv(
                missing,
                ["photos_id", "filename", "taken_at", "location_status"],
                [
                    {"photos_id": "m1", "filename": "missing.jpg", "taken_at": "2026-01-01 10:09:00", "location_status": "missing"},
                ],
            )

            plans = fill_locations.build_plan(timeline, missing, None, None)

            self.assertEqual(plans[0].source_id, "n1")
            self.assertEqual(plans[0].source_rule, "next closer")
            self.assertEqual(plans[0].previous_source_id, "p1")
            self.assertEqual(plans[0].next_source_id, "n1")

    def test_plan_chooses_closer_previous_without_threshold_warning(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            timeline = root / "timeline.csv"
            missing = root / "missing.csv"
            self.write_csv(
                timeline,
                ["photos_id", "filename", "taken_at"],
                [
                    {"photos_id": "p1", "filename": "prev.jpg", "taken_at": "2026-01-01 10:21:00"},
                    {"photos_id": "m1", "filename": "missing.jpg", "taken_at": "2026-01-01 10:37:00"},
                    {"photos_id": "n1", "filename": "next.mov", "taken_at": "2026-01-01 12:10:00"},
                ],
            )
            self.write_csv(
                missing,
                ["photos_id", "filename", "taken_at", "location_status"],
                [
                    {"photos_id": "m1", "filename": "missing.jpg", "taken_at": "2026-01-01 10:37:00", "location_status": "missing"},
                ],
            )

            plans = fill_locations.build_plan(timeline, missing, None, None)

            self.assertEqual(plans[0].source_id, "p1")
            self.assertEqual(plans[0].source_rule, "previous closer")
            self.assertEqual(plans[0].previous_source_id, "p1")
            self.assertEqual(plans[0].next_source_id, "n1")
            self.assertEqual(plans[0].note, "")

    def test_plan_json_round_trips_rows_for_reviewed_apply(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "reviewed-plan.json"
            plans = [
                fill_locations.PlanRow(
                    target_id="m1",
                    target_filename="missing.jpg",
                    target_taken_at="2026-01-01 10:05:00",
                    source_rule="previous closer",
                    source_id="p1",
                    source_filename="prev.jpg",
                    source_taken_at="2026-01-01 10:00:00",
                    delta_minutes=5.0,
                    latitude="42.0",
                    longitude="89.0",
                    previous_source_id="p1",
                    previous_delta_minutes=5.0,
                    next_source_id="n1",
                    next_delta_minutes=8.0,
                )
            ]

            fill_locations.write_plan_json(plans, plan_path, "unit test")
            loaded = fill_locations.read_plan_json(plan_path)

            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].target_id, "m1")
            self.assertEqual(loaded[0].source_id, "p1")
            self.assertEqual(loaded[0].latitude, "42.0")
            self.assertEqual(loaded[0].previous_source_id, "p1")
            self.assertEqual(loaded[0].next_source_id, "n1")

    def test_incremental_export_script_filters_by_scan_start_with_lookback(self):
        script = fill_locations.build_export_timeline_script(
            Path("/tmp/timeline.csv"),
            Path("/tmp/missing.csv"),
            datetime(2026, 4, 30, 0, 0, 0),
            48,
        )

        self.assertIn("set scanStartEnabled to true", script)
        self.assertIn("with timeout of 3600 seconds", script)
        self.assertIn("set scanStartDate to my makeDate(2026, 4, 30, 0, 0, 0)", script)
        self.assertIn("set scanLookbackDate to my makeDate(2026, 4, 28, 0, 0, 0)", script)
        self.assertIn("set xs to media items whose its date ≥ scanLookbackDate", script)
        self.assertIn("if scanStartEnabled and itemDate < scanStartDate and isMissing then", script)

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
                fill_locations.parse_date_arg("2026-02-01"),
                fill_locations.parse_date_arg("2026-02-02"),
            )

            self.assertEqual([plan.target_id for plan in plans], ["m2"])
            self.assertEqual(plans[0].source_id, "p2")

    def test_format_duration_is_human_readable(self):
        self.assertEqual(fill_locations.format_duration(0.65), "0.65 seconds")
        self.assertEqual(fill_locations.format_duration(75.4), "1 minute 15.40 seconds")
        self.assertEqual(fill_locations.format_duration(3725.0), "1 hour 2 minutes 5.00 seconds")

    def test_history_report_renders_one_table_row_per_run(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            output_dir = root / "outputs"
            history_path = root / "run_history.json"
            plans = [
                fill_locations.PlanRow(
                    target_id="m1",
                    target_filename="missing.jpg",
                    target_taken_at="2026-01-01 10:05:00",
                    source_rule="previous closer",
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

            fill_locations.append_run_history(
                history_path,
                plans,
                timing,
                mode="apply-plan",
                human_report_path=output_dir / fill_locations.HUMAN_REPORT_NAME,
                plan_json_path=Path("/tmp/plan.json"),
            )
            html_path = fill_locations.write_history_report(history_path, output_dir)

            report = html_path.read_text(encoding="utf-8")
            self.assertIn("Photos Location Fill Runs", report)
            self.assertIn("<table", report)
            self.assertIn("2026-06-06 10:00:00", report)
            self.assertIn("1.25 seconds", report)
            self.assertIn("reused cache", report)
            self.assertIn("applied 1", report)
            self.assertIn("5.0", report)
            self.assertIn("missing.jpg", report)
            self.assertNotIn("Target file", report)
            self.assertEqual(html_path.name, fill_locations.HUMAN_REPORT_NAME)
            self.assertFalse((output_dir / "photos_location_fill_plan.csv").exists())
            self.assertFalse((output_dir / "photos_location_fill_summary.txt").exists())

    def test_run_history_appends_plan_and_apply_metrics(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            history_path = root / "run_history.json"
            plans = [
                fill_locations.PlanRow(
                    target_id="m1",
                    target_filename="missing.jpg",
                    target_taken_at="2026-01-01 10:05:00",
                    source_rule="previous closer",
                    source_id="p1",
                    source_filename="prev.jpg",
                    source_taken_at="2026-01-01 10:00:00",
                    delta_minutes=5.0,
                    latitude="42.0",
                    longitude="89.0",
                ),
                fill_locations.PlanRow(
                    target_id="m2",
                    target_filename="warn.jpg",
                    target_taken_at="2026-01-01 11:05:00",
                    source_rule="next fallback",
                    source_id="n1",
                    source_filename="next.jpg",
                    source_taken_at="2026-01-01 12:05:00",
                    delta_minutes=60.0,
                    latitude="43.0",
                    longitude="90.0",
                    note="SOURCE LOCATION READ ERROR: denied",
                ),
            ]
            timing = fill_locations.RunTiming(
                started_at="2026-06-06 10:00:00",
                finished_at="2026-06-06 10:00:12",
                elapsed_seconds=12.0,
                cache_mode="reviewed plan",
                applied_result="applied=2",
            )

            fill_locations.append_run_history(
                history_path,
                plans,
                timing,
                mode="apply-plan",
                human_report_path=Path("/tmp/report.html"),
                plan_json_path=Path("/tmp/plan.json"),
            )
            fill_locations.append_run_history(
                history_path,
                plans[:1],
                timing,
                mode="plan",
                human_report_path=Path("/tmp/report.html"),
                plan_json_path=Path("/tmp/plan.json"),
            )

            history = fill_locations.read_run_history(history_path)
            self.assertEqual(history["version"], 1)
            self.assertEqual(len(history["runs"]), 2)
            self.assertEqual(history["runs"][0]["mode"], "apply-plan")
            self.assertTrue(history["runs"][0]["applied"])
            self.assertEqual(history["runs"][0]["applied_count"], 2)
            self.assertEqual(history["runs"][0]["missing_items"], 2)
            self.assertEqual(history["runs"][0]["warnings"], 1)
            self.assertEqual(history["runs"][0]["max_delta_minutes"], 60.0)
            self.assertEqual(history["runs"][0]["examples"][0]["filename"], "missing.jpg")


if __name__ == "__main__":
    unittest.main()
