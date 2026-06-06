import argparse
import os
import shlex
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src import compress_drone_video, traverse


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
        description="Compress drone videos to 1080p @ 15Mbps."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory containing videos. If omitted, prompts interactively.",
    )
    return parser.parse_args()


def get_directory(args: argparse.Namespace) -> Path:
    if args.directory:
        return normalize_directory_input(args.directory)
    raw = input("📁 Enter directory path: ").strip()
    return normalize_directory_input(raw)


args = parse_args()
dir = get_directory(args)

# Check if directory exists
if not dir.exists():
    print(f"❌ Error: Directory not found: {dir}")
    print("Please check the path and try again.")
    sys.exit(1)

if not dir.is_dir():
    print(f"❌ Error: Path is not a directory: {dir}")
    sys.exit(1)

# Compress drone videos to 1080p @ 15Mbps (keeps original fps)
# Compressed files are saved to 'compressed/' subdirectory
# Original files remain untouched in their original location
try:
    traverse(str(dir), ".mp4", compress_drone_video, "1920:1080", "15M", None)
    print("\n✅ Processing completed!")
except KeyboardInterrupt:
    print("\n⚠️  Processing interrupted by user.")
except Exception as e:
    print(f"\n❌ An error occurred: {e}")
    print("Some files may have been processed successfully.")
