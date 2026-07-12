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
    find_photos_import_directories,
    is_panorama_finalize_directory,
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
        dest="recursive",
        action="store_true",
        default=True,
        help="Finalize every subdirectory containing a raw/ folder.",
    )
    parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Finalize only the provided directory.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

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
    if copy_destination_is_inside_source(root, destination):
        print(
            "Error: --copy-to must be outside the source photo directory. "
            "Provide an explicit archive destination such as /Volumes/SD/DCIM/101MSDCF.",
            file=sys.stderr,
        )
        return 2

    if args.recursive:
        bases = find_finalize_directories(root)
        photos_bases = find_photos_import_directories(root)
        if not bases and (args.hif_only or not photos_bases):
            print("No directories with raw/ found.", file=sys.stderr)
            return 1
    else:
        bases = [] if is_panorama_finalize_directory(root) else [root]
        photos_bases = [root]
        if not bases and args.hif_only:
            print("Panorama source HIF files cannot be archived.", file=sys.stderr)
            return 1

    print(f"Finalizing scene: {args.scene}")
    if bases:
        archive_plan = final_hif_archive.build_archive_plan(
            bases,
            destination,
            source_root=root,
        )
        success = final_hif_archive.execute_archive_plan(
            archive_plan,
            dry_run=args.dry_run,
        )
    else:
        success = True

    if not args.hif_only:
        photos_preview = args.photos_dry_run or args.dry_run
        if success or photos_preview:
            for base in photos_bases:
                if not import_exports_to_photos(
                    base,
                    album=args.photos_album,
                    dry_run=photos_preview,
                ):
                    success = False
    return 0 if success else 1
