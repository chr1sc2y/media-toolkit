#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from media_toolkit.commands.organize import (
    FILE_TYPES,
    OrganizeSummary,
    build_file_types,
    classify_file,
    get_target_directory,
    main,
    normalize_directory_input,
    normalize_extensions,
    normalize_file_types,
    organize_directory,
    parse_args,
    print_summary,
    unique_destination,
)


_normalize_directory_input = normalize_directory_input


if __name__ == "__main__":
    raise SystemExit(main())
