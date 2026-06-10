#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from media_toolkit.commands.finalize import (
    build_photos_import_script,
    collect_photos_export_files,
    copy_destination_is_inside_source,
    finalize_directory,
    find_finalize_directories,
    import_exports_to_photos,
    main,
    parse_args,
)


if __name__ == "__main__":
    raise SystemExit(main())
