"""Compatibility exports for the old src package."""

from media_toolkit.legacy_processing import (
    FileContext,
    compress_video,
    compress_drone_video,
    compress_rate,
    convert_webm_to_mp4,
    get_video_bitrate,
    get_video_fps,
    get_video_resolution,
    format_file_size,
    print_video_info,
    compress_image,
    traverse,
)

__all__ = [
    "traverse",
    "FileContext",
    "compress_video",
    "compress_drone_video",
    "compress_rate",
    "convert_webm_to_mp4",
    "get_video_bitrate",
    "get_video_fps",
    "get_video_resolution",
    "format_file_size",
    "print_video_info",
    "compress_image",
]
