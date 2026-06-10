from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from media_toolkit.path_input import normalize_directory_input

EXPORT_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}
HIF_EXTS = {".hif"}


def destination_is_inside_source(base_dir: Path, destination_dir: Path) -> bool:
    base_dir = Path(base_dir).expanduser().resolve()
    destination_dir = Path(destination_dir).expanduser().resolve()
    return destination_dir == base_dir or destination_dir.is_relative_to(base_dir)


def find_directories_with_raw(root: Path) -> list[Path]:
    found: list[Path] = []
    root = Path(root).expanduser().resolve()
    for dirpath, dirnames, _ in os.walk(root):
        current = Path(dirpath)
        if (current / "raw").is_dir():
            found.append(current)
            dirnames[:] = [
                dirname for dirname in dirnames if dirname.lower() not in ("raw", "featured")
            ]
    return sorted(found)


def export_scan_directories(base_dir: Path) -> list[Path]:
    base_dir = Path(base_dir)
    export_dirs: list[Path] = []
    seen: set[Path] = set()

    def add_dir(path: Path) -> None:
        if not path.exists() or not path.is_dir():
            return
        real = path.resolve()
        if real not in seen:
            seen.add(real)
            export_dirs.append(path)

    add_dir(base_dir / "raw" / "Export")
    for group_name in ("portrait",):
        group_root = base_dir / group_name
        if not group_root.exists():
            continue
        try:
            for child in group_root.iterdir():
                if child.is_dir():
                    add_dir(child / "raw" / "Export")
        except PermissionError:
            pass
    return export_dirs


def hif_search_directories(base_dir: Path) -> list[Path]:
    base_dir = Path(base_dir)
    search_dirs: list[Path] = []
    seen: set[Path] = set()

    def add_dir(path: Path) -> None:
        if not path.exists() or not path.is_dir():
            return
        real = path.resolve()
        if real not in seen:
            seen.add(real)
            search_dirs.append(path)

    add_dir(base_dir / "hif")
    group_root = base_dir / "portrait"
    if group_root.exists():
        try:
            for child in group_root.iterdir():
                if child.is_dir():
                    add_dir(child / "hif")
        except PermissionError:
            pass
    return search_dirs


def display_relative(base_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(base_dir))
    except ValueError:
        return str(path)


def _scan_export_stems(export_dir: Path) -> set[str]:
    stems: set[str] = set()
    for file_path in export_dir.iterdir():
        if not file_path.is_file():
            continue
        if file_path.stem.startswith("."):
            continue
        if file_path.suffix.lower() in EXPORT_EXTS:
            stems.add(file_path.stem.lower())
    return stems


def selected_export_stems(base_dir: Path) -> set[str]:
    stems: set[str] = set()
    for export_dir in export_scan_directories(base_dir):
        stems.update(_scan_export_stems(export_dir))
    return stems


def matching_hif_files(base_dir: Path, selected_stems: set[str]) -> dict[str, Path]:
    matches: dict[str, Path] = {}
    seen_paths: set[Path] = set()
    for search_dir in hif_search_directories(base_dir):
        try:
            for file_path in search_dir.iterdir():
                if not file_path.is_file():
                    continue
                stem = file_path.stem.lower()
                if stem.startswith("."):
                    continue
                if stem not in selected_stems or file_path.suffix.lower() not in HIF_EXTS:
                    continue
                if stem in matches:
                    continue
                real = file_path.resolve()
                if real in seen_paths:
                    continue
                seen_paths.add(real)
                matches[stem] = file_path
        except PermissionError:
            print(f"   Permission denied: {search_dir}")
            continue
    return matches


def process_files(base_dir: Path, destination_dir: Path, *, dry_run: bool = False) -> bool:
    base_dir = Path(base_dir).expanduser().resolve()
    destination_dir = Path(destination_dir).expanduser().resolve()
    raw_dir = base_dir / "raw"
    if destination_is_inside_source(base_dir, destination_dir):
        print(
            "Error: --copy-to must be outside the source photo directory. "
            "Provide an explicit archive destination such as /Volumes/SD/DCIM/101MSDCF.",
            file=sys.stderr,
        )
        return False

    print(f"\n{'='*60}")
    print("FINAL HIF COPIER")
    print(f"{'='*60}")
    print(f"Working directory: {base_dir}")

    export_dirs = export_scan_directories(base_dir)
    if not export_dirs:
        print(f"\nError: no Lightroom export directories found in '{base_dir}'")
        return False

    print(f"Raw directory: {raw_dir}")
    print(f"Destination directory: {destination_dir}")
    print(f"\n{'Step 1: Scanning Lightroom export directories':-<50}")

    try:
        selected_stems = selected_export_stems(base_dir)
    except PermissionError:
        print(f"Error: Permission denied accessing '{raw_dir}'")
        return False

    if not selected_stems:
        print("   Warning: No valid Lightroom export files found.")
        return False

    print(
        "   Scanning export directories: "
        + ", ".join(display_relative(base_dir, directory) for directory in export_dirs)
    )
    print(f"   Total unique exported file names: {len(selected_stems)}")

    print(f"\n{'Step 2: Finding matching files':-<50}")
    search_dirs = hif_search_directories(base_dir)
    if search_dirs:
        print(
            "   Searching in HIF directories: "
            + ", ".join(display_relative(base_dir, directory) for directory in search_dirs)
        )
    else:
        print("   Searching in HIF directories: none found")

    matches = matching_hif_files(base_dir, selected_stems)
    print(f"   Searched directories: {len(search_dirs)}")
    matching_files = [matches[stem] for stem in sorted(matches)]
    if not matching_files:
        print("   Warning: No matching files found in any searched directory.")
        return False

    for file_path in matching_files:
        print(f"   Match: {display_relative(base_dir, file_path)}")
    print(f"   Total matching files: {len(matching_files)}")
    missing_hif = sorted(selected_stems - set(matches))
    if missing_hif:
        print(f"   Missing matching HIF files: {', '.join(missing_hif)}")

    step_title = "Step 3: Dry-run HIF copy plan" if dry_run else "Step 3: Copying files to destination directory"
    print(f"\n{step_title:-<50}")
    try:
        if dry_run:
            for file_path in matching_files:
                destination = destination_dir / file_path.name
                action = "would skip existing" if destination.exists() else "would copy"
                print(f"   {action}: {display_relative(base_dir, file_path)} -> {destination}")
            print(f"\n{'SUMMARY':-<50}")
            print(f"   Would copy: {len(matching_files)} files")
            print(f"   Destination: {destination_dir}")
            return True

        destination_dir.mkdir(parents=True, exist_ok=True)
        print(f"   Directory ready: {destination_dir}")

        copied_count = 0
        failed_count = 0
        skipped_count = 0
        for file_path in matching_files:
            try:
                destination = destination_dir / file_path.name
                if destination.exists():
                    print(f"   Skipped (already exists): {file_path.name}")
                    skipped_count += 1
                    continue
                shutil.copy2(file_path, destination)
                print(f"   Copied: {display_relative(base_dir, file_path)}")
                copied_count += 1
            except Exception as exc:
                print(f"   Failed: {file_path.name} - {exc}")
                failed_count += 1

        print(f"\n{'SUMMARY':-<50}")
        print(f"   Successfully copied: {copied_count} files")
        if skipped_count:
            print(f"   Skipped duplicates: {skipped_count} files")
        if failed_count:
            print(f"   Failed to copy: {failed_count} files")
        print(f"   Destination: {destination_dir}")
        return copied_count > 0
    except Exception as exc:
        print(f"Error creating destination directory: {exc}")
        return False
