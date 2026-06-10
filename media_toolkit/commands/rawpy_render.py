from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit import rawpy_tools


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt rawpy-render",
        description="Render selected RAW files into RAW-derived JPEG inputs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory to scan")
    parser.add_argument(
        "--ratings",
        default=">=3",
        help='Only render RAW files whose XMP rating matches an expression such as ">=3".',
    )
    parser.add_argument(
        "--output-dir",
        help=(
            "Override output directory. By default, files are written to codex/rawpy_inputs "
            "beside each root, portrait/<n>, or panorama/<n> RAW folder."
        ),
    )
    parser.add_argument("--quality", type=int, default=96, help="JPEG quality")
    return parser.parse_args(argv)


def default_output_path(root: Path, raw_file: Path) -> Path:
    parent = raw_file.parent
    if parent.name.lower() != "raw":
        return root / "codex" / "rawpy_inputs" / f"{raw_file.stem}.jpg"
    container = parent.parent
    return container / "codex" / "rawpy_inputs" / f"{raw_file.stem}.jpg"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1
    if not 1 <= args.quality <= 100:
        print("Error: --quality must be between 1 and 100.", file=sys.stderr)
        return 2

    try:
        raw_files = rawpy_tools.collect_raw_files(root, rating_filter=args.ratings)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    output_override = Path(args.output_dir).expanduser().resolve() if args.output_dir else None
    errors = 0
    rendered = 0
    for raw_file in raw_files:
        output = (
            output_override / f"{raw_file.stem}.jpg"
            if output_override
            else default_output_path(root, raw_file)
        )
        try:
            rawpy_tools.render_raw_to_jpeg(raw_file, output, quality=args.quality)
        except Exception as exc:
            errors += 1
            print(f"ERROR {raw_file}: {exc}", file=sys.stderr)
            continue
        rendered += 1
        print(f"Rendered {output}")

    print(f"Rendered {rendered} RAW-derived JPEG input(s).")
    if errors:
        print(f"Skipped {errors} RAW file(s) due to errors.", file=sys.stderr)
        return 1
    return 0
