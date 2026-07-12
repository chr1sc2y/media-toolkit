from __future__ import annotations

import argparse
import json
from pathlib import Path

from media_toolkit.preflight import preflight_finalize, render_preflight_report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt preflight-run",
        description="Run a read-only workflow preflight sequence.",
    )
    subparsers = parser.add_subparsers(dest="workflow", required=True)

    finalize_parser = subparsers.add_parser(
        "finalize",
        help="Run status, doctor, and finalize dry-run checks.",
    )
    finalize_parser.add_argument("directory", type=Path, help="Photo directory to inspect.")
    finalize_parser.add_argument(
        "--copy-to",
        type=Path,
        required=True,
        help="External destination directory to validate.",
    )
    finalize_parser.add_argument(
        "--scene",
        default="general-travel",
        help="Scene category used for the finalize dry-run.",
    )
    finalize_parser.add_argument(
        "--photos-album",
        default="Sony",
        help="Photos album used for the finalize dry-run import plan.",
    )
    finalize_parser.add_argument(
        "--hif-only",
        "--no-photos",
        dest="hif_only",
        action="store_true",
        help="Validate HIF-only finalization without Photos import.",
    )
    finalize_parser.add_argument(
        "--recursive",
        "-r",
        dest="recursive",
        action="store_true",
        default=True,
        help="Validate every subdirectory containing a raw/ folder.",
    )
    finalize_parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Validate only the provided directory.",
    )
    finalize_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.workflow == "finalize":
        report = preflight_finalize(
            args.directory,
            copy_to=args.copy_to,
            scene=args.scene,
            hif_only=args.hif_only,
            photos_album=args.photos_album,
            recursive=args.recursive,
        )
    else:
        raise AssertionError(f"unsupported workflow: {args.workflow}")

    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_preflight_report(report))
    return 0 if report.ok else 1
