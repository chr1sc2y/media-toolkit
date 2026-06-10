#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from media_toolkit.commands.fill_locations import (
    COMMON_APPLESCRIPT_HELPERS,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_WORK_DIR,
    ROOT,
    SCRIPT_FEATURES,
    PlanRow,
    RunTiming,
    applescript_quote,
    apply_plan,
    build_plan,
    export_source_locations,
    export_timeline_and_missing,
    format_duration,
    local_timestamp,
    main,
    parse_date_arg,
    parse_dt,
    run_osascript,
    script_description,
    write_outputs,
)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
