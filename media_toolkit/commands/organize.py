from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence

from media_toolkit.path_input import normalize_directory_input
from media_toolkit.rawpy_tools import RAW_EXTS

FILE_TYPES = {
    "hif": frozenset({".hif", ".heif", ".heic"}),
    "raw": frozenset(RAW_EXTS | {
        ".acr",
        ".xmp",
    }),
}


@dataclass
class OrganizeSummary:
    scanned_dirs: int = 0
    moved: int = 0
    dry_run_moves: int = 0
    errors: int = 0
    moved_by_type: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    destination_dirs_by_type: dict[str, set[Path]] = field(
        default_factory=lambda: defaultdict(set)
    )


@dataclass(frozen=True)
class OrganizeOperation:
    source: Path
    destination: Path
    bucket: str


def normalize_extensions(extensions: Iterable[str]) -> frozenset[str]:
    return frozenset(
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in extensions
    )


def normalize_file_types(file_types: dict[str, Iterable[str]]) -> dict[str, frozenset[str]]:
    return {
        bucket.lower(): normalize_extensions(extensions)
        for bucket, extensions in file_types.items()
    }


def classify_file(file_path: Path, file_types: dict[str, frozenset[str]]) -> Optional[str]:
    extension = file_path.suffix.lower()
    for bucket, extensions in file_types.items():
        if extension in extensions:
            return bucket
    return None


def _destination_conflicts(destination: Path, planned_keys: set[str]) -> bool:
    destination_key = str(destination).casefold()
    if destination_key in planned_keys:
        return True
    if destination.parent.is_dir():
        destination_name = destination.name.casefold()
        if any(
            child.name.casefold() == destination_name
            for child in destination.parent.iterdir()
        ):
            return True
    return False


def _build_organize_plan(
    base_dir: Path,
    normalized_types: dict[str, frozenset[str]],
    summary: OrganizeSummary,
) -> list[OrganizeOperation]:
    output_dirs = frozenset(normalized_types)
    operations: list[OrganizeOperation] = []
    planned_keys: set[str] = set()

    for current_dir_str, dirnames, filenames in os.walk(base_dir):
        current_dir = Path(current_dir_str)
        dirnames[:] = sorted(
            name for name in dirnames if name.lower() not in output_dirs
        )
        summary.scanned_dirs += 1

        for filename in sorted(filenames):
            source = current_dir / filename
            bucket = classify_file(source, normalized_types)
            if bucket is None:
                continue

            destination_dir = current_dir / bucket
            destination = destination_dir / source.name
            if _destination_conflicts(destination, planned_keys):
                raise FileExistsError(f"destination already exists: {destination}")

            planned_keys.add(str(destination).casefold())
            operations.append(OrganizeOperation(source, destination, bucket))
            summary.moved_by_type[bucket] += 1
            summary.destination_dirs_by_type[bucket].add(destination_dir)

    return operations


def _execute_organize_plan(
    operations: Sequence[OrganizeOperation],
    summary: OrganizeSummary,
    *,
    verbose: bool,
) -> None:
    completed: list[OrganizeOperation] = []
    created_dirs: list[Path] = []

    planned_keys: set[str] = set()
    for operation in operations:
        if _destination_conflicts(operation.destination, planned_keys):
            raise FileExistsError(
                f"destination already exists: {operation.destination}"
            )
        planned_keys.add(str(operation.destination).casefold())

    try:
        for operation in operations:
            destination_dir = operation.destination.parent
            if not destination_dir.exists():
                destination_dir.mkdir()
                created_dirs.append(destination_dir)
            if _destination_conflicts(operation.destination, set()):
                raise FileExistsError(
                    f"destination already exists: {operation.destination}"
                )
            shutil.move(str(operation.source), str(operation.destination))
            completed.append(operation)
            summary.moved += 1
            if verbose:
                print(f"MOVED {operation.source} -> {operation.destination}")
    except OSError as exc:
        rollback_errors: list[str] = []
        for operation in reversed(completed):
            try:
                shutil.move(str(operation.destination), str(operation.source))
            except OSError as rollback_exc:
                rollback_errors.append(
                    f"{operation.destination} -> {operation.source}: {rollback_exc}"
                )
        for directory in reversed(created_dirs):
            try:
                directory.rmdir()
            except OSError:
                if directory.exists() and any(directory.iterdir()):
                    continue
                rollback_errors.append(f"could not remove directory {directory}")

        summary.errors += 1
        summary.moved = 0 if not rollback_errors else summary.moved
        if rollback_errors:
            details = "; ".join(rollback_errors)
            raise RuntimeError(
                f"organize failed after {len(completed)} moves; rollback incomplete: "
                f"{exc}; {details}"
            ) from exc
        raise RuntimeError(
            f"organize failed after {len(completed)} moves and was rolled back: {exc}"
        ) from exc


def organize_directory(
    base_dir: Path,
    *,
    dry_run: bool = False,
    verbose: bool = False,
    file_types: Optional[dict[str, Iterable[str]]] = None,
) -> OrganizeSummary:
    base_dir = Path(base_dir).expanduser().resolve()
    if not base_dir.exists():
        raise FileNotFoundError(f"Directory does not exist: {base_dir}")
    if not base_dir.is_dir():
        raise NotADirectoryError(f"Not a directory: {base_dir}")

    normalized_types = normalize_file_types(file_types or FILE_TYPES)
    summary = OrganizeSummary()

    operations = _build_organize_plan(base_dir, normalized_types, summary)
    if dry_run:
        summary.dry_run_moves = len(operations)
        if verbose:
            for operation in operations:
                print(f"DRY-RUN {operation.source} -> {operation.destination}")
        return summary

    _execute_organize_plan(operations, summary, verbose=verbose)

    return summary


def get_target_directory(args: argparse.Namespace) -> Path:
    if args.directory:
        return normalize_directory_input(args.directory)

    print(
        "  (Tip: you can paste paths copied from your terminal, "
        "including ones shown with \\ escapes for spaces.)"
    )
    raw_input = input(
        "Enter the directory to organize (press Enter for current directory): "
    )
    if not raw_input.strip():
        return Path.cwd().resolve()
    return normalize_directory_input(raw_input)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt organize",
        description="Recursively move camera media files into typed folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /Volumes/Untitled/DCIM
  %(prog)s ~/Pictures/SonyImport --dry-run --verbose
  %(prog)s ~/Pictures/Import --type xmp:xmp
  %(prog)s
        """,
    )
    parser.add_argument(
        "directory",
        nargs="?",
        help="Directory to organize. If omitted, the script prompts for one.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan moves without changing files; add --verbose to print each move.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every individual file move.",
    )
    parser.add_argument(
        "--type",
        action="append",
        dest="extra_types",
        metavar="FOLDER:EXT[,EXT...]",
        help="Add or replace a file type mapping, repeatable. Example: --type xmp:xmp",
    )
    return parser.parse_args(argv)


def build_file_types(extra_types: Optional[Sequence[str]]) -> dict[str, frozenset[str]]:
    file_types = dict(FILE_TYPES)
    for type_spec in extra_types or ():
        if ":" not in type_spec:
            raise ValueError(f"Invalid --type value: {type_spec}")
        bucket, extensions = type_spec.split(":", 1)
        bucket = bucket.strip().lower()
        extension_list = [ext.strip() for ext in extensions.split(",") if ext.strip()]
        if not bucket or not extension_list:
            raise ValueError(f"Invalid --type value: {type_spec}")
        file_types[bucket] = normalize_extensions(extension_list)
    return file_types


def print_summary(summary: OrganizeSummary, target_dir: Path, dry_run: bool) -> None:
    action_count = summary.dry_run_moves if dry_run else summary.moved
    print("\nSummary")
    print(f"  Directory: {target_dir}")
    print(f"  Scanned directories: {summary.scanned_dirs}")
    print(f"  {'Planned moves' if dry_run else 'Moved files'}: {action_count}")

    for bucket in sorted(summary.moved_by_type):
        count = summary.moved_by_type[bucket]
        noun = "file" if count == 1 else "files"
        print(f"  {bucket}: {count} {noun}")
        for destination_dir in sorted(summary.destination_dirs_by_type[bucket]):
            print(f"    -> {destination_dir}")

    print("  Collision policy: hard error (automatic renaming disabled)")
    print(f"  Errors: {summary.errors}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    target_dir = get_target_directory(args)

    try:
        file_types = build_file_types(args.extra_types)
        summary = organize_directory(
            target_dir,
            dry_run=args.dry_run,
            verbose=args.verbose,
            file_types=file_types,
        )
    except (
        FileExistsError,
        FileNotFoundError,
        NotADirectoryError,
        RuntimeError,
        ValueError,
    ) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_summary(summary, target_dir, args.dry_run)
    return 1 if summary.errors else 0
