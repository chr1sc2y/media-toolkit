from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from media_toolkit.final_hif_archive import EXPORT_EXTS


def collect_photos_export_files(base_dir: Path) -> list[Path]:
    base_dir = Path(base_dir).expanduser().resolve()
    export_dirs = [base_dir / "raw" / "Export"]
    for group_name in ("portrait", "panorama"):
        group_root = base_dir / group_name
        if group_root.exists():
            export_dirs.extend(sorted(group_root.glob("*/raw/Export")))

    files: list[Path] = []
    for export_dir in export_dirs:
        if not export_dir.is_dir():
            continue
        files.extend(
            path
            for path in export_dir.iterdir()
            if path.is_file() and path.suffix.lower() in EXPORT_EXTS
        )
    return sorted(files, key=lambda path: path.name.lower())


def _applescript_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_photos_import_script(export_files: list[Path], album: str) -> str:
    file_items = ", ".join(
        f"POSIX file {_applescript_string(str(path))}" for path in export_files
    )
    return f"""
tell application "Photos"
    if not (exists album {_applescript_string(album)}) then
        make new album named {_applescript_string(album)}
    end if
    set targetAlbum to album {_applescript_string(album)}
    import {{{file_items}}} into targetAlbum skip check duplicates false
end tell
"""


def import_exports_to_photos(
    base_dir: Path,
    *,
    album: str,
    dry_run: bool = False,
    runner=subprocess.run,
) -> bool:
    export_files = collect_photos_export_files(base_dir)
    if not export_files:
        print(f"   Warning: no Lightroom export files found for Photos import: {base_dir}")
        return False

    print(f"Photos album: {album}")
    print(f"Photos export files: {len(export_files)}")
    for path in export_files:
        try:
            display = path.relative_to(base_dir)
        except ValueError:
            display = path
        print(f"   {'Would import' if dry_run else 'Import'}: {display}")

    if dry_run:
        return True

    script = build_photos_import_script(export_files, album)
    try:
        runner(
            ["osascript", "-e", script],
            check=True,
            text=True,
            capture_output=True,
        )
    except FileNotFoundError:
        print("Error: osascript not found; Photos import requires macOS.", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        print(f"Error: Photos import failed{': ' + stderr if stderr else ''}", file=sys.stderr)
        return False
    return True
