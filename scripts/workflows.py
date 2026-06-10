#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from media_toolkit.commands.workflows import main, parse_args


if __name__ == "__main__":
    raise SystemExit(main())
