#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from media_toolkit.commands.png_to_jpg import (
    compress_image,
    get_directory,
    main,
    parse_args,
    traverse,
)
from media_toolkit.path_input import normalize_directory_input


if __name__ == "__main__":
    raise SystemExit(main())
