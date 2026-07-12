#!/usr/bin/env python3
from __future__ import annotations
"""
Generate contact sheet thumbnails for fast photo review.

Examples:
    mt contact-sheet /path/to/photos
    mt contact-sheet /path/to/photos --export-only --exclude-dir PixCake
    mt contact-sheet /path/to/photos --output /tmp/review --cols 5 --rows 4
"""

import argparse
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

IMAGE_EXTS = {
    ".avif",
    ".heic",
    ".jpeg",
    ".jpg",
    ".hif",
    ".heif",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}
HIF_EXTS = {".hif", ".heif", ".heic"}
TRANSCODE_INPUT_EXTS = HIF_EXTS
FFMPEG_FULL_PATHS = (
    Path("/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"),
    Path("/usr/local/opt/ffmpeg-full/bin/ffmpeg"),
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt contact-sheet",
        description="Create contact sheets from images.",
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
        "--hif-only",
        action="store_true",
        help='Only include HIF files below directories named "hif" (case-insensitive).',
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
    parser.add_argument(
        "--show-index",
        action="store_true",
        help="Prefix each tile label with its manifest index.",
    )
    parser.add_argument(
        "--final-overview",
        help="Also combine generated sheet pages into this final JPG path.",
    )
    parser.add_argument(
        "--section-by-numbered-dir",
        action="store_true",
        help="Keep numbered child directories in separate final-overview sections.",
    )
    parser.add_argument(
        "--section-prefix",
        help='Section title prefix for numbered dirs, such as "Portrait" or "Panorama".',
    )
    return parser.parse_args(argv)


class SheetPage:
    def __init__(self, images: list[Path], title: str | None = None):
        self.images = images
        self.title = title


def require_ffmpeg():
    candidates = [
        *(str(path) for path in FFMPEG_FULL_PATHS if path.exists() and os.access(path, os.X_OK)),
        *(candidate for candidate in [shutil.which("ffmpeg")] if candidate),
    ]
    for ffmpeg in candidates:
        if ffmpeg_has_filter(ffmpeg, "drawtext"):
            return ffmpeg
    if candidates:
        print(
            "Error: ffmpeg was found, but it does not support the drawtext filter. "
            "Install ffmpeg-full or another ffmpeg build with libfreetype.",
            file=sys.stderr,
        )
    else:
        print("Error: ffmpeg is required but was not found in PATH.", file=sys.stderr)
    sys.exit(1)


def ffmpeg_has_filter(ffmpeg: str, filter_name: str) -> bool:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-filters"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        return False
    return any(line.split()[1:2] == [filter_name] for line in result.stdout.splitlines())


def is_under_export(path: Path) -> bool:
    return any(part.lower() == "export" for part in path.parts)


def is_excluded(path: Path, excluded_names: set[str]) -> bool:
    return any(part.lower() in excluded_names for part in path.parts)


def is_under_hif(path: Path) -> bool:
    return any(part.lower() == "hif" for part in path.parts)


def collect_images(
    root: Path,
    export_only: bool,
    exclude_dirs: list[str],
    hif_only: bool = False,
    *,
    exclude_roots: Iterable[Path] = (),
    exclude_files: Iterable[Path] = (),
) -> list[Path]:
    excluded_names = {name.lower() for name in exclude_dirs}
    excluded_root_paths = tuple(Path(path).resolve() for path in exclude_roots)
    excluded_file_paths = {Path(path).resolve() for path in exclude_files}
    images = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in excluded_file_paths or any(
            resolved == excluded_root or resolved.is_relative_to(excluded_root)
            for excluded_root in excluded_root_paths
        ):
            continue
        if hif_only:
            if path.suffix.lower() not in HIF_EXTS:
                continue
            if not is_under_hif(path):
                continue
            if excluded_names and is_excluded(path, excluded_names):
                continue
            images.append(path)
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


def format_label(image: Path, index: int, show_index: bool) -> str:
    name = shorten_label(image.name)
    if show_index:
        return f"{index:03d} {name}"
    return name


def chunk_images(images: list[Path], per_sheet: int) -> list[list[Path]]:
    return [images[index : index + per_sheet] for index in range(0, len(images), per_sheet)]


def numbered_section_key(root: Path, image: Path) -> str | None:
    try:
        parts = image.relative_to(root).parts
    except ValueError:
        parts = image.parts
    for part in parts[:-1]:
        if part.isdigit():
            return part
    return None


def build_sheet_plan(
    images: list[Path],
    root: Path,
    per_sheet: int,
    section_by_numbered_dir: bool,
    section_prefix: str | None,
) -> list[SheetPage]:
    if per_sheet < 1:
        raise ValueError("per_sheet must be positive")
    if not section_by_numbered_dir:
        return [SheetPage(chunk) for chunk in chunk_images(images, per_sheet)]

    sections: list[tuple[str | None, list[Path]]] = []
    section_index: dict[str | None, int] = {}
    for image in images:
        key = numbered_section_key(root, image)
        if key not in section_index:
            section_index[key] = len(sections)
            sections.append((key, []))
        sections[section_index[key]][1].append(image)

    pages: list[SheetPage] = []
    for key, section_images in sections:
        title = None
        if key is not None:
            title = f"{section_prefix or 'Section'} {key}"
        for index, chunk in enumerate(chunk_images(section_images, per_sheet)):
            pages.append(SheetPage(chunk, title if index == 0 else None))
    return pages


def load_font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def combine_contact_sheets(
    sheets: list[tuple[Path, str | None]],
    output_path: Path,
    quality: int = 92,
) -> None:
    if not sheets:
        raise ValueError("sheets must not be empty")

    images = [Image.open(path).convert("RGB") for path, _title in sheets]
    try:
        header_height = 82
        width = max(image.width for image in images)
        height = sum(image.height for image in images)
        height += sum(header_height for _path, title in sheets if title)
        canvas = Image.new("RGB", (width, height), "white")
        draw = ImageDraw.Draw(canvas)
        font = load_font(42)
        y = 0
        for image, (_path, title) in zip(images, sheets):
            if title:
                draw.rectangle((0, y, width, y + header_height), fill=(245, 245, 245))
                draw.text((24, y + 20), title, fill=(20, 20, 20), font=font)
                y += header_height
            canvas.paste(image, (0, y))
            y += image.height
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output_path, quality=quality)
    finally:
        for image in images:
            image.close()


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


def render_ffmpeg_input_image(ffmpeg: str, source: Path, destination: Path) -> None:
    run_ffmpeg(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(destination),
        ]
    )


def prepare_input_image(ffmpeg: str, image: Path, tile_path: Path) -> Path:
    if image.suffix.lower() not in TRANSCODE_INPUT_EXTS:
        return image

    converted = tile_path.with_name(f"{tile_path.stem}_input.jpg")
    try:
        render_ffmpeg_input_image(ffmpeg, image, converted)
    except RuntimeError:
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
    show_index: bool = False,
) -> None:
    image_height = tile_height - label_height
    if image_height < 80:
        raise ValueError("--thumb-height must leave at least 80px for the image area")

    label = escape_drawtext(format_label(image, index, show_index))
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

    def render_with(input_image: Path) -> None:
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

    try:
        input_image = prepare_input_image(ffmpeg, image, tile_path)
        render_with(input_image)
    except RuntimeError:
        if image.suffix.lower() not in TRANSCODE_INPUT_EXTS:
            raise
        converted = tile_path.with_name(f"{tile_path.stem}_input.jpg")
        if not converted.exists():
            run_sips(image, converted)
        render_with(converted)


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
    tile_count: int,
    tile_width: int,
    tile_height: int,
    quality: int,
) -> None:
    if tile_count < 1:
        raise ValueError("tile_count must be positive")

    inputs = []
    labels = []
    layout = []
    padding = 8
    margin = 12
    rows = math.ceil(tile_count / cols)

    for index in range(1, tile_count + 1):
        inputs.extend(["-i", str(temp_dir / f"tile_{index:04d}.jpg")])
        labels.append(f"[{index - 1}:v]")
        col = (index - 1) % cols
        row = (index - 1) // cols
        layout.append(f"{col * (tile_width + padding)}_{row * (tile_height + padding)}")

    used_cols = min(cols, tile_count)
    width = used_cols * tile_width + (used_cols - 1) * padding + 2 * margin
    height = rows * tile_height + (rows - 1) * padding + 2 * margin

    if tile_count == 1:
        run_ffmpeg(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(temp_dir / "tile_0001.jpg"),
                "-filter_complex",
                f"[0:v]pad={width}:{height}:{margin}:{margin}:white,setsar=1,crop={width}:{height}:0:0[out]",
                "-map",
                "[out]",
                "-frames:v",
                "1",
                "-q:v",
                str(quality),
                str(sheet_path),
            ]
        )
        return

    filter_complex = (
        f"{''.join(labels)}"
        f"xstack=inputs={tile_count}:layout={'|'.join(layout)}:fill=white,"
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
    final_overview = (
        Path(args.final_overview).expanduser().resolve()
        if args.final_overview
        else None
    )

    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1
    if args.cols < 1 or args.rows < 1:
        print("Error: --cols and --rows must be positive.", file=sys.stderr)
        return 1
    if args.label_height >= args.thumb_height:
        print("Error: --label-height must be smaller than --thumb-height.", file=sys.stderr)
        return 1
    if args.section_by_numbered_dir and not args.final_overview:
        print(
            "Error: --section-by-numbered-dir requires --final-overview.",
            file=sys.stderr,
        )
        return 1

    images = collect_images(
        root,
        args.export_only,
        args.exclude_dir,
        args.hif_only,
        exclude_roots=[output_dir],
        exclude_files=[final_overview] if final_overview is not None else [],
    )
    if not images:
        print("No images found.")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    write_manifest(output_dir, root, images, args.cols, args.rows)

    per_sheet = args.cols * args.rows
    sheet_plan = build_sheet_plan(
        images,
        root,
        per_sheet,
        args.section_by_numbered_dir,
        args.section_prefix,
    )
    total_sheets = len(sheet_plan)
    print(f"Found {len(images)} images.")
    print(f"Writing {total_sheets} contact sheet(s) to: {output_dir}")

    rendered_sheets: list[tuple[Path, str | None]] = []
    global_index = 0
    for sheet_index, page in enumerate(sheet_plan):
        chunk = page.images
        sheet_path = output_dir / f"contact_sheet_{sheet_index + 1:03d}.jpg"

        with tempfile.TemporaryDirectory(prefix="contact-sheet-") as temp:
            temp_dir = Path(temp)
            for pos, image in enumerate(chunk, start=1):
                tile_path = temp_dir / f"tile_{pos:04d}.jpg"
                global_index += 1
                render_tile(
                    ffmpeg,
                    image,
                    tile_path,
                    global_index,
                    args.thumb_width,
                    args.thumb_height,
                    args.label_height,
                    args.quality,
                    args.show_index,
                )

            render_sheet(
                ffmpeg,
                temp_dir,
                sheet_path,
                args.cols,
                len(chunk),
                args.thumb_width,
                args.thumb_height,
                args.quality,
            )
            print(f"  {sheet_path.name}: {len(chunk)} image(s)")
            rendered_sheets.append((sheet_path, page.title))

    if args.final_overview:
        assert final_overview is not None
        combine_contact_sheets(rendered_sheets, final_overview)
        print(f"Final overview: {final_overview}")

    print(f"Manifest: {output_dir / 'manifest.tsv'}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return generate_contact_sheets(parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
