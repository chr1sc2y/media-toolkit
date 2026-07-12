from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit.legacy_processing import compress_drone_video, traverse
from media_toolkit.path_input import normalize_directory_input


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt drone",
        description="Compress drone videos to 1080p @ 15Mbps.",
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory containing videos. If omitted, prompts interactively.",
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

    try:
        succeeded, failed = traverse(
            str(directory),
            ".mp4",
            compress_drone_video,
            "1920:1080",
            "15M",
            None,
        )
        if failed:
            print(
                f"\nProcessing completed with failures: "
                f"succeeded={succeeded} failed={failed}.",
                file=sys.stderr,
            )
            return 1
        print("\nProcessing completed.")
        return 0
    except KeyboardInterrupt:
        print("\nProcessing interrupted by user.", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"\nAn error occurred: {exc}", file=sys.stderr)
        print("Some files may have been processed successfully.", file=sys.stderr)
        return 1
