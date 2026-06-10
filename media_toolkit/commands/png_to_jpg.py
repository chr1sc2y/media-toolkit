from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit.legacy_processing import compress_image, traverse
from media_toolkit.path_input import normalize_directory_input


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt png-to-jpg",
        description="Convert PNG images to JPG, keeping original resolution.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory containing PNG images. If omitted, prompts interactively.",
    )
    return parser.parse_args(argv)


def get_directory(args: argparse.Namespace) -> Path:
    if args.directory:
        return normalize_directory_input(args.directory)
    raw = input("Enter directory path: ").strip()
    return normalize_directory_input(raw)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    directory = get_directory(args)
    if not directory.exists():
        print(f"Error: Directory not found: {directory}", file=sys.stderr)
        return 1
    if not directory.is_dir():
        print(f"Error: Path is not a directory: {directory}", file=sys.stderr)
        return 1
    traverse(str(directory), ".png", compress_image, "iw:ih", "jpg")
    return 0
