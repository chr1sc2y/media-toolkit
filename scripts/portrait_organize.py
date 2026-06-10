#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from media_toolkit.commands.portrait_organize import (
    ManifestEntry,
    MoveOperation,
    apply_move_plan,
    build_move_plan,
    main,
    organize_portraits,
    parse_args,
    read_manifest,
    rebuild_contact_sheets,
    run_command,
    summarize,
)


if __name__ == "__main__":
    raise SystemExit(main())
