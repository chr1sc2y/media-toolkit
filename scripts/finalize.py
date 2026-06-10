#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PHOTOS_ALBUM = "Sony"
FEATURED_SPEC = importlib.util.spec_from_file_location(
    "extract_featured_raw",
    SCRIPT_DIR / "extract_featured_raw.py",
)
extract_featured_raw = importlib.util.module_from_spec(FEATURED_SPEC)
assert FEATURED_SPEC.loader is not None
FEATURED_SPEC.loader.exec_module(extract_featured_raw)


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
            if path.is_file() and path.suffix.lower() in extract_featured_raw.EXPORT_EXTS
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


def finalize_directory(
    base_dir: Path,
    *,
    copy_to: Path | None,
    scene: str,
    photos_album: str | None = None,
    photos_dry_run: bool = False,
) -> bool:
    base_dir = Path(base_dir).expanduser().resolve()
    print(f"Finalizing scene: {scene}")
    success = True
    if copy_to is not None:
        destination = Path(copy_to).expanduser().resolve()
        success = extract_featured_raw.process_files(base_dir, destination) and success
    if photos_album:
        success = import_exports_to_photos(
            base_dir,
            album=photos_album,
            dry_run=photos_dry_run,
        ) and success
    return success


def find_finalize_directories(root: Path) -> list[Path]:
    return extract_featured_raw.find_directories_with_raw(root)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Finalize Lightroom-exported photos by copying matching original HIF previews to an SD card folder and importing Lightroom exports into Apple Photos.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Photo directory to finalize")
    parser.add_argument(
        "--copy-to",
        help="SD card destination directory for matching original HIF previews.",
    )
    parser.add_argument(
        "--scene",
        default="general-travel",
        help="Scene category label for reporting and future repo-level style tuning.",
    )
    parser.add_argument(
        "--photos-album",
        default=DEFAULT_PHOTOS_ALBUM,
        help="Import Lightroom export images into this Apple Photos album.",
    )
    parser.add_argument(
        "--photos-dry-run",
        action="store_true",
        help="List Lightroom export images that would be imported into Photos without importing.",
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Finalize every subdirectory containing a raw/ folder.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

    if args.recursive:
        bases = find_finalize_directories(root)
        if not bases:
            print("No directories with raw/ found.", file=sys.stderr)
            return 1
    else:
        bases = [root]

    copy_to = Path(args.copy_to).expanduser() if args.copy_to else None
    if copy_to is None:
        if sys.stdin.isatty():
            raw = input("Enter destination directory for HIF copies: ").strip()
            if not raw:
                print("Error: SD card destination directory is required for HIF copies.", file=sys.stderr)
                return 2
            copy_to = extract_featured_raw._normalize_directory_input(raw)
        else:
            print("Error: --copy-to is required for the SD card HIF archive.", file=sys.stderr)
            return 2

    success = True
    for base in bases:
        if not finalize_directory(
            base,
            copy_to=copy_to,
            scene=args.scene,
            photos_album=args.photos_album,
            photos_dry_run=args.photos_dry_run,
        ):
            success = False
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
