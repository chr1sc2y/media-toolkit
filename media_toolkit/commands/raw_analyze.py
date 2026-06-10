from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit import rawpy_tools


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt raw-analyze",
        description="Analyze RAW files with rawpy/LibRaw and write histogram metrics.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory to scan")
    parser.add_argument(
        "--output",
        default="raw_stats.tsv",
        help="TSV output path. Relative paths are written under the shoot directory.",
    )
    parser.add_argument(
        "--ratings",
        help='Only include RAW files whose XMP rating matches an expression such as ">=3".',
    )
    return parser.parse_args(argv)


def resolve_output(root: Path, output: str) -> Path:
    path = Path(output).expanduser()
    if path.is_absolute():
        return path
    return root / path


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

    output = resolve_output(root, args.output)
    stats = []
    errors = 0
    for raw_file in raw_files:
        try:
            stats.append(rawpy_tools.analyze_raw(raw_file))
        except Exception as exc:
            errors += 1
            print(f"ERROR {raw_file}: {exc}", file=sys.stderr)

    rawpy_tools.write_raw_stats_tsv(output, stats, root=root)
    print(f"Analyzed {len(stats)} RAW file(s).")
    print(f"Raw stats: {output}")
    if errors:
        print(f"Skipped {errors} RAW file(s) due to errors.", file=sys.stderr)
        return 1
    return 0
