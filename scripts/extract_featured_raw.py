#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from media_toolkit.commands.extract_featured_raw import (
    EXPORT_EXTS,
    FEATURED_EXTS,
    HIF_EXTS,
    _destination_is_inside_source,
    _normalize_directory_input,
    find_directories_with_raw,
    get_target_directory,
    main,
    parse_args,
    process_files,
)


if __name__ == "__main__":
    raise SystemExit(main())
