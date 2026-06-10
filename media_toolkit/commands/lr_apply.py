from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit import rawpy_tools
from media_toolkit.style_profiles import (
    lr_plan_styles_by_xmp_style,
    style_profile_ids,
)


PLAN_STYLE_BY_XMP_STYLE = lr_plan_styles_by_xmp_style()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt lr-apply",
        description="Write Lightroom rough-edit XMP fields from RAW evidence and style profiles.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory to scan")
    parser.add_argument(
        "--ratings",
        default=">=3",
        help='Only edit RAW files whose XMP rating matches an expression such as ">=3".',
    )
    parser.add_argument(
        "--style",
        choices=style_profile_ids(),
        default="travel-rich",
        help="Scene style profile to write into candidate XMP sidecars.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the RAW files that would be updated without writing XMP.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

    try:
        raw_files = rawpy_tools.collect_raw_files(root, rating_filter=args.ratings)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    stats = []
    ratings: dict[str, int | None] = {}
    errors = 0
    for raw_file in raw_files:
        ratings[raw_file.stem] = rawpy_tools.read_xmp_rating(raw_file.with_suffix(".xmp"))
        try:
            stats.append(rawpy_tools.analyze_raw(raw_file))
        except Exception as exc:
            errors += 1
            print(f"ERROR {raw_file}: {exc}", file=sys.stderr)

    plan_style = PLAN_STYLE_BY_XMP_STYLE[args.style]
    plans = rawpy_tools.build_lr_plans(stats, ratings, style=plan_style)
    for plan in plans:
        try:
            rel_path = plan.path.resolve().relative_to(root)
        except ValueError:
            rel_path = plan.path
        if args.dry_run:
            print(f"Would write {rel_path}")
            continue
        fields = rawpy_tools.build_lr_xmp_fields(plan, style=args.style)
        rawpy_tools.write_lr_xmp_sidecar(plan.path, fields, rating=plan.rating)
        print(f"Wrote {rel_path.with_suffix('.xmp')}")

    action = "Planned" if args.dry_run else "Wrote"
    print(f"{action} {len(plans)} Lightroom XMP sidecar(s) with style {args.style}.")
    if errors:
        print(f"Skipped {errors} RAW file(s) due to errors.", file=sys.stderr)
        return 1
    return 0
