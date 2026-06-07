#!/usr/bin/env python3
"""
Organize camera media files into per-directory type folders.

Usage:
    python3 scripts/organize.py /path/to/imported/card
    python3 scripts/organize.py /path/to/imported/card --dry-run
    python3 scripts/organize.py

If no directory is provided, the script prompts for one interactively.
"""

import argparse
import os
import shlex
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Sequence


FILE_TYPES = {
    "hif": frozenset({".hif", ".heif", ".heic"}),
    "raw": frozenset({
        ".3fr",
        ".acr",
        ".arw",
        ".cr2",
        ".cr3",
        ".dng",
        ".erf",
        ".iiq",
        ".nef",
        ".nrw",
        ".orf",
        ".pef",
        ".raf",
        ".raw",
        ".rw2",
        ".rwl",
        ".srw",
        ".x3f",
        ".xmp",
    }),
}
OUTPUT_DIRS = frozenset(FILE_TYPES)


def _normalize_directory_input(raw_input: str) -> Path:
    """
    Normalize a user-provided directory string.

    Handles:
    - Surrounding quotes (single or double)
    - Shell-style backslash escapes (e.g. paths copied from terminal prompts
      or history that contain "\\ " for spaces, "\\~" etc.)
    - Tilde expansion (~)

    This is especially useful in interactive mode where users often paste
    escaped paths directly from their shell.
    """
    s = raw_input.strip()

    # Remove one layer of surrounding matching quotes if present.
    if len(s) >= 2 and s[0] in ('"', "'") and s[-1] == s[0]:
        s = s[1:-1]

    # If the (now unquoted) string still contains backslashes, interpret
    # it as a shell-escaped path.
    if '\\' in s:
        try:
            parts = shlex.split(s)
            if parts:
                s = parts[0]
        except ValueError:
            # Malformed; keep what we have after quote stripping
            pass

    return Path(s).expanduser().resolve()


@dataclass
class OrganizeSummary:
    scanned_dirs: int = 0
    moved: int = 0
    renamed: int = 0
    dry_run_moves: int = 0
    errors: int = 0
    moved_by_type: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    destination_dirs_by_type: dict[str, set[Path]] = field(
        default_factory=lambda: defaultdict(set)
    )


def normalize_extensions(extensions: Iterable[str]) -> frozenset[str]:
    return frozenset(
        ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        for ext in extensions
    )


def unique_destination(destination: Path) -> tuple[Path, bool]:
    if not destination.exists():
        return destination, False

    for index in range(1, 10000):
        candidate = destination.with_name(
            f"{destination.stem}_{index}{destination.suffix}"
        )
        if not candidate.exists():
            return candidate, True

    raise FileExistsError(f"Could not find available destination for {destination}")


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
    output_dirs = frozenset(normalized_types)
    summary = OrganizeSummary()

    for current_dir_str, dirnames, filenames in os.walk(base_dir):
        current_dir = Path(current_dir_str)
        dirnames[:] = [name for name in dirnames if name.lower() not in output_dirs]
        summary.scanned_dirs += 1

        for filename in filenames:
            source = current_dir / filename
            bucket = classify_file(source, normalized_types)
            if bucket is None:
                continue

            destination_dir = current_dir / bucket
            destination, renamed = unique_destination(destination_dir / source.name)
            summary.moved_by_type[bucket] += 1
            summary.destination_dirs_by_type[bucket].add(destination_dir)

            if dry_run:
                summary.dry_run_moves += 1
                if renamed:
                    summary.renamed += 1
                if verbose:
                    print(f"DRY-RUN {source} -> {destination}")
                continue

            try:
                destination_dir.mkdir(exist_ok=True)
                shutil.move(str(source), str(destination))
                summary.moved += 1
                if renamed:
                    summary.renamed += 1
                if verbose:
                    print(f"MOVED {source} -> {destination}")
            except OSError as exc:
                summary.errors += 1
                print(f"ERROR {source}: {exc}", file=sys.stderr)

    return summary


def get_target_directory(args: argparse.Namespace) -> Path:
    if args.directory:
        return _normalize_directory_input(args.directory)

    print(
        "  (Tip: you can paste paths copied from your terminal, "
        "including ones shown with \\ escapes for spaces.)"
    )
    raw_input = input(
        "Enter the directory to organize (press Enter for current directory): "
    )
    user_input = raw_input.strip()
    if not user_input:
        return Path.cwd().resolve()
    return _normalize_directory_input(raw_input)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recursively move camera media files into typed folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /Volumes/Untitled/DCIM
  %(prog)s ~/Pictures/SonyImport --dry-run
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
        help="Print planned moves without changing files.",
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
    return parser.parse_args()


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

    print(f"  Renamed collisions: {summary.renamed}")
    print(f"  Errors: {summary.errors}")


def main() -> int:
    args = parse_args()
    target_dir = get_target_directory(args)

    try:
        file_types = build_file_types(args.extra_types)
        summary = organize_directory(
            target_dir,
            dry_run=args.dry_run,
            verbose=args.verbose,
            file_types=file_types,
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print_summary(summary, target_dir, args.dry_run)
    return 1 if summary.errors else 0


if __name__ == "__main__":
    sys.exit(main())
