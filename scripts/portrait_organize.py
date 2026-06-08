#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from media_toolkit import manifest_organize


ManifestEntry = manifest_organize.ManifestEntry
MoveOperation = manifest_organize.MoveOperation


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move portrait RAW/HIF pairs into portrait/<group>/ folders.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory containing raw/ and hif/")
    parser.add_argument(
        "--manifest",
        help="TSV or CSV with columns stem and group. Defaults to portrait/portrait_manifest.tsv.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print planned moves without changing files.",
    )
    parser.add_argument(
        "--no-contact-sheets",
        action="store_true",
        help="Skip rebuilding root and portrait contact sheets after moving.",
    )
    return parser.parse_args(argv)


def read_manifest(path: Path) -> list[ManifestEntry]:
    return manifest_organize.read_manifest(path)


def build_move_plan(root: Path, entries: list[ManifestEntry]) -> list[MoveOperation]:
    return manifest_organize.build_move_plan(root, entries, "portrait")


def apply_move_plan(operations: list[MoveOperation]) -> None:
    manifest_organize.apply_move_plan(operations)


def run_command(command: list[str]) -> None:
    manifest_organize.run_command(command)


def rebuild_contact_sheets(root: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="portrait-organize-sheets-") as temp:
        temp_dir = Path(temp)
        run_command(
            [
                "mt",
                "contact-sheet",
                str(root),
                "--hif-only",
                "--exclude-dir",
                "portrait",
                "--exclude-dir",
                "panorama",
                "--output",
                str(temp_dir / "root"),
                "--final-overview",
                str(root / "_contact_sheet.jpg"),
            ]
        )

        portrait_dir = root / "portrait"
        if portrait_dir.exists():
            run_command(
                [
                    "mt",
                    "contact-sheet",
                    str(portrait_dir),
                    "--hif-only",
                    "--output",
                    str(temp_dir / "portrait"),
                    "--final-overview",
                    str(portrait_dir / "_contact_sheet.jpg"),
                    "--section-by-numbered-dir",
                    "--section-prefix",
                    "Portrait",
                ]
            )


def summarize(entries: list[ManifestEntry]) -> str:
    return manifest_organize.summarize(entries, "portrait")


def organize_portraits(args: argparse.Namespace) -> int:
    root = Path(args.directory).expanduser().resolve()
    manifest = (
        Path(args.manifest).expanduser().resolve()
        if args.manifest
        else root / "portrait" / "portrait_manifest.tsv"
    )
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

    try:
        entries = read_manifest(manifest)
        operations = build_move_plan(root, entries)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(summarize(entries))
    if args.dry_run:
        for operation in operations:
            print(f"DRY-RUN {operation.source} -> {operation.destination}")
        return 0

    apply_move_plan(operations)
    print(f"Moved {len(operations)} file(s).")

    if not args.no_contact_sheets:
        rebuild_contact_sheets(root)
    return 0


if __name__ == "__main__":
    sys.exit(organize_portraits(parse_args()))
