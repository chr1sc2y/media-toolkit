#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from media_toolkit.commands.contact_sheet import (
    FFMPEG_FULL_PATHS,
    IMAGE_EXTS,
    TRANSCODE_INPUT_EXTS,
    SheetPage,
    build_sheet_plan,
    chunk_images,
    collect_images,
    combine_contact_sheets,
    escape_drawtext,
    ffmpeg_has_filter,
    format_label,
    generate_contact_sheets,
    is_excluded,
    is_under_export,
    is_under_hif,
    load_font,
    main,
    numbered_section_key,
    parse_args,
    prepare_input_image,
    render_blank,
    render_ffmpeg_input_image,
    render_sheet,
    render_tile,
    require_ffmpeg,
    run_ffmpeg,
    run_sips,
    shorten_label,
    write_manifest,
)


if __name__ == "__main__":
    raise SystemExit(main())
