from __future__ import annotations

import argparse
import json
from pathlib import Path

from media_toolkit.workflow_doctor import inspect_directory


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt batch-report",
        description="Print a read-only human summary of a photo batch.",
    )
    parser.add_argument("directory", type=Path, help="Photo directory to summarize.")
    parser.add_argument(
        "--copy-to",
        type=Path,
        help="Optional finalize destination to include finalize readiness.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def render_batch_report(report) -> str:
    summary = report.summary
    total_raw = (
        summary.get("raw", 0)
        + summary.get("portrait_raw", 0)
        + summary.get("panorama_raw", 0)
        + summary.get("loose_raw", 0)
    )
    total_hif = (
        summary.get("hif", 0)
        + summary.get("portrait_hif", 0)
        + summary.get("panorama_hif", 0)
        + summary.get("loose_hif", 0)
    )
    lines = [
        f"Batch report: {report.path}",
        f"status: {report.status}",
        f"stage: {report.inferred_stage}",
        f"total media: raw={total_raw}, hif={total_hif}, xmp={summary.get('xmp', 0)}",
        (
            "root: "
            f"raw={summary.get('raw', 0)}, hif={summary.get('hif', 0)}, "
            f"loose_raw={summary.get('loose_raw', 0)}, loose_hif={summary.get('loose_hif', 0)}"
        ),
        (
            "portrait: "
            f"groups={summary.get('portrait_groups', 0)}, "
            f"raw={summary.get('portrait_raw', 0)}, hif={summary.get('portrait_hif', 0)}"
        ),
        (
            "panorama: "
            f"groups={summary.get('panorama_groups', 0)}, "
            f"raw={summary.get('panorama_raw', 0)}, hif={summary.get('panorama_hif', 0)}"
        ),
        f"outputs: exports={summary.get('exports', 0)}, contact_sheets={summary.get('contact_sheets', 0)}",
    ]
    actionable = [
        finding for finding in report.findings if finding.severity in {"warning", "error"}
    ]
    if actionable:
        lines.append("findings:")
        lines.extend(
            f"- {finding.severity.upper()} {finding.code}: {finding.message}"
            for finding in actionable
        )
    if report.recommendations:
        lines.append("next:")
        lines.extend(f"- {item}" for item in report.recommendations)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workflow = "finalize" if args.copy_to else "auto"
    report = inspect_directory(args.directory, workflow=workflow, copy_to=args.copy_to)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_batch_report(report))
    return 0 if report.ok else 1
