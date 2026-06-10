#!/usr/bin/env python3
"""
Fill missing Apple Photos locations from nearby timeline neighbors.

Default mode is dry-run: scan Photos, generate a plan, and write readable CSV/HTML
outputs. Pass --apply to write the planned locations back to Photos.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_WORK_DIR = ROOT / "work" / "photos-location-fill"
DEFAULT_OUTPUT_DIR = ROOT / "outputs"

SCRIPT_FEATURES = [
    "Find Apple Photos media items that have no location.",
    "Build a dry-run CSV/HTML fill plan from nearby located timeline neighbors.",
    "Prefer the previous located item within the threshold, then optionally fall back to the next located item.",
    "Reuse cached Photos timeline exports unless --force-refresh is provided.",
    "Write planned locations back to Photos only when --apply is provided.",
    "Record run timing in stdout and the summary file.",
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
            "- Apply from cached plan data: mt fill-locations --apply",
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


def export_timeline_and_missing(work_dir: Path, force: bool) -> tuple[Path, Path, bool]:
    timeline_path = work_dir / "timeline_basic.csv"
    missing_path = work_dir / "missing_items.csv"
    if not force and timeline_path.exists() and missing_path.exists():
        return timeline_path, missing_path, True

    work_dir.mkdir(parents=True, exist_ok=True)
    script = (
        f'set timelinePath to {applescript_quote(str(timeline_path))}\n'
        f'set missingPath to {applescript_quote(str(missing_path))}\n'
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

tell application "Photos"
  set xs to media items
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
      set dt to my isoDate(date of m)
    on error
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

    set timelineBuffer to timelineBuffer & my csvCell(uid) & "," & my csvCell(fn) & "," & my csvCell(dt) & linefeed
    if isMissing then
      set missingCount to missingCount + 1
      set missingBuffer to missingBuffer & my csvCell(uid) & "," & my csvCell(fn) & "," & my csvCell(dt) & "," & my csvCell("missing") & linefeed
    end if

    set rowCount to rowCount + 1
    if rowCount mod 500 = 0 then
      set tf to open for access POSIX file timelinePath with write permission
      write timelineBuffer to tf starting at eof
      close access tf
      set timelineBuffer to ""

      if missingBuffer is not "" then
        set mf to open for access POSIX file missingPath with write permission
        write missingBuffer to mf starting at eof
        close access mf
        set missingBuffer to ""
      end if
    end if
  end repeat
end tell

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
    print("Scanning Photos timeline and missing locations. This can take several minutes...")
    print(run_osascript(script))
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


def build_plan(
    timeline_path: Path,
    missing_path: Path,
    threshold_minutes: float,
    require_next_within_threshold: bool,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[PlanRow]:
    with missing_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        missing_ids = {row["photos_id"] for row in csv.DictReader(handle)}

    rows: list[dict[str, object]] = []
    with timeline_path.open(newline="", encoding="utf-8", errors="replace") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                {
                    **row,
                    "dt": parse_dt(row["taken_at"]),
                    "is_missing": row["photos_id"] in missing_ids,
                }
            )

    threshold_seconds = threshold_minutes * 60
    plans: list[PlanRow] = []
    for index, row in enumerate(rows):
        if not row["is_missing"]:
            continue
        target_dt = row["dt"]
        if start and (not target_dt or target_dt < start):
            continue
        if end and (not target_dt or target_dt >= end):
            continue

        previous = next((rows[j] for j in range(index - 1, -1, -1) if not rows[j]["is_missing"]), None)
        next_row = next((rows[j] for j in range(index + 1, len(rows)) if not rows[j]["is_missing"]), None)

        source = None
        source_rule = ""
        delta_seconds: float | None = None

        if previous and target_dt and previous["dt"]:
            previous_delta = (target_dt - previous["dt"]).total_seconds()  # type: ignore[operator]
            if 0 <= previous_delta <= threshold_seconds:
                source = previous
                source_rule = f"previous <= {threshold_minutes:g} min"
                delta_seconds = previous_delta

        if source is None and next_row and target_dt and next_row["dt"]:
            next_delta = (next_row["dt"] - target_dt).total_seconds()  # type: ignore[operator]
            if not require_next_within_threshold or next_delta <= threshold_seconds:
                source = next_row
                source_rule = "next fallback"
                delta_seconds = next_delta

        note = ""
        if source is None:
            note = "NO SOURCE FOUND"
        elif source_rule == "next fallback" and delta_seconds and delta_seconds > threshold_seconds:
            note = "next fallback is over threshold"

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


def write_outputs(
    plans: list[PlanRow],
    output_dir: Path,
    suffix: str,
    timing: RunTiming | None = None,
) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"photos_location_fill_plan{suffix}.csv"
    html_path = output_dir / f"photos_location_fill_plan{suffix}.html"
    summary_path = output_dir / f"photos_location_fill_summary{suffix}.txt"

    fields = [
        "target_filename",
        "target_taken_at",
        "source_rule",
        "source_filename",
        "source_taken_at",
        "delta_minutes",
        "new_latitude",
        "new_longitude",
        "target_photos_id",
        "source_photos_id",
        "note",
    ]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in plans:
            writer.writerow(
                {
                    "target_filename": row.target_filename,
                    "target_taken_at": row.target_taken_at,
                    "source_rule": row.source_rule,
                    "source_filename": row.source_filename,
                    "source_taken_at": row.source_taken_at,
                    "delta_minutes": row.delta_minutes if row.delta_minutes is not None else "",
                    "new_latitude": row.latitude,
                    "new_longitude": row.longitude,
                    "target_photos_id": row.target_id,
                    "source_photos_id": row.source_id,
                    "note": row.note,
                }
            )

    html_rows = []
    for index, row in enumerate(plans, 1):
        cls = "warn" if row.note else ""
        html_rows.append(
            "<tr class='{cls}'><td>{index}</td><td>{target_time}</td><td>{target}</td>"
            "<td>{rule}</td><td>{delta}</td><td>{source_time}</td><td>{source}</td>"
            "<td>{lat}, {lon}</td><td>{note}</td></tr>".format(
                cls=cls,
                index=index,
                target_time=html.escape(row.target_taken_at),
                target=html.escape(row.target_filename),
                rule=html.escape(row.source_rule),
                delta=html.escape("" if row.delta_minutes is None else str(row.delta_minutes)),
                source_time=html.escape(row.source_taken_at),
                source=html.escape(row.source_filename),
                lat=html.escape(row.latitude),
                lon=html.escape(row.longitude),
                note=html.escape(row.note),
            )
        )

    planned = sum(1 for row in plans if row.source_id and row.latitude and row.longitude and row.latitude != "ERROR")
    no_source = sum(1 for row in plans if not row.source_id)
    warnings = sum(1 for row in plans if row.note and row.note != "NO SOURCE FOUND")
    html_path.write_text(
        f"""<!doctype html><html><head><meta charset="utf-8"><title>Photos Location Fill Plan</title><style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:28px;background:#fbfbf8;color:#1f2933}}
h1{{font-size:24px;margin:0 0 8px}}p{{color:#52606d}}table{{border-collapse:collapse;width:100%;background:white;border:1px solid #d9e2ec}}
th,td{{padding:8px 10px;border-bottom:1px solid #e4e7eb;text-align:left;font-size:13px;vertical-align:top}}
th{{position:sticky;top:0;background:#f1f5f9}}.warn{{background:#fff7ed}}td:nth-child(2),td:nth-child(6){{white-space:nowrap}}td:nth-child(9){{color:#9a3412}}
</style></head><body><h1>Photos Location Fill Plan</h1>
<p>Missing: {len(plans)} · Planned fills: {planned} · No source: {no_source} · Warnings: {warnings}</p>
<table><thead><tr><th>#</th><th>Target time</th><th>Target file</th><th>Rule</th><th>Delta min</th><th>Source time</th><th>Source file</th><th>New location</th><th>Note</th></tr></thead><tbody>{''.join(html_rows)}</tbody></table>
</body></html>""",
        encoding="utf-8",
    )

    summary_lines = [
        "Photos location fill summary",
        f"Missing items: {len(plans)}",
        f"Planned fills: {planned}",
        f"No source: {no_source}",
        f"Warnings: {warnings}",
        "",
        "What this script does:",
    ]
    summary_lines.extend(f"- {feature}" for feature in SCRIPT_FEATURES)
    if timing:
        summary_lines.extend(
            [
                "",
                "Run timing",
                f"Started: {timing.started_at}",
                f"Finished: {timing.finished_at}",
                f"Duration: {format_duration(timing.elapsed_seconds)}",
                f"Cache mode: {timing.cache_mode}",
            ]
        )
        if timing.applied_result:
            summary_lines.append(f"Apply result: {timing.applied_result.strip()}")
    summary_lines.extend(
        [
            "",
            f"Plan CSV: {csv_path}",
            f"Plan HTML: {html_path}",
            "",
        ]
    )
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")
    return csv_path, html_path, summary_path


def apply_plan(plans: list[PlanRow]) -> str:
    apply_rows = [
        row
        for row in plans
        if row.source_id and row.latitude and row.longitude and row.latitude != "ERROR"
    ]
    if not apply_rows:
        return "applied=0, errors=0"

    items = []
    for row in apply_rows:
        items.append(
            "{"
            + applescript_quote(row.target_id)
            + ", "
            + row.latitude
            + ", "
            + row.longitude
            + ", "
            + applescript_quote(row.target_filename)
            + "}"
        )
    script = (
        "set fillItems to {" + ", ".join(items) + "}\n"
        + r'''
set appliedCount to 0
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
      set errorText to errorText & targetName & " | " & targetId & " | " & errMsg & linefeed
    end try
  end repeat
end tell
return "applied=" & appliedCount & linefeed & errorText
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
    parser.add_argument("--apply", action="store_true", help="write planned locations back to Photos")
    parser.add_argument("--force-refresh", action="store_true", help="rescan Photos instead of reusing cache")
    parser.add_argument("--threshold-minutes", type=float, default=10.0)
    parser.add_argument(
        "--start",
        type=parse_date_arg,
        help="only plan/apply missing items taken at or after this time (YYYY-MM-DD or 'YYYY-MM-DD HH:MM:SS')",
    )
    parser.add_argument(
        "--end",
        type=parse_date_arg,
        help="only plan/apply missing items taken before this time (YYYY-MM-DD or 'YYYY-MM-DD HH:MM:SS')",
    )
    parser.add_argument(
        "--require-next-within-threshold",
        action="store_true",
        help="skip next-photo fallback if the next photo is also outside the threshold",
    )
    parser.add_argument("--work-dir", type=Path, default=DEFAULT_WORK_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--suffix", default="")
    args = parser.parse_args(argv)

    if args.describe:
        print(script_description())
        return 0

    started_at = local_timestamp()
    started = time.perf_counter()
    applied_result = ""

    timeline_path, missing_path, reused_cache = export_timeline_and_missing(args.work_dir, args.force_refresh)
    plans = build_plan(
        timeline_path,
        missing_path,
        args.threshold_minutes,
        args.require_next_within_threshold,
        args.start,
        args.end,
    )
    locations = export_source_locations(plans, args.work_dir)
    for row in plans:
        if row.source_id:
            row.latitude, row.longitude = locations.get(row.source_id, ("", ""))
            if row.latitude == "ERROR":
                row.note = f"SOURCE LOCATION READ ERROR: {row.longitude}"

    if args.apply:
        applied_result = apply_plan(plans)

    elapsed_seconds = time.perf_counter() - started
    timing = RunTiming(
        started_at=started_at,
        finished_at=local_timestamp(),
        elapsed_seconds=elapsed_seconds,
        cache_mode="reused cache" if reused_cache else "refreshed Photos timeline",
        applied_result=applied_result,
    )

    csv_path, html_path, summary_path = write_outputs(plans, args.output_dir, args.suffix, timing)
    print(f"Plan CSV: {csv_path}")
    print(f"Plan HTML: {html_path}")
    print(f"Summary: {summary_path}")

    if args.apply:
        print(applied_result)
    else:
        print("Dry run only. Re-run with --apply to write locations to Photos.")
    print(f"Started: {timing.started_at}")
    print(f"Finished: {timing.finished_at}")
    print(f"Duration: {format_duration(timing.elapsed_seconds)}")
    print(f"Cache mode: {timing.cache_mode}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
