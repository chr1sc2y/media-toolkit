#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit.final_hif_archive import (
    EXPORT_EXTS,
    HIF_EXTS,
    destination_is_inside_source as _destination_is_inside_source,
    find_directories_with_raw,
    normalize_directory_input as _normalize_directory_input,
    process_files,
)


FEATURED_EXTS = HIF_EXTS


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Legacy compatibility entry point. Prefer `mt finalize`; this command "
            "copies matching original HIF previews selected by Lightroom exports."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/photos --copy-to /path/to/destination
  %(prog)s /path/to/root --copy-to /path/to/destination -r
        """,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help='Target photo directory. In recursive mode, finds subdirs containing "raw".',
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.7",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help='Recursively process directories that contain a "raw" subdirectory.',
    )
    parser.add_argument(
        "--copy-to",
        required=True,
        help="Destination directory for matching original HIF previews. Must be outside the source photo directory.",
    )
    return parser.parse_args(argv)


def get_target_directory(argv: list[str] | None = None) -> tuple[Path, bool, Path]:
    args = parse_args(argv)
    destination_dir = _normalize_directory_input(args.copy_to)
    if args.directory:
        target_dir = _normalize_directory_input(args.directory)
        if not target_dir.exists():
            print(f"Error: Directory '{target_dir}' does not exist.")
            sys.exit(1)
        if not target_dir.is_dir():
            print(f"Error: '{target_dir}' is not a directory.")
            sys.exit(1)
        return target_dir, args.recursive, destination_dir

    print("Interactive mode: Please specify the target directory.")
    while True:
        raw_input = input("Enter the target directory path (or press Enter for current directory): ")
        if not raw_input.strip():
            return Path.cwd(), args.recursive, destination_dir
        target_dir = _normalize_directory_input(raw_input)
        if target_dir.exists() and target_dir.is_dir():
            return target_dir, args.recursive, destination_dir
        print(f"Error: '{target_dir}' does not exist or is not a directory.")


def main(argv: list[str] | None = None) -> int:
    try:
        base_dir, recursive, destination_dir = get_target_directory(argv)
        bases = find_directories_with_raw(base_dir) if recursive else [base_dir]
        if recursive:
            print(f"\n{'='*60}")
            print("RECURSIVE MODE ENABLED")
            print(f"{'='*60}")
            print(f"Root search directory: {base_dir}")
            print(f"Found {len(bases)} directory(ies) containing a 'raw' subdirectory.")
            if not bases:
                print("No directories with 'raw' found. Nothing to do.")
                return 1

        success = True
        for idx, base in enumerate(bases, 1):
            if recursive:
                print(f"\n--- [{idx}/{len(bases)}] {base} ---")
            if not process_files(base, destination_dir):
                success = False
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n\nOperation cancelled by user.")
        return 1
    except Exception as exc:
        print(f"\nUnexpected error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
