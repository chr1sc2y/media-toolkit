import csv
import hashlib
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

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

    def test_reviewed_plan_rejects_malformed_rows_and_duplicate_targets(self):
        with TemporaryDirectory() as tmp:
            plan_path = Path(tmp) / "bad-plan.json"
            valid = fill_locations.row_to_json(
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
            )
            for rows, message in (
                ([valid, "truncated"], "row 2 must be an object"),
                ([{key: value for key, value in valid.items() if key != "target_id"}], "missing field"),
                ([valid, dict(valid)], "duplicate target_id"),
            ):
                with self.subTest(message=message):
                    plan_path.write_text(
                        json.dumps({"version": 1, "rows": rows}), encoding="utf-8"
                    )
                    with self.assertRaisesRegex(ValueError, message):
                        fill_locations.read_plan_json(plan_path)

    def test_apply_plan_rejects_invalid_coordinates_before_osascript(self):
        invalid_coordinates = (
            ("NaN", "89.0"),
            ("91", "89.0"),
            ("42.0", "181"),
            ("42.0, do shell script \"touch /tmp/pwned\"", "89.0"),
        )
        for latitude, longitude in invalid_coordinates:
            with self.subTest(latitude=latitude, longitude=longitude):
                row = fill_locations.PlanRow(
                    target_id="m1",
                    target_filename="missing.jpg",
                    target_taken_at="2026-01-01 10:05:00",
                    source_rule="previous closer",
                    source_id="p1",
                    source_filename="prev.jpg",
                    source_taken_at="2026-01-01 10:00:00",
                    delta_minutes=5.0,
                    latitude=latitude,
                    longitude=longitude,
                )
                with patch.object(fill_locations, "run_osascript") as run_osascript:
                    with self.assertRaisesRegex(ValueError, "coordinate"):
                        fill_locations.apply_plan([row])
                run_osascript.assert_not_called()

    def test_apply_plan_cli_rejects_non_object_top_level_without_osascript(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            plan_path = root / "bad-plan.json"
            plan_path.write_text("[]", encoding="utf-8")
            stderr = StringIO()

            with (
                patch.object(fill_locations, "run_osascript") as run_osascript,
                redirect_stdout(StringIO()),
                redirect_stderr(stderr),
            ):
                exit_code = fill_locations.main(
                    [
                        "--apply-plan",
                        str(plan_path),
                        "--work-dir",
                        str(root / "work"),
                        "--output-dir",
                        str(root / "output"),
                    ]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("invalid reviewed plan", stderr.getvalue())
        run_osascript.assert_not_called()

    def test_combined_apply_mode_is_rejected_before_scanning_or_writing(self):
        stderr = StringIO()
        with (
            patch.object(fill_locations, "run_osascript") as run_osascript,
            patch.object(fill_locations, "export_timeline_and_missing") as export_scan,
            redirect_stdout(StringIO()),
            redirect_stderr(stderr),
        ):
            exit_code = fill_locations.main(["--apply"])

        self.assertEqual(exit_code, 2)
        self.assertIn("--apply-plan", stderr.getvalue())
        export_scan.assert_not_called()
        run_osascript.assert_not_called()

    def test_apply_plan_partial_photos_failure_is_audited_and_returns_nonzero(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            work_dir = root / "work"
            output_dir = root / "output"
            plan_path = root / "reviewed.json"
            rows = [
                fill_locations.PlanRow(
                    target_id=f"m{index}",
                    target_filename=f"missing-{index}.jpg",
                    target_taken_at="2026-01-01 10:05:00",
                    source_rule="previous closer",
                    source_id="p1",
                    source_filename="prev.jpg",
                    source_taken_at="2026-01-01 10:00:00",
                    delta_minutes=5.0,
                    latitude="42.0",
                    longitude="89.0",
                )
                for index in (1, 2)
            ]
            fill_locations.write_plan_json(rows, plan_path, "unit test")

            with (
                patch.object(
                    fill_locations,
                    "run_osascript",
                    return_value="applied=1, errors=1\nmissing-2.jpg | m2 | denied",
                ),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                exit_code = fill_locations.main(
                    [
                        "--apply-plan",
                        str(plan_path),
                        "--work-dir",
                        str(work_dir),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            history = fill_locations.read_run_history(
                work_dir / fill_locations.RUN_HISTORY_NAME
            )
            report = (output_dir / fill_locations.HUMAN_REPORT_NAME).read_text(
                encoding="utf-8"
            )

        self.assertEqual(exit_code, 1)
        self.assertEqual(history["runs"][-1]["applied_count"], 1)
        self.assertEqual(history["runs"][-1]["apply_error_count"], 1)
        self.assertIn("partial failure", report)

    def test_apply_plan_rejects_corrupt_history_before_writing_photos(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            work_dir = root / "work"
            work_dir.mkdir()
            plan_path = root / "reviewed.json"
            fill_locations.write_plan_json(
                [
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
                ],
                plan_path,
                "unit test",
            )
            (work_dir / fill_locations.RUN_HISTORY_NAME).write_text(
                "[]", encoding="utf-8"
            )

            with (
                patch.object(fill_locations, "run_osascript") as run_osascript,
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                exit_code = fill_locations.main(
                    [
                        "--apply-plan",
                        str(plan_path),
                        "--work-dir",
                        str(work_dir),
                        "--output-dir",
                        str(root / "output"),
                    ]
                )

        self.assertEqual(exit_code, 2)
        run_osascript.assert_not_called()

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

    def test_failed_refresh_preserves_complete_cache_and_removes_partial_temps(self):
        for failure in (RuntimeError("scan failed"), KeyboardInterrupt()):
            with self.subTest(failure=type(failure).__name__), TemporaryDirectory() as tmp:
                work_dir = Path(tmp)
                timeline = work_dir / "timeline_basic.csv"
                missing = work_dir / "missing_items.csv"
                timeline.write_text("old complete timeline", encoding="utf-8")
                missing.write_text("old complete missing", encoding="utf-8")
                temporary_paths: list[Path] = []

                def fake_build(temp_timeline, temp_missing, *_args):
                    temporary_paths.extend([temp_timeline, temp_missing])
                    temp_timeline.write_text("partial timeline", encoding="utf-8")
                    temp_missing.write_text("partial missing", encoding="utf-8")
                    return "scan script"

                with (
                    patch.object(
                        fill_locations,
                        "build_export_timeline_script",
                        side_effect=fake_build,
                    ),
                    patch.object(
                        fill_locations,
                        "run_osascript",
                        side_effect=failure,
                    ),
                    redirect_stdout(StringIO()),
                    self.assertRaises(type(failure)),
                ):
                    fill_locations.export_timeline_and_missing(
                        work_dir,
                        force=True,
                    )

                self.assertEqual(
                    timeline.read_text(encoding="utf-8"),
                    "old complete timeline",
                )
                self.assertEqual(
                    missing.read_text(encoding="utf-8"),
                    "old complete missing",
                )
                self.assertTrue(temporary_paths)
                self.assertTrue(all(path not in {timeline, missing} for path in temporary_paths))
                self.assertTrue(all(not path.exists() for path in temporary_paths))

    def test_successful_refresh_atomically_promotes_temporary_cache_files(self):
        with TemporaryDirectory() as tmp:
            work_dir = Path(tmp)
            timeline = work_dir / "timeline_basic.csv"
            missing = work_dir / "missing_items.csv"
            temporary_paths: list[Path] = []

            def fake_build(temp_timeline, temp_missing, *_args):
                temporary_paths.extend([temp_timeline, temp_missing])
                temp_timeline.write_text("new complete timeline", encoding="utf-8")
                temp_missing.write_text("new complete missing", encoding="utf-8")
                return "scan script"

            with (
                patch.object(
                    fill_locations,
                    "build_export_timeline_script",
                    side_effect=fake_build,
                ),
                patch.object(
                    fill_locations,
                    "run_osascript",
                    return_value="exported=1, missing=1",
                ),
                redirect_stdout(StringIO()),
            ):
                result_timeline, result_missing, reused = (
                    fill_locations.export_timeline_and_missing(
                        work_dir,
                        force=True,
                    )
                )

            self.assertEqual((result_timeline, result_missing), (timeline, missing))
            self.assertFalse(reused)
            self.assertEqual(timeline.read_text(encoding="utf-8"), "new complete timeline")
            self.assertEqual(missing.read_text(encoding="utf-8"), "new complete missing")
            self.assertTrue(all(path not in {timeline, missing} for path in temporary_paths))
            self.assertTrue(all(not path.exists() for path in temporary_paths))

    def test_plan_and_apply_print_the_same_reviewed_json_sha256(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            work_dir = root / "work"
            output_dir = root / "output"
            work_dir.mkdir()
            timeline = root / "timeline.csv"
            missing = root / "missing.csv"
            self.write_csv(
                timeline,
                ["photos_id", "filename", "taken_at"],
                [
                    {
                        "photos_id": "p1",
                        "filename": "prev.jpg",
                        "taken_at": "2026-01-01 10:00:00",
                    },
                    {
                        "photos_id": "m1",
                        "filename": "missing.jpg",
                        "taken_at": "2026-01-01 10:05:00",
                    },
                ],
            )
            self.write_csv(
                missing,
                ["photos_id", "filename", "taken_at", "location_status"],
                [
                    {
                        "photos_id": "m1",
                        "filename": "missing.jpg",
                        "taken_at": "2026-01-01 10:05:00",
                        "location_status": "missing",
                    }
                ],
            )
            plan_stdout = StringIO()
            with (
                patch.object(
                    fill_locations,
                    "export_timeline_and_missing",
                    return_value=(timeline, missing, False),
                ),
                patch.object(
                    fill_locations,
                    "export_source_locations",
                    return_value={"p1": ("42.0", "89.0")},
                ),
                redirect_stdout(plan_stdout),
            ):
                plan_exit = fill_locations.main(
                    [
                        "--work-dir",
                        str(work_dir),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            plan_path = work_dir / fill_locations.PLAN_JSON_NAME
            digest = hashlib.sha256(plan_path.read_bytes()).hexdigest()
            apply_stdout = StringIO()
            with (
                patch.object(
                    fill_locations,
                    "run_osascript",
                    return_value="applied=1, errors=0",
                ),
                redirect_stdout(apply_stdout),
            ):
                apply_exit = fill_locations.main(
                    [
                        "--apply-plan",
                        str(plan_path),
                        "--work-dir",
                        str(work_dir),
                        "--output-dir",
                        str(output_dir),
                    ]
                )

        self.assertEqual((plan_exit, apply_exit), (0, 0))
        expected = f"Plan SHA-256: {digest}"
        self.assertIn(expected, plan_stdout.getvalue())
        self.assertIn(expected, apply_stdout.getvalue())

    def test_help_says_start_and_end_filter_only_the_generated_plan(self):
        stdout = StringIO()
        with redirect_stdout(stdout), self.assertRaises(SystemExit):
            fill_locations.main(["--help"])

        help_text = stdout.getvalue()
        self.assertIn("generated plan only", help_text)
        self.assertIn("exclusive", help_text)
        self.assertIn("does not bound the Photos scan", help_text)

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
