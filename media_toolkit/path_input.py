from __future__ import annotations

import shlex
from pathlib import Path


def normalize_directory_input(raw_input: str) -> Path:
    value = raw_input.strip()
    if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
        value = value[1:-1]
    if "\\" in value:
        try:
            parts = shlex.split(value)
            if parts:
                value = parts[0]
        except ValueError:
            pass
    return Path(value).expanduser().resolve()
