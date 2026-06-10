from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit import final_hif_archive
from media_toolkit.finalize_workflow import (
    DEFAULT_PHOTOS_ALBUM,
    copy_destination_is_inside_source,
    finalize_directory,
    find_finalize_directories,
)
from media_toolkit.photos_import import (
    build_photos_import_script,
    collect_photos_export_files,
    import_exports_to_photos,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt finalize",
        description="Finalize Lightroom-exported photos by copying matching original HIF previews to an explicit destination and optionally importing Lightroom exports into Apple Photos.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Photo directory to finalize")
    parser.add_argument(
        "--copy-to",
        help="Destination directory for matching original HIF previews. Must be outside the source photo directory.",
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
        "--dry-run",
        action="store_true",
        help="List HIF copy and Photos import actions without copying files or importing into Photos.",
    )
    parser.add_argument(
        "--hif-only",
        "--no-photos",
        dest="hif_only",
        action="store_true",
        help="Copy matching HIF files only; do not import Lightroom exports into Apple Photos.",
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
                print("Error: --copy-to destination directory is required for HIF copies.", file=sys.stderr)
                return 2
            copy_to = final_hif_archive.normalize_directory_input(raw)
        else:
            print("Error: --copy-to is required for the HIF archive.", file=sys.stderr)
            return 2

    assert copy_to is not None
    destination = copy_to.expanduser().resolve()
    for base in bases:
        if copy_destination_is_inside_source(base, destination):
            print(
                "Error: --copy-to must be outside the source photo directory. "
                "Provide an explicit archive destination such as /Volumes/SD/DCIM/101MSDCF.",
                file=sys.stderr,
            )
            return 2

    success = True
    for base in bases:
        if not finalize_directory(
            base,
            copy_to=copy_to,
            scene=args.scene,
            photos_album=None if args.hif_only else args.photos_album,
            photos_dry_run=args.photos_dry_run,
            dry_run=args.dry_run,
        ):
            success = False
    return 0 if success else 1
