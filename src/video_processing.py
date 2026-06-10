"""Compatibility layer for legacy src.video_processing imports."""

from media_toolkit.legacy_processing import (
    compress_drone_video,
    compress_rate,
    compress_video,
    convert_webm_to_mp4,
    format_file_size,
    get_video_bitrate,
    get_video_fps,
    get_video_resolution,
    print_video_info,
)

__all__ = [
    "compress_video",
    "compress_drone_video",
    "compress_rate",
    "convert_webm_to_mp4",
    "get_video_bitrate",
    "get_video_fps",
    "get_video_resolution",
    "format_file_size",
    "print_video_info",
]
