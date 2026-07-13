from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit import subject_lift


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt subject-apply",
        description="Apply a reviewed per-image Lightroom Select Subject plan.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory to update")
    parser.add_argument("--plan", required=True, help="Reviewed subject-plan TSV")
    parser.add_argument("--ratings", default=">=3", help="Eligible XMP rating expression")
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without writing XMP")
    return parser.parse_args(argv)


def resolve_plan(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1
    try:
        adjustments = subject_lift.read_reviewed_plan(
            resolve_plan(root, args.plan),
            root,
        )
        pairs = subject_lift.validate_reviewed_plan(root, adjustments, args.ratings)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    for candidate, adjustment in pairs:
        relative = candidate.raw_path.relative_to(root)
        if args.dry_run:
            print(f"DRY-RUN {adjustment.action} {relative}: {adjustment.rationale}")
            continue
        try:
            subject_lift.write_subject_adjustment(candidate.raw_path, adjustment)
        except (OSError, UnicodeError, ValueError) as exc:
            print(f"Error: {relative}: {exc}", file=sys.stderr)
            return 1
        print(f"{adjustment.action.upper()} {relative}")

    action = "Validated" if args.dry_run else "Applied"
    print(f"{action} {len(pairs)} portrait subject-plan row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
