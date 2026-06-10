from __future__ import annotations

import argparse
import json
from pathlib import Path

from media_toolkit.workflows import workflow_choices
from media_toolkit.workflow_doctor import inspect_directory


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt status",
        description="Summarize photo directory workflow status.",
    )
    parser.add_argument("directory", type=Path, help="Photo directory to inspect.")
    parser.add_argument(
        "--workflow",
        choices=workflow_choices(include_auto=True),
        default="auto",
        help="Workflow-specific status to report.",
    )
    parser.add_argument(
        "--copy-to",
        type=Path,
        help="Finalize destination to validate when --workflow finalize is used.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def render_status(report) -> str:
    summary = report.summary
    lines = [
        f"Photo status: {report.path}",
        f"status: {report.status}",
        f"stage: {report.inferred_stage}",
        f"workflow: {report.workflow}",
        (
            "counts: "
            f"raw={summary.get('raw', 0)}, hif={summary.get('hif', 0)}, "
            f"xmp={summary.get('xmp', 0)}, exports={summary.get('exports', 0)}, "
            f"loose_raw={summary.get('loose_raw', 0)}, loose_hif={summary.get('loose_hif', 0)}, "
            f"contact_sheets={summary.get('contact_sheets', 0)}"
        ),
        (
            "groups: "
            f"portrait={summary.get('portrait_groups', 0)} "
            f"(raw={summary.get('portrait_raw', 0)}, hif={summary.get('portrait_hif', 0)}), "
            f"panorama={summary.get('panorama_groups', 0)} "
            f"(raw={summary.get('panorama_raw', 0)}, hif={summary.get('panorama_hif', 0)})"
        ),
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
        lines.append("recommendations:")
        lines.extend(f"- {item}" for item in report.recommendations)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = inspect_directory(args.directory, workflow=args.workflow, copy_to=args.copy_to)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_status(report))
    return 0 if report.ok else 1
