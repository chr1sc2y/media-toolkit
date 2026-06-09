#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
FEATURED_SPEC = importlib.util.spec_from_file_location(
    "extract_featured_raw",
    SCRIPT_DIR / "extract_featured_raw.py",
)
extract_featured_raw = importlib.util.module_from_spec(FEATURED_SPEC)
assert FEATURED_SPEC.loader is not None
FEATURED_SPEC.loader.exec_module(extract_featured_raw)


def finalize_directory(base_dir: Path, *, scene: str) -> bool:
    base_dir = Path(base_dir).expanduser().resolve()
    destination = base_dir / "featured"
    print(f"Finalizing scene: {scene}")
    return extract_featured_raw.process_files(base_dir, destination)


def find_finalize_directories(root: Path) -> list[Path]:
    return extract_featured_raw.find_directories_with_raw(root)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize Lightroom-exported photos by copying matching original HIF previews into the photo directory's featured/ folder.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Photo directory to finalize")
    parser.add_argument(
        "--scene",
        default="general-travel",
        help="Scene category label for reporting and future repo-level style tuning.",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Finalize every subdirectory containing a raw/ folder.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

    if args.recursive:
        bases = find_finalize_directories(root)
        if not bases:
            print("No directories with raw/ found.", file=sys.stderr)
            return 1
    else:
        bases = [root]

    success = True
    for base in bases:
        if not finalize_directory(base, scene=args.scene):
            success = False
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
