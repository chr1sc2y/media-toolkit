from __future__ import annotations

import argparse
import json
from pathlib import Path

from media_toolkit.workflow_doctor import inspect_directory, render_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt doctor",
        description="Inspect a photo directory before running an agent workflow.",
    )
    parser.add_argument("directory", type=Path, help="Photo directory to inspect.")
    parser.add_argument(
        "--workflow",
        choices=("auto", "initial-cull", "finalize", "learn-style"),
        default="auto",
        help="Workflow-specific checks to run.",
    )
    parser.add_argument(
        "--copy-to",
        type=Path,
        help="Finalize destination to validate when --workflow finalize is used.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = inspect_directory(args.directory, workflow=args.workflow, copy_to=args.copy_to)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_report(report))
    return 0 if report.ok else 1
