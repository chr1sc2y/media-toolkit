#!/usr/bin/env python3
"""
Generate contact sheet thumbnails for fast photo review.

Examples:
    python scripts/generate_contact_sheets.py /path/to/photos
    python scripts/generate_contact_sheets.py /path/to/photos --export-only --exclude-dir PixCake
    python scripts/generate_contact_sheets.py /path/to/photos --output /tmp/review --cols 5 --rows 4
"""

import argparse
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IMAGE_EXTS = {
    ".avif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".hif",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
SIPS_INPUT_EXTS = {".hif"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Create numbered contact sheets from images.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Directory to scan recursively")
    parser.add_argument(
        "--output",
        default="contact_sheets",
        help="Output directory for sheets and manifest",
    )
    parser.add_argument(
        "--export-only",
        action="store_true",
        help='Only include images below directories named "export" (case-insensitive)',
    )
    parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude, case-insensitive. Can be passed more than once.",
    )
    parser.add_argument("--cols", type=int, default=5, help="Thumbnail columns per sheet")
    parser.add_argument("--rows", type=int, default=4, help="Thumbnail rows per sheet")
    parser.add_argument("--thumb-width", type=int, default=360, help="Thumbnail tile width")
    parser.add_argument("--thumb-height", type=int, default=320, help="Thumbnail tile height")
    parser.add_argument("--label-height", type=int, default=52, help="Reserved label area height")
    parser.add_argument("--quality", type=int, default=3, help="FFmpeg JPEG quality, 1 is best")
    return parser.parse_args()


def require_ffmpeg():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        print("Error: ffmpeg is required but was not found in PATH.", file=sys.stderr)
        sys.exit(1)
    return ffmpeg


def is_under_export(path: Path) -> bool:
    return any(part.lower() == "export" for part in path.parts)


def is_excluded(path: Path, excluded_names: set[str]) -> bool:
    return any(part.lower() in excluded_names for part in path.parts)


def collect_images(root: Path, export_only: bool, exclude_dirs: list[str]) -> list[Path]:
    excluded_names = {name.lower() for name in exclude_dirs}
    images = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in IMAGE_EXTS:
            continue
        if export_only and not is_under_export(path):
            continue
        if excluded_names and is_excluded(path, excluded_names):
            continue
        images.append(path)

    return sorted(images, key=lambda p: str(p).lower())


def escape_drawtext(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "\\'")
        .replace("%", "\\%")
        .replace("\n", " ")
    )


def shorten_label(value: str, max_len: int = 34) -> str:
    if len(value) <= max_len:
        return value
    stem = Path(value).stem
    suffix = Path(value).suffix
    room = max_len - len(suffix) - 1
    if room <= 8:
        return value[: max_len - 1] + "..."
    return stem[:room] + "..." + suffix


def run_ffmpeg(cmd: list[str]) -> None:
    result = subprocess.run(cmd, text=True, capture_output=True)
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(stderr or "ffmpeg failed")


def run_sips(source: Path, destination: Path) -> None:
    result = subprocess.run(
        ["sips", "-s", "format", "jpeg", str(source), "--out", str(destination)],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(stderr or "sips failed")


def prepare_input_image(image: Path, tile_path: Path) -> Path:
    if image.suffix.lower() not in SIPS_INPUT_EXTS:
        return image

    converted = tile_path.with_name(f"{tile_path.stem}_input.jpg")
    run_sips(image, converted)
    return converted


def render_tile(
    ffmpeg: str,
    image: Path,
    tile_path: Path,
    index: int,
    tile_width: int,
    tile_height: int,
    label_height: int,
    quality: int,
) -> None:
    image_height = tile_height - label_height
    if image_height < 80:
        raise ValueError("--thumb-height must leave at least 80px for the image area")

    input_image = prepare_input_image(image, tile_path)
    label = escape_drawtext(f"{index:03d} {shorten_label(image.name)}")
    scale = (
        f"scale=w='if(gt(a,{tile_width}/{image_height}),{tile_width},-2)':"
        f"h='if(gt(a,{tile_width}/{image_height}),-2,{image_height})'"
    )
    filters = [
        scale,
        f"pad={tile_width}:{tile_height}:({tile_width}-iw)/2:({image_height}-ih)/2:color=0x202020",
        f"drawbox=x=0:y={image_height}:w={tile_width}:h={label_height}:color=black@0.85:t=fill",
        f"drawtext=text='{label}':fontcolor=white:fontsize=18:x=12:y={image_height + 10}",
    ]
    run_ffmpeg(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_image),
            "-vf",
            ",".join(filters),
            "-frames:v",
            "1",
            "-q:v",
            str(quality),
            str(tile_path),
        ]
    )


def render_blank(
    ffmpeg: str,
    tile_path: Path,
    tile_width: int,
    tile_height: int,
    quality: int,
) -> None:
    run_ffmpeg(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x111111:s={tile_width}x{tile_height}:d=0.1",
            "-frames:v",
            "1",
            "-q:v",
            str(quality),
            str(tile_path),
        ]
    )


def render_sheet(
    ffmpeg: str,
    temp_dir: Path,
    sheet_path: Path,
    cols: int,
    rows: int,
    tile_width: int,
    tile_height: int,
    quality: int,
) -> None:
    inputs = []
    labels = []
    layout = []
    padding = 8
    margin = 12

    for index in range(1, cols * rows + 1):
        inputs.extend(["-i", str(temp_dir / f"tile_{index:04d}.jpg")])
        labels.append(f"[{index - 1}:v]")
        col = (index - 1) % cols
        row = (index - 1) // cols
        layout.append(f"{col * (tile_width + padding)}_{row * (tile_height + padding)}")

    width = cols * tile_width + (cols - 1) * padding + 2 * margin
    height = rows * tile_height + (rows - 1) * padding + 2 * margin
    filter_complex = (
        f"{''.join(labels)}"
        f"xstack=inputs={cols * rows}:layout={'|'.join(layout)}:fill=white,"
        f"pad={width}:{height}:{margin}:{margin}:white,"
        f"setsar=1,crop={width}:{height}:0:0[out]"
    )

    run_ffmpeg(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[out]",
            "-frames:v",
            "1",
            "-q:v",
            str(quality),
            str(sheet_path),
        ]
    )


def write_manifest(output_dir: Path, root: Path, images: list[Path], cols: int, rows: int) -> None:
    per_sheet = cols * rows
    manifest = output_dir / "manifest.tsv"
    with manifest.open("w", encoding="utf-8") as fh:
        fh.write("sheet\ttile\tindex\tfile\tpath\n")
        for idx, image in enumerate(images, start=1):
            sheet = math.ceil(idx / per_sheet)
            tile = ((idx - 1) % per_sheet) + 1
            try:
                rel = image.relative_to(root)
            except ValueError:
                rel = image
            fh.write(f"{sheet:03d}\t{tile:02d}\t{idx:03d}\t{image.name}\t{rel}\n")


def generate_contact_sheets(args) -> int:
    ffmpeg = require_ffmpeg()
    root = Path(args.directory).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1
    if args.cols < 1 or args.rows < 1:
        print("Error: --cols and --rows must be positive.", file=sys.stderr)
        return 1
    if args.label_height >= args.thumb_height:
        print("Error: --label-height must be smaller than --thumb-height.", file=sys.stderr)
        return 1

    images = collect_images(root, args.export_only, args.exclude_dir)
    if not images:
        print("No images found.")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(output_dir, root, images, args.cols, args.rows)

    per_sheet = args.cols * args.rows
    total_sheets = math.ceil(len(images) / per_sheet)
    print(f"Found {len(images)} images.")
    print(f"Writing {total_sheets} contact sheet(s) to: {output_dir}")

    for sheet_index in range(total_sheets):
        chunk = images[sheet_index * per_sheet : (sheet_index + 1) * per_sheet]
        sheet_path = output_dir / f"contact_sheet_{sheet_index + 1:03d}.jpg"

        with tempfile.TemporaryDirectory(prefix="contact-sheet-") as temp:
            temp_dir = Path(temp)
            for pos, image in enumerate(chunk, start=1):
                tile_path = temp_dir / f"tile_{pos:04d}.jpg"
                global_index = sheet_index * per_sheet + pos
                render_tile(
                    ffmpeg,
                    image,
                    tile_path,
                    global_index,
                    args.thumb_width,
                    args.thumb_height,
                    args.label_height,
                    args.quality,
                )

            for pos in range(len(chunk) + 1, per_sheet + 1):
                tile_path = temp_dir / f"tile_{pos:04d}.jpg"
                render_blank(ffmpeg, tile_path, args.thumb_width, args.thumb_height, args.quality)

            render_sheet(
                ffmpeg,
                temp_dir,
                sheet_path,
                args.cols,
                args.rows,
                args.thumb_width,
                args.thumb_height,
                args.quality,
            )
            print(f"  {sheet_path.name}: {len(chunk)} image(s)")

    print(f"Manifest: {output_dir / 'manifest.tsv'}")
    return 0


if __name__ == "__main__":
    sys.exit(generate_contact_sheets(parse_args()))
