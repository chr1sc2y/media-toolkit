#!/usr/bin/env python3
"""Compress JPG/JPEG images until they fit under a target byte size."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_MAX_BYTES = 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compress images larger than a size cap with ffmpeg."
    )
    parser.add_argument("photos_dir", type=Path, help="Directory containing images.")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="Maximum allowed size per image in bytes. Defaults to 1 MiB.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list files that would be compressed.",
    )
    return parser.parse_args()


def require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("ffmpeg is required but was not found in PATH.", file=sys.stderr)
        sys.exit(1)
    return ffmpeg


def candidate_settings() -> list[tuple[float, int]]:
    # Lower q:v is better quality. Try quality first, then gentle downscaling.
    qualities = [3, 4, 5, 6, 7, 8, 10, 12]
    scales = [1.0, 0.92, 0.84, 0.76, 0.68, 0.60]
    return [(scale, quality) for scale in scales for quality in qualities]


def ffmpeg_filter(scale: float) -> str | None:
    if scale >= 0.999:
        return None
    return (
        f"scale=w='trunc(iw*{scale}/2)*2':"
        f"h='trunc(ih*{scale}/2)*2':flags=lanczos"
    )


def collect_oversized(photos_dir: Path, max_bytes: int) -> list[Path]:
    return sorted(
        p
        for p in photos_dir.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".jpg", ".jpeg"}
        and p.stat().st_size > max_bytes
        and ".compress-tmp" not in p.parts
    )


def compress_one(ffmpeg: str, image: Path, max_bytes: int) -> tuple[bool, int, int]:
    original_size = image.stat().st_size
    temp_dir = image.parent / ".compress-tmp"
    temp_dir.mkdir(exist_ok=True)

    try:
        for scale, quality in candidate_settings():
            temp = temp_dir / f"{image.stem}.q{quality}.s{int(scale * 100)}{image.suffix}"
            cmd = [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(image),
                "-map_metadata",
                "0",
                "-q:v",
                str(quality),
            ]
            vf = ffmpeg_filter(scale)
            if vf:
                cmd.extend(["-vf", vf])
            cmd.append(str(temp))

            subprocess.run(cmd, check=True)
            new_size = temp.stat().st_size
            if new_size <= max_bytes and new_size < original_size:
                temp.replace(image)
                return True, original_size, new_size
            temp.unlink(missing_ok=True)

        return False, original_size, original_size
    finally:
        for leftover in temp_dir.glob(f"{image.stem}.*{image.suffix}"):
            leftover.unlink(missing_ok=True)
        try:
            temp_dir.rmdir()
        except OSError:
            pass


def main() -> None:
    args = parse_args()
    photos_dir = args.photos_dir.resolve()
    if not photos_dir.exists():
        print(f"Image directory not found: {photos_dir}", file=sys.stderr)
        sys.exit(1)

    oversized = collect_oversized(photos_dir, args.max_bytes)

    if args.dry_run:
        for image in oversized:
            print(f"would compress {image} {image.stat().st_size}")
        print(f"oversized={len(oversized)}")
        return

    ffmpeg = require_ffmpeg()
    changed = 0
    failed: list[Path] = []
    for image in oversized:
        ok, before, after = compress_one(ffmpeg, image, args.max_bytes)
        if ok:
            changed += 1
            print(f"compressed {image} {before} -> {after}")
        else:
            failed.append(image)
            print(f"failed {image} {before}", file=sys.stderr)

    print(f"oversized={len(oversized)} compressed={changed} failed={len(failed)}")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
