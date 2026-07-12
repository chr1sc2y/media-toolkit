#!/usr/bin/env python3
"""
Fill missing Apple Photos locations from nearby timeline neighbors.

Default mode is dry-run: scan Photos, generate a reviewed JSON plan and a human
HTML report. Pass --apply-plan to write reviewed locations back to Photos.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import re
import subprocess
import sys
import time
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_DIR = ROOT / "work" / "photos-location-fill"
DEFAULT_OUTPUT_DIR = ROOT / "outputs"
RUN_HISTORY_NAME = "run_history.json"
HUMAN_REPORT_NAME = "photos_location_fill_plan.html"

SCRIPT_FEATURES = [
    "Find Apple Photos media items that have no location.",
    "Build a dry-run HTML report and reviewed JSON plan from nearby located timeline neighbors.",
    "Use a two-pass scan to compare previous and next located timeline neighbors.",
    "Choose the closer eligible previous/next source by timestamp.",
    "Use --scan-start with a lookback window for faster incremental planning.",
    "Reuse cached Photos timeline exports unless --force-refresh is provided.",
    "Write locations back to Photos only from an explicitly reviewed --apply-plan JSON file.",
    "Record run timing in stdout, the HTML report, and the run history JSON.",
]


@dataclass
class RunTiming:
    started_at: str
    finished_at: str
    elapsed_seconds: float
    cache_mode: str
    applied_result: str = ""


def local_timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.2f} seconds"

    whole_seconds = int(seconds)
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    fractional_secs = secs + (seconds - whole_seconds)

    parts = []
    if hours:
        parts.append(f"{hours} hour" + ("" if hours == 1 else "s"))
    if minutes:
        parts.append(f"{minutes} minute" + ("" if minutes == 1 else "s"))
    parts.append(f"{fractional_secs:.2f} seconds")
    return " ".join(parts)


def script_description() -> str:
    lines = ["Apple Photos Missing Location Fill", "", "What this script does:"]
    lines.extend(f"- {feature}" for feature in SCRIPT_FEATURES)
    lines.extend(
        [
            "",
            "Typical runs:",
            "- Dry-run with fresh Photos scan: mt fill-locations --force-refresh",
            "- Incremental dry-run from a date: mt fill-locations --scan-start '2026-04-30 00:00:00' --force-refresh",
            "- Apply reviewed plan data: mt fill-locations --apply-plan work/photos-location-fill/photos_location_fill_plan.json",
        ]
    )
    return "\n".join(lines)


def run_osascript(script: str, timeout: int | None = None) -> str:
    result = subprocess.run(
        ["osascript"],
        input=script,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def applescript_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


COMMON_APPLESCRIPT_HELPERS = r'''
on pad2(n)
  set s to n as text
  if length of s is 1 then return "0" & s
  return s
end pad2

on monthNum(m)
  set ms to {January, February, March, April, May, June, July, August, September, October, November, December}
  repeat with i from 1 to 12
    if m = item i of ms then return i
  end repeat
  return 0
end monthNum

on monthConst(n)
  set ms to {January, February, March, April, May, June, July, August, September, October, November, December}
  return item n of ms
end monthConst

on makeDate(y, mo, da, hh, mi, ss)
  set d to current date
  set year of d to y
  set month of d to my monthConst(mo)
  set day of d to da
  set hours of d to hh
  set minutes of d to mi
  set seconds of d to ss
  return d
end makeDate

on isoDate(d)
  try
    set y to year of d as integer
    set mo to my monthNum(month of d)
    set da to day of d as integer
    set hh to hours of d as integer
    set mi to minutes of d as integer
    set ss to seconds of d as integer
    return (y as text) & "-" & my pad2(mo) & "-" & my pad2(da) & " " & my pad2(hh) & ":" & my pad2(mi) & ":" & my pad2(ss)
  on error
    return ""
  end try
end isoDate

on csvCell(v)
  set s to v as text
  set AppleScript's text item delimiters to "\""
  set parts to text items of s
  set AppleScript's text item delimiters to "\"\""
  set escaped to parts as text
  set AppleScript's text item delimiters to ""
  return "\"" & escaped & "\""
end csvCell
'''


def applescript_make_date(dt: datetime) -> str:
    return f"my makeDate({dt.year}, {dt.month}, {dt.day}, {dt.hour}, {dt.minute}, {dt.second})"


def build_export_timeline_script(
    timeline_path: Path,
    missing_path: Path,
    scan_start: datetime | None = None,
    scan_lookback_hours: float = 24.0,
) -> str:
    if scan_start:
        lookback_start = scan_start - timedelta(hours=scan_lookback_hours)
        scan_preamble = (
            "set scanStartEnabled to true\n"
            f"set scanStartDate to {applescript_make_date(scan_start)}\n"
            f"set scanLookbackDate to {applescript_make_date(lookback_start)}\n"
        )
        photos_query = "set xs to media items whose its date ≥ scanLookbackDate"
    else:
        scan_preamble = (
            "set scanStartEnabled to false\n"
            "set scanStartDate to missing value\n"
            "set scanLookbackDate to missing value\n"
        )
        photos_query = "set xs to media items"

    return (
        f"set timelinePath to {applescript_quote(str(timeline_path))}\n"
        f"set missingPath to {applescript_quote(str(missing_path))}\n"
        + scan_preamble
        + COMMON_APPLESCRIPT_HELPERS
        + r'''
set tf to open for access POSIX file timelinePath with write permission
set eof tf to 0
write "photos_id,filename,taken_at" & linefeed to tf
close access tf

set mf to open for access POSIX file missingPath with write permission
set eof mf to 0
write "photos_id,filename,taken_at,location_status" & linefeed to mf
close access mf

set timelineBuffer to ""
set missingBuffer to ""
set rowCount to 0
set missingCount to 0

with timeout of 3600 seconds
tell application "Photos"
  '''
        + photos_query
        + r'''
  repeat with m in xs
    try
      set uid to id of m as text
    on error
      set uid to ""
    end try
    try
      set fn to filename of m as text
    on error
      set fn to ""
    end try
    try
      set itemDate to date of m
      set dt to my isoDate(itemDate)
    on error
      set itemDate to missing value
      set dt to ""
    end try

    set isMissing to false
    try
      set loc to location of m
      if loc is missing value then
        set isMissing to true
      else
        set locText to loc as text
        if locText is "" or locText contains "missing value" then set isMissing to true
      end if
    on error
      set isMissing to true
    end try

    set shouldWriteTimeline to true
    set shouldWriteMissing to isMissing
    if scanStartEnabled and itemDate < scanStartDate and isMissing then
      set shouldWriteTimeline to false
      set shouldWriteMissing to false
    end if
    if scanStartEnabled and itemDate < scanStartDate and not isMissing then
      set shouldWriteMissing to false
    end if

    if shouldWriteTimeline then
      set timelineBuffer to timelineBuffer & my csvCell(uid) & "," & my csvCell(fn) & "," & my csvCell(dt) & linefeed
      set rowCount to rowCount + 1
    end if
    if shouldWriteMissing then
      set missingCount to missingCount + 1
      set missingBuffer to missingBuffer & my csvCell(uid) & "," & my csvCell(fn) & "," & my csvCell(dt) & "," & my csvCell("missing") & linefeed
    end if

    if rowCount mod 500 = 0 then
      if timelineBuffer is not "" then
        set tf to open for access POSIX file timelinePath with write permission
        write timelineBuffer to tf starting at eof
        close access tf
        set timelineBuffer to ""
      end if

      if missingBuffer is not "" then
        set mf to open for access POSIX file missingPath with write permission
        write missingBuffer to mf starting at eof
        close access mf
        set missingBuffer to ""
      end if
    end if
  end repeat
end tell
end timeout

if timelineBuffer is not "" then
  set tf to open for access POSIX file timelinePath with write permission
  write timelineBuffer to tf starting at eof
  close access tf
end if
if missingBuffer is not "" then
  set mf to open for access POSIX file missingPath with write permission
  write missingBuffer to mf starting at eof
  close access mf
end if

return "exported=" & rowCount & ", missing=" & missingCount
'''
    )


def export_timeline_and_missing(
    work_dir: Path,
    force: bool,
    scan_start: datetime | None = None,
    scan_lookback_hours: float = 24.0,
) -> tuple[Path, Path, bool]:
    timeline_path = work_dir / "timeline_basic.csv"
    missing_path = work_dir / "missing_items.csv"
    if not force and timeline_path.exists() and missing_path.exists():
        return timeline_path, missing_path, True

    work_dir.mkdir(parents=True, exist_ok=True)
    temporary_paths: list[Path] = []
    try:
        for target in (timeline_path, missing_path):
            descriptor, temporary_name = tempfile.mkstemp(
                dir=str(work_dir),
                prefix=f".{target.name}.",
                suffix=".tmp",
            )
            os.close(descriptor)
            temporary_paths.append(Path(temporary_name))

        temporary_timeline, temporary_missing = temporary_paths
        script = build_export_timeline_script(
            temporary_timeline,
            temporary_missing,
            scan_start,
            scan_lookback_hours,
        )
        if scan_start:
            print(
                "Scanning Photos timeline and missing locations from "
                f"{scan_start:%Y-%m-%d %H:%M:%S} with "
                f"{scan_lookback_hours:g}h lookback..."
            )
        else:
            print(
                "Scanning Photos timeline and missing locations. "
                "This can take several minutes..."
            )
        scan_result = run_osascript(script)

        timeline_promoted = False
        try:
            os.replace(temporary_timeline, timeline_path)
            timeline_promoted = True
            os.replace(temporary_missing, missing_path)
        except BaseException:
            if timeline_promoted:
                timeline_path.unlink(missing_ok=True)
                missing_path.unlink(missing_ok=True)
            raise
        print(scan_result)
    finally:
        for temporary_path in temporary_paths:
            temporary_path.unlink(missing_ok=True)
    return timeline_path, missing_path, False


def parse_dt(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def parse_date_arg(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(
        f"expected YYYY-MM-DD or YYYY-MM-DD HH:MM:SS, got {value!r}"
    )


@dataclass
class PlanRow:
    target_id: str
    target_filename: str
    target_taken_at: str
    source_rule: str
    source_id: str
    source_filename: str
    source_taken_at: str
    delta_minutes: float | None
    latitude: str = ""
    longitude: str = ""
    note: str = ""
    previous_source_id: str = ""
    previous_source_filename: str = ""
    previous_source_taken_at: str = ""
    previous_delta_minutes: float | None = None
    next_source_id: str = ""
    next_source_filename: str = ""
    next_source_taken_at: str = ""
    next_delta_minutes: float | None = None


PLAN_JSON_NAME = "photos_location_fill_plan.json"
PLAN_TEXT_FIELDS = (
    "target_id",
    "target_filename",
    "target_taken_at",
    "source_rule",
    "source_id",
    "source_filename",
    "source_taken_at",
    "latitude",
    "longitude",
    "note",
    "previous_source_id",
    "previous_source_filename",
    "previous_source_taken_at",
    "next_source_id",
    "next_source_filename",
    "next_source_taken_at",
)
PLAN_MINUTE_FIELDS = (
    "delta_minutes",
    "previous_delta_minutes",
    "next_delta_minutes",
)
PLAN_ROW_FIELDS = PLAN_TEXT_FIELDS + PLAN_MINUTE_FIELDS


def row_to_json(row: PlanRow) -> dict[str, object]:
    return {
        "target_id": row.target_id,
        "target_filename": row.target_filename,
        "target_taken_at": row.target_taken_at,
        "source_rule": row.source_rule,
        "source_id": row.source_id,
        "source_filename": row.source_filename,
        "source_taken_at": row.source_taken_at,
        "delta_minutes": row.delta_minutes,
        "latitude": row.latitude,
        "longitude": row.longitude,
        "note": row.note,
        "previous_source_id": row.previous_source_id,
        "previous_source_filename": row.previous_source_filename,
        "previous_source_taken_at": row.previous_source_taken_at,
        "previous_delta_minutes": row.previous_delta_minutes,
        "next_source_id": row.next_source_id,
        "next_source_filename": row.next_source_filename,
        "next_source_taken_at": row.next_source_taken_at,
        "next_delta_minutes": row.next_delta_minutes,
    }


def row_from_json(data: dict[str, object], *, row_number: int | None = None) -> PlanRow:
    context = f"plan row {row_number}" if row_number is not None else "plan row"
    missing = [key for key in PLAN_ROW_FIELDS if key not in data]
    if missing:
        raise ValueError(f"{context} is missing field(s): {', '.join(missing)}")

    def text(key: str) -> str:
        value = data[key]
        if not isinstance(value, str):
            raise ValueError(f"{context} field {key} must be a string")
        return value

    def minutes(key: str) -> float | None:
        value = data[key]
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{context} field {key} must be a finite number or null")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"{context} field {key} must be a finite number or null")
        return number

    row = PlanRow(
        target_id=text("target_id"),
        target_filename=text("target_filename"),
        target_taken_at=text("target_taken_at"),
        source_rule=text("source_rule"),
        source_id=text("source_id"),
        source_filename=text("source_filename"),
        source_taken_at=text("source_taken_at"),
        delta_minutes=minutes("delta_minutes"),
        latitude=text("latitude"),
        longitude=text("longitude"),
        note=text("note"),
        previous_source_id=text("previous_source_id"),
        previous_source_filename=text("previous_source_filename"),
        previous_source_taken_at=text("previous_source_taken_at"),
        previous_delta_minutes=minutes("previous_delta_minutes"),
        next_source_id=text("next_source_id"),
        next_source_filename=text("next_source_filename"),
        next_source_taken_at=text("next_source_taken_at"),
        next_delta_minutes=minutes("next_delta_minutes"),
    )
    _validate_plan_row(row, context=context)
    return row


def _normalized_coordinates(
    row: PlanRow,
    *,
    context: str,
) -> tuple[str, str] | None:
    if not row.source_id:
        if row.latitude or row.longitude:
            raise ValueError(f"{context} has coordinates without a source_id")
        return None
    if row.latitude == "ERROR":
        if not row.longitude:
            raise ValueError(f"{context} has an empty source-location error")
        return None
    if not row.latitude or not row.longitude:
        raise ValueError(f"{context} has incomplete coordinates")
    try:
        latitude = float(row.latitude)
        longitude = float(row.longitude)
    except ValueError as exc:
        raise ValueError(f"{context} has invalid coordinate text") from exc
    if not math.isfinite(latitude) or not math.isfinite(longitude):
        raise ValueError(f"{context} has non-finite coordinates")
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError(f"{context} has out-of-range coordinates")
    return (format(latitude, ".15g"), format(longitude, ".15g"))


def _validate_plan_row(row: PlanRow, *, context: str) -> None:
    if not row.target_id:
        raise ValueError(f"{context} has an empty target_id")
    if not row.target_filename:
        raise ValueError(f"{context} has an empty target_filename")
    _normalized_coordinates(row, context=context)


def write_plan_json(plans: list[PlanRow], plan_path: Path, source: str) -> Path:
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "generated_at": local_timestamp(),
        "source": source,
        "rows": [row_to_json(row) for row in plans],
    }
    _atomic_write_text(
        plan_path,
        json.dumps(payload, indent=2, ensure_ascii=False),
    )
    return plan_path


def _plans_from_payload(payload: object, plan_path: Path) -> list[PlanRow]:
    if not isinstance(payload, dict):
        raise ValueError(f"plan top level must be an object: {plan_path}")
    if payload.get("version") != 1:
        raise ValueError(f"unsupported plan version in {plan_path}")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"plan has no rows list: {plan_path}")
    plans: list[PlanRow] = []
    target_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"plan row {row_number} must be an object")
        plan = row_from_json(row, row_number=row_number)
        if plan.target_id in target_ids:
            raise ValueError(f"plan row {row_number} has duplicate target_id: {plan.target_id}")
        target_ids.add(plan.target_id)
        plans.append(plan)
    return plans


def read_plan_json_with_sha256(plan_path: Path) -> tuple[list[PlanRow], str]:
    data = plan_path.read_bytes()
    payload = json.loads(data.decode("utf-8"))
    return _plans_from_payload(payload, plan_path), hashlib.sha256(data).hexdigest()


def read_plan_json(plan_path: Path) -> list[PlanRow]:
    plans, _sha256 = read_plan_json_with_sha256(plan_path)
    return plans


def plan_counts(plans: list[PlanRow]) -> dict[str, int | float | None]:
    planned = sum(1 for row in plans if row.source_id and row.latitude and row.longitude and row.latitude != "ERROR")
    no_source = sum(1 for row in plans if not row.source_id)
    warnings = sum(1 for row in plans if row.note and row.note != "NO SOURCE FOUND")
    previous_sources = sum(1 for row in plans if row.source_rule.startswith("previous"))
    next_sources = sum(1 for row in plans if row.source_rule.startswith("next"))
    deltas = [row.delta_minutes for row in plans if row.delta_minutes is not None]
    return {
        "missing_items": len(plans),
        "planned_fills": planned,
        "no_source": no_source,
        "warnings": warnings,
        "previous_sources": previous_sources,
        "next_sources": next_sources,
        "max_delta_minutes": max(deltas) if deltas else None,
    }


def plan_examples(plans: list[PlanRow], limit: int = 8) -> list[dict[str, object]]:
    rows = plans[:limit]
    warning_rows = [row for row in plans if row.note and row not in rows]
    combined = rows + warning_rows[: max(0, limit - len(rows))]
    return [
        {
            "filename": row.target_filename,
            "taken_at": row.target_taken_at,
            "source_filename": row.source_filename,
            "source_taken_at": row.source_taken_at,
            "source_rule": row.source_rule,
            "delta_minutes": row.delta_minutes,
            "note": row.note,
        }
        for row in combined[:limit]
    ]


def parse_apply_counts(applied_result: str) -> tuple[int, int]:
    for line in applied_result.splitlines():
        if line.startswith("applied="):
            try:
                match = re.fullmatch(
                    r"applied=(\d+)(?:,\s*errors=(\d+))?",
                    line.strip(),
                )
                if match is None:
                    return (0, 1)
                return (int(match.group(1)), int(match.group(2) or 0))
            except ValueError:
                return (0, 1)
    return (0, 1) if applied_result.strip() else (0, 0)


def parse_applied_count(applied_result: str) -> int:
    return parse_apply_counts(applied_result)[0]


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _ensure_directory_writable(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path),
        prefix=".media-toolkit-write-check.",
    )
    os.close(descriptor)
    Path(temporary_name).unlink()


def read_run_history(history_path: Path) -> dict[str, object]:
    if not history_path.exists():
        return {"version": 1, "runs": []}
    payload = json.loads(history_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"unsupported run history format: {history_path}")
    if payload.get("version") != 1 or not isinstance(payload.get("runs"), list):
        raise ValueError(f"unsupported run history format: {history_path}")
    return payload


def append_run_history(
    history_path: Path,
    plans: list[PlanRow],
    timing: RunTiming,
    mode: str,
    human_report_path: Path,
    plan_json_path: Path | None,
) -> Path:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history = read_run_history(history_path)
    counts = plan_counts(plans)
    applied_count, apply_error_count = parse_apply_counts(timing.applied_result)
    run = {
        "started_at": timing.started_at,
        "finished_at": timing.finished_at,
        "duration_seconds": round(timing.elapsed_seconds, 2),
        "duration": format_duration(timing.elapsed_seconds),
        "cache_mode": timing.cache_mode,
        "mode": mode,
        "applied": bool(timing.applied_result),
        "applied_count": applied_count,
        "apply_error_count": apply_error_count,
        "apply_result": timing.applied_result.strip(),
        "human_report_path": str(human_report_path),
        "plan_json_path": str(plan_json_path) if plan_json_path else "",
        **counts,
        "examples": plan_examples(plans),
    }
    history["runs"].append(run)  # type: ignore[index]
    _atomic_write_text(
        history_path,
        json.dumps(history, indent=2, ensure_ascii=False),
    )
    return history_path


def build_plan(
    timeline_path: Path,
    missing_path: Path,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[PlanRow]:
    with missing_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        missing_ids = {row["photos_id"] for row in csv.DictReader(handle)}

    rows: list[dict[str, object]] = []
    with timeline_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for original_index, row in enumerate(csv.DictReader(handle)):
            rows.append(
                {
                    **row,
                    "dt": parse_dt(row["taken_at"]),
                    "is_missing": row["photos_id"] in missing_ids,
                    "original_index": original_index,
                }
            )
    rows.sort(key=lambda row: (row["dt"] or datetime.max, row["original_index"]))  # type: ignore[operator]

    previous_located: list[dict[str, object] | None] = []
    last_located: dict[str, object] | None = None
    for row in rows:
        previous_located.append(last_located)
        if not row["is_missing"]:
            last_located = row

    next_located: list[dict[str, object] | None] = [None] * len(rows)
    next_seen: dict[str, object] | None = None
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        next_located[index] = next_seen
        if not row["is_missing"]:
            next_seen = row

    plans: list[PlanRow] = []
    for index, row in enumerate(rows):
        if not row["is_missing"]:
            continue
        target_dt = row["dt"]
        if start and (not target_dt or target_dt < start):
            continue
        if end and (not target_dt or target_dt >= end):
            continue

        previous = previous_located[index]
        next_row = next_located[index]

        source = None
        source_rule = ""
        delta_seconds: float | None = None
        previous_delta: float | None = None
        next_delta: float | None = None
        candidates: list[tuple[float, dict[str, object], str]] = []

        if previous and target_dt and previous["dt"]:
            previous_delta = (target_dt - previous["dt"]).total_seconds()  # type: ignore[operator]
            if 0 <= previous_delta:
                candidates.append((previous_delta, previous, "previous closer"))

        if next_row and target_dt and next_row["dt"]:
            next_delta = (next_row["dt"] - target_dt).total_seconds()  # type: ignore[operator]
            if 0 <= next_delta:
                candidates.append((next_delta, next_row, "next closer"))

        if candidates:
            delta_seconds, source, source_rule = min(candidates, key=lambda item: item[0])

        note = ""
        if source is None:
            note = "NO SOURCE FOUND"

        plans.append(
            PlanRow(
                target_id=str(row["photos_id"]),
                target_filename=str(row["filename"]),
                target_taken_at=str(row["taken_at"]),
                source_rule=source_rule,
                source_id=str(source["photos_id"]) if source else "",
                source_filename=str(source["filename"]) if source else "",
                source_taken_at=str(source["taken_at"]) if source else "",
                delta_minutes=round(delta_seconds / 60, 1) if delta_seconds is not None else None,
                note=note,
                previous_source_id=str(previous["photos_id"]) if previous else "",
                previous_source_filename=str(previous["filename"]) if previous else "",
                previous_source_taken_at=str(previous["taken_at"]) if previous else "",
                previous_delta_minutes=round(previous_delta / 60, 1) if previous_delta is not None else None,
                next_source_id=str(next_row["photos_id"]) if next_row else "",
                next_source_filename=str(next_row["filename"]) if next_row else "",
                next_source_taken_at=str(next_row["taken_at"]) if next_row else "",
                next_delta_minutes=round(next_delta / 60, 1) if next_delta is not None else None,
            )
        )

    return plans


def export_source_locations(plans: list[PlanRow], work_dir: Path) -> dict[str, tuple[str, str]]:
    source_ids = sorted({row.source_id for row in plans if row.source_id})
    if not source_ids:
        return {}

    ids_literal = "{" + ", ".join(applescript_quote(source_id) for source_id in source_ids) + "}"
    out_path = work_dir / "source_locations.csv"
    script = (
        f"set sourceIds to {ids_literal}\n"
        f"set outPath to {applescript_quote(str(out_path))}\n"
        + COMMON_APPLESCRIPT_HELPERS
        + r'''
set csvText to "source_id,latitude,longitude" & linefeed
tell application "Photos"
  repeat with sid in sourceIds
    set sourceId to sid as text
    try
      set loc to location of media item id sourceId
      set latVal to item 1 of loc as text
      set lonVal to item 2 of loc as text
      set csvText to csvText & my csvCell(sourceId) & "," & my csvCell(latVal) & "," & my csvCell(lonVal) & linefeed
    on error errMsg
      set csvText to csvText & my csvCell(sourceId) & "," & my csvCell("ERROR") & "," & my csvCell(errMsg) & linefeed
    end try
  end repeat
end tell
set f to open for access POSIX file outPath with write permission
set eof f to 0
write csvText to f as «class utf8»
close access f
return "sources=" & (count of sourceIds as text)
'''
    )
    print(run_osascript(script))

    locations: dict[str, tuple[str, str]] = {}
    with out_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            locations[row["source_id"]] = (row["latitude"], row["longitude"])
    return locations


def write_history_report(history_path: Path, output_dir: Path, suffix: str = "") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_path = output_dir / (f"photos_location_fill_plan{suffix}.html" if suffix else HUMAN_REPORT_NAME)
    history = read_run_history(history_path)
    rows = history.get("runs", [])
    html_rows = []
    for index, run in enumerate(rows, 1):
        examples = ", ".join(example.get("filename", "") for example in run.get("examples", [])[:5])
        apply_errors = int(run.get("apply_error_count", 0) or 0)
        if run.get("applied") and apply_errors:
            status = (
                f"partial failure: applied {run.get('applied_count', 0)}, "
                f"errors {apply_errors}"
            )
        elif run.get("applied"):
            status = f"applied {run.get('applied_count', 0)}"
        else:
            status = "planned only"
        cls = "warn" if run.get("warnings", 0) or apply_errors else ""
        html_rows.append(
            "<tr class='{cls}'><td>{index}</td><td>{started}</td><td>{mode}</td>"
            "<td>{duration}</td><td>{missing}</td><td>{planned}</td><td>{warnings}</td>"
            "<td>{max_delta}</td><td>{status}</td><td>{examples}</td><td>{cache}</td></tr>".format(
                cls=cls,
                index=index,
                started=html.escape(str(run.get("started_at", ""))),
                mode=html.escape(str(run.get("mode", ""))),
                duration=html.escape(str(run.get("duration", ""))),
                missing=html.escape(str(run.get("missing_items", ""))),
                planned=html.escape(str(run.get("planned_fills", ""))),
                warnings=html.escape(str(run.get("warnings", ""))),
                max_delta=html.escape(str(run.get("max_delta_minutes", ""))),
                status=html.escape(status),
                examples=html.escape(examples),
                cache=html.escape(str(run.get("cache_mode", ""))),
            )
        )

    last_updated = local_timestamp()
    html_path.write_text(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>Photos Location Fill Runs</title><style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:28px;background:#fbfbf8;color:#1f2933}}
h1{{font-size:24px;margin:0 0 8px}}p{{color:#52606d}}table{{border-collapse:collapse;width:100%;background:white;border:1px solid #d9e2ec}}
th,td{{padding:8px 10px;border-bottom:1px solid #e4e7eb;text-align:left;font-size:13px;vertical-align:top}}
th{{position:sticky;top:0;background:#f1f5f9}}.warn{{background:#fff7ed}}td:nth-child(2),td:nth-child(4){{white-space:nowrap}}
</style></head><body><h1>Photos Location Fill Runs</h1>
<p>One row per completed plan/apply run. Last updated: {html.escape(last_updated)}.</p>
	<table><thead><tr><th>#</th><th>Started</th><th>Mode</th><th>Duration</th><th>Missing</th><th>Planned</th><th>Warnings</th><th>Max Delta (min)</th><th>Status</th><th>Examples</th><th>Cache</th></tr></thead><tbody>{''.join(html_rows)}</tbody></table>
</body></html>""",
        encoding="utf-8",
    )
    return html_path


def apply_plan(plans: list[PlanRow]) -> str:
    apply_rows: list[tuple[PlanRow, tuple[str, str]]] = []
    target_ids: set[str] = set()
    for row_number, row in enumerate(plans, start=1):
        context = f"plan row {row_number}"
        _validate_plan_row(row, context=context)
        if row.target_id in target_ids:
            raise ValueError(f"{context} has duplicate target_id: {row.target_id}")
        target_ids.add(row.target_id)
        coordinates = _normalized_coordinates(row, context=context)
        if coordinates is not None:
            apply_rows.append((row, coordinates))
    if not apply_rows:
        return "applied=0, errors=0"

    items = []
    for row, (latitude, longitude) in apply_rows:
        items.append(
            "{"
            + applescript_quote(row.target_id)
            + ", "
            + latitude
            + ", "
            + longitude
            + ", "
            + applescript_quote(row.target_filename)
            + "}"
        )
    script = (
        "set fillItems to {" + ", ".join(items) + "}\n"
        + r'''
set appliedCount to 0
set errorCount to 0
set errorText to ""

tell application "Photos"
  repeat with fillItem in fillItems
    set targetId to item 1 of fillItem
    set latVal to item 2 of fillItem
    set lonVal to item 3 of fillItem
    set targetName to item 4 of fillItem
    try
      set location of media item id targetId to {latVal, lonVal}
      set appliedCount to appliedCount + 1
    on error errMsg
      set errorCount to errorCount + 1
      set errorText to errorText & targetName & " | " & targetId & " | " & errMsg & linefeed
    end try
  end repeat
end tell
return "applied=" & appliedCount & ", errors=" & errorCount & linefeed & errorText
'''
    )
    return run_osascript(script)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mt fill-locations",
        description="Plan or apply missing-location fixes in Apple Photos.",
        epilog=script_description(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--describe", action="store_true", help="print what this script does and exit")
    parser.add_argument(
        "--apply",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--apply-plan",
        type=Path,
        help="write locations from a reviewed JSON plan without rescanning Photos",
    )
    parser.add_argument("--force-refresh", action="store_true", help="rescan Photos instead of reusing cache")
    parser.add_argument(
        "--scan-start",
        type=parse_date_arg,
        help="only scan Photos items at or after this time, plus a small lookback window for location context",
    )
    parser.add_argument(
        "--scan-lookback-hours",
        type=float,
        default=24.0,
        help="hours before --scan-start to scan for previous located context",
    )
    parser.add_argument(
        "--start",
        type=parse_date_arg,
        help=(
            "filter generated plan only at or after this inclusive time; "
            "does not bound the Photos scan"
        ),
    )
    parser.add_argument(
        "--end",
        type=parse_date_arg,
        help=(
            "filter generated plan only before this exclusive time; "
            "does not bound the Photos scan"
        ),
    )
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--suffix", default="")
    args = parser.parse_args(argv)

    if args.describe:
        print(script_description())
        return 0
    if args.apply:
        print(
            "Error: combined --apply mode was removed. Run a plan, review its "
            "JSON, then use --apply-plan <reviewed-plan.json>.",
            file=sys.stderr,
        )
        return 2

    started_at = local_timestamp()
    started = time.perf_counter()
    applied_result = ""
    plan_json_path: Path | None = args.apply_plan
    mode = "apply-plan" if args.apply_plan else "plan"
    history_path = args.work_dir / RUN_HISTORY_NAME

    if args.apply_plan:
        try:
            plans, plan_sha256 = read_plan_json_with_sha256(args.apply_plan)
            print(f"Plan SHA-256: {plan_sha256}")
            read_run_history(history_path)
            _ensure_directory_writable(args.work_dir)
            _ensure_directory_writable(args.output_dir)
            applied_result = apply_plan(plans)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            print(f"Error: invalid reviewed plan: {exc}", file=sys.stderr)
            return 2
        reused_cache = True
    else:
        timeline_path, missing_path, reused_cache = export_timeline_and_missing(
            args.work_dir,
            args.force_refresh,
            args.scan_start,
            args.scan_lookback_hours,
        )
        plan_start = args.start or args.scan_start
        plans = build_plan(
            timeline_path,
            missing_path,
            plan_start,
            args.end,
        )
        locations = export_source_locations(plans, args.work_dir)
        for row in plans:
            if row.source_id:
                row.latitude, row.longitude = locations.get(row.source_id, ("", ""))
                if row.latitude == "ERROR":
                    row.note = f"SOURCE LOCATION READ ERROR: {row.longitude}"
        source_label = (
            f"Photos timeline scan from {args.scan_start:%Y-%m-%d %H:%M:%S}"
            if args.scan_start
            else "Photos timeline scan"
        )
        plan_json_path = write_plan_json(plans, args.work_dir / PLAN_JSON_NAME, source_label)
        print(f"Plan JSON: {plan_json_path}")
        plan_sha256 = hashlib.sha256(plan_json_path.read_bytes()).hexdigest()
        print(f"Plan SHA-256: {plan_sha256}")

    elapsed_seconds = time.perf_counter() - started
    timing = RunTiming(
        started_at=started_at,
        finished_at=local_timestamp(),
        elapsed_seconds=elapsed_seconds,
        cache_mode="reviewed plan" if args.apply_plan else "reused cache" if reused_cache else "refreshed Photos timeline",
        applied_result=applied_result,
    )

    html_path = args.output_dir / (f"photos_location_fill_plan{args.suffix}.html" if args.suffix else HUMAN_REPORT_NAME)
    history_path = append_run_history(
        history_path,
        plans,
        timing,
        mode=mode,
        human_report_path=html_path,
        plan_json_path=plan_json_path,
    )
    html_path = write_history_report(history_path, args.output_dir, args.suffix)
    print(f"Human report: {html_path}")
    print(f"Run history: {history_path}")

    if args.apply_plan:
        print(applied_result)
    else:
        print(
            "Dry run only. Review the HTML report, then re-run with "
            "--apply-plan <plan-json> to write locations to Photos."
        )
    print(f"Started: {timing.started_at}")
    print(f"Finished: {timing.finished_at}")
    print(f"Duration: {format_duration(timing.elapsed_seconds)}")
    print(f"Cache mode: {timing.cache_mode}")

    _applied_count, apply_error_count = parse_apply_counts(applied_result)
    return 1 if args.apply_plan and apply_error_count else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
