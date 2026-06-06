import argparse
import os
import shlex
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import traverse, compress_image


def normalize_directory_input(raw_input: str) -> Path:
    value = raw_input.strip()
    if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
        value = value[1:-1]
    if "\\" in value:
        try:
            parts = shlex.split(value)
            if parts:
                value = parts[0]
        except ValueError:
            pass
    return Path(value).expanduser().resolve()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert PNG images to JPG, keeping original resolution."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory containing PNG images. If omitted, prompts interactively.",
    )
    return parser.parse_args()


def get_directory(args: argparse.Namespace) -> Path:
    if args.directory:
        return normalize_directory_input(args.directory)
    raw = input("📁 Enter directory path: ").strip()
    return normalize_directory_input(raw)


args = parse_args()
dir = get_directory(args)

if not dir.exists():
    print(f"❌ Error: Directory not found: {dir}")
    sys.exit(1)

if not dir.is_dir():
    print(f"❌ Error: Path is not a directory: {dir}")
    sys.exit(1)

# Convert PNG to JPG, keeping original resolution
traverse(str(dir), ".png", compress_image, "iw:ih", "jpg")
