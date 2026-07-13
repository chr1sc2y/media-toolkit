from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from media_toolkit import manifest_organize


ManifestEntry = manifest_organize.ManifestEntry
MoveOperation = manifest_organize.MoveOperation


def read_manifest(path: Path) -> list[ManifestEntry]:
    return manifest_organize.read_manifest(path)


def build_move_plan(
    root: Path,
    entries: list[ManifestEntry],
    group_kind: str,
) -> list[MoveOperation]:
    return manifest_organize.build_move_plan(root, entries, group_kind)


def apply_move_plan(operations: list[MoveOperation]) -> None:
    manifest_organize.apply_move_plan(operations)


def run_command(command: list[str]) -> None:
    manifest_organize.run_command(command)


def numbered_group_dirs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.iterdir() if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
    )


def rebuild_contact_sheets(
    root: Path,
    group_kind: str,
    section_prefix: str,
    runner=run_command,
) -> None:
    with tempfile.TemporaryDirectory(prefix=f"{group_kind}-organize-sheets-") as temp:
        temp_dir = Path(temp)
        runner(
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

        group_dir = root / group_kind
        for numbered_dir in numbered_group_dirs(group_dir):
            runner(
                [
                    "mt",
                    "contact-sheet",
                    str(numbered_dir),
                    "--hif-only",
                    "--output",
                    str(temp_dir / group_kind / numbered_dir.name),
                    "--final-overview",
                    str(numbered_dir / "_contact_sheet.jpg"),
                ]
            )
        legacy_sheet = group_dir / "_contact_sheet.jpg"
        if legacy_sheet.exists():
            legacy_sheet.unlink()


def summarize(entries: list[ManifestEntry], group_kind: str) -> str:
    return manifest_organize.summarize(entries, group_kind)


def organize_groups(
    args: argparse.Namespace,
    *,
    group_kind: str,
    section_prefix: str,
    rebuild_func=rebuild_contact_sheets,
) -> int:
    root = Path(args.directory).expanduser().resolve()
    manifest = (
        Path(args.manifest).expanduser().resolve()
        if args.manifest
        else root / group_kind / f"{group_kind}_manifest.tsv"
    )
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

    try:
        entries = read_manifest(manifest)
        operations = build_move_plan(root, entries, group_kind)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(summarize(entries, group_kind))
    if args.dry_run:
        for operation in operations:
            print(f"DRY-RUN {operation.source} -> {operation.destination}")
        return 0

    try:
        apply_move_plan(operations)
    except (OSError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Moved {len(operations)} file(s).")

    if not args.no_contact_sheets:
        rebuild_func(root, group_kind, section_prefix)
    return 0
