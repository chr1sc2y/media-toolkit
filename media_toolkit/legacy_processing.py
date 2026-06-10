from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Callable


class FileContext:
    """Processing context for legacy compression commands."""

    def __init__(self, original_file: str) -> None:
        self.original_file = str(original_file)
        source = Path(original_file)
        compressed_dir = source.parent / "compressed"
        compressed_dir.mkdir(parents=True, exist_ok=True)

        self.temp_file = str(compressed_dir / f"{source.stem}-temp{source.suffix}")
        self.final_file = str(compressed_dir / source.name)
        self.original_file_name = self.original_file
        self.temp_file_name = self.temp_file

    def set_format(self, format: str) -> None:
        temp_path = Path(self.temp_file)
        source = Path(self.original_file)
        self.temp_file = str(temp_path.with_suffix(f".{format}"))
        self.temp_file_name = self.temp_file
        self.final_file = str(Path(self.final_file).with_name(f"{source.stem}.{format}"))

    def archive_original_file(self) -> None:
        pass

    def delete_original_file(self) -> None:
        if os.path.exists(self.original_file):
            os.remove(self.original_file)

    def rename_temp_file(self) -> None:
        os.replace(self.temp_file, self.final_file)


def traverse(
    directory: str,
    extension: str,
    func: Callable,
    var1=None,
    var2=None,
    var3=None,
    recursive: bool = False,
) -> None:
    root = Path(directory)
    if not root.exists():
        print(f"⚠️  Directory not found: {root}")
        return
    if not root.is_dir():
        print(f"⚠️  Not a directory: {root}")
        return

    for path in root.iterdir():
        try:
            if path.is_dir():
                if recursive:
                    traverse(str(path), extension, func, var1, var2, var3, recursive)
                continue
            if path.is_file() and path.name.lower().endswith(extension.lower()):
                func(FileContext(str(path)), var1, var2, var3)
        except (OSError, IOError, PermissionError) as exc:
            print(f"⚠️  Cannot access {path}: {exc}")


def _run_command(args: list[str], ctx: FileContext) -> bool:
    result = subprocess.run(args)
    if result.returncode == 0 and os.path.exists(ctx.temp_file):
        original_size = os.path.getsize(ctx.original_file)
        output_size = os.path.getsize(ctx.temp_file)
        ratio = (1 - output_size / original_size) * 100 if original_size else 0
        ctx.archive_original_file()
        ctx.rename_temp_file()
        print(f"✅ Success: {os.path.basename(ctx.original_file)}")
        print(f"   Size: {format_file_size(original_size)} -> {format_file_size(output_size)} (saved {ratio:.1f}%)\n")
        return True

    print(f"❌ Failed: {os.path.basename(ctx.original_file)} (exit code: {result.returncode})")
    if os.path.exists(ctx.temp_file):
        os.remove(ctx.temp_file)
    return False


def compress_image(ctx: FileContext, scale, extension=None, reserved=None) -> bool:
    ctx.set_format(extension)
    scale_param = "iw:ih" if scale in (None, "original") else scale
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-stats",
        "-i",
        ctx.original_file,
        "-vf",
        f"scale={scale_param}",
        "-map_metadata",
        "0",
        ctx.temp_file,
        "-y",
    ]
    return _run_command(args, ctx)


def get_video_bitrate(file_path: str) -> int:
    data = _ffprobe(file_path, "-show_format", "-show_streams")
    if "format" in data and "bit_rate" in data["format"]:
        return int(data["format"]["bit_rate"])
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video" and "bit_rate" in stream:
            return int(stream["bit_rate"])
    return 0


def get_video_fps(file_path: str) -> float:
    data = _ffprobe(file_path, "-show_streams")
    for stream in data.get("streams", []):
        if stream.get("codec_type") != "video":
            continue
        for key in ("r_frame_rate", "avg_frame_rate"):
            value = stream.get(key)
            if value and "/" in value:
                numerator, denominator = value.split("/")
                return float(numerator) / float(denominator)
    return 0


def get_video_resolution(file_path: str) -> tuple[int, int]:
    data = _ffprobe(file_path, "-show_streams")
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            return (int(stream.get("width", 0)), int(stream.get("height", 0)))
    return (0, 0)


def _ffprobe(file_path: str, *extra_args: str) -> dict:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", *extra_args, file_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def format_file_size(bytes_size: int) -> str:
    size = float(bytes_size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"


def print_video_info(resolution_str: str, fps: float, original_mbps: float, target_mbps: float, ratio: float) -> None:
    print(f"📊 {resolution_str} | {fps:.0f}fps | Bitrate: {original_mbps:.1f}M -> {target_mbps:.1f}M ({ratio*100:.0f}%)")


def compress_video(ctx: FileContext, scale, fps, bitrate=None) -> bool:
    if not scale:
        print(f"❌ Invalid scale parameter for {ctx.original_file_name}")
        return False
    if not fps or not isinstance(fps, (int, float)) or fps <= 0:
        print(f"❌ Invalid fps parameter for {ctx.original_file_name}: {fps}")
        return False
    return _run_command(_video_args(ctx, scale, fps, bitrate or "8M"), ctx)


def compress_drone_video(ctx: FileContext, scale="1920:1080", bitrate="15M", fps=None) -> bool:
    if not os.path.exists(ctx.original_file):
        print(f"⚠️  Skipping: File not found - {os.path.basename(ctx.original_file)}")
        return False
    width, height = get_video_resolution(ctx.original_file)
    original_fps = get_video_fps(ctx.original_file)
    original_bitrate_bps = get_video_bitrate(ctx.original_file)
    fps = fps if fps is not None else (original_fps if original_fps > 0 else 30)
    original_resolution = f"{width}x{height}" if width > 0 else "Unknown"
    original_mbps = original_bitrate_bps / 1_000_000 if original_bitrate_bps > 0 else 0
    target_mbps = float(bitrate.rstrip("Mk")) if isinstance(bitrate, str) else bitrate
    print(f"📊 {original_resolution} → 1920x1080 | {original_fps:.0f}fps → {fps:.0f}fps | Bitrate: {original_mbps:.1f}M → {target_mbps}M")
    return _run_command(_video_args(ctx, scale, fps, bitrate), ctx)


def _video_args(ctx: FileContext, scale, fps, bitrate) -> list[str]:
    return [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        ctx.original_file,
        "-vf",
        f"scale={scale}",
        "-r",
        str(fps),
        "-c:v",
        "hevc_videotoolbox",
        "-tag:v",
        "hvc1",
        "-b:v",
        str(bitrate),
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-map_metadata",
        "0",
        ctx.temp_file,
        "-y",
    ]


def compress_rate(ctx: FileContext, video_rate="8M", audio_rate="128k", reserved=None) -> bool:
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        ctx.original_file,
        "-b:v",
        str(video_rate),
        "-b:a",
        str(audio_rate),
        ctx.temp_file,
    ]
    return _run_command(args, ctx)


def convert_webm_to_mp4(ctx: FileContext, scale, reserved1=None, reserved2=None) -> bool:
    ctx.set_format("mp4")
    args = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        ctx.original_file,
        "-vf",
        f"scale={scale}",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-crf",
        "18",
        ctx.temp_file,
        "-y",
    ]
    return _run_command(args, ctx)
