from __future__ import annotations

import argparse
import json
from pathlib import Path

from media_toolkit.style_learning import (
    learn_style_from_directory,
    render_style_learning_report,
)
from media_toolkit.style_profiles import style_profile_ids


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt learn-style",
        description="Read Lightroom final-pick XMP files and summarize scene style evidence.",
    )
    parser.add_argument("directory", type=Path, help="Photo directory to inspect.")
    parser.add_argument(
        "--scene",
        required=True,
        help="Scene label for the style evidence, such as flower-field or grassland.",
    )
    parser.add_argument(
        "--baseline",
        choices=style_profile_ids(),
        help="Existing scene profile to compare against.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = learn_style_from_directory(
        args.directory,
        scene=args.scene,
        baseline_profile=args.baseline,
    )
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_style_learning_report(report))
    return 0 if report.sample_count else 1
