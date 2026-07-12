from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from media_toolkit.path_input import normalize_directory_input

EXPORT_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}
HIF_EXTS = {".hif", ".heif", ".heic"}


@dataclass(frozen=True)
class HifArchiveItem:
    source: Path
    destination: Path


@dataclass(frozen=True)
class HifArchivePlan:
    source_root: Path
    base_dirs: tuple[Path, ...]
    destination_dir: Path
    copies: tuple[HifArchiveItem, ...]
    identical_skips: tuple[HifArchiveItem, ...]
    errors: tuple[str, ...]


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


def child_dir_case_insensitive(parent: Path, name: str) -> Path:
    desired = name.lower()
    try:
        for child in parent.iterdir():
            if child.is_dir() and child.name.lower() == desired:
                return child
    except (FileNotFoundError, PermissionError):
        pass
    return parent / name


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

    root_export = base_dir / "raw" / "Export"
    add_dir(root_export)
    add_dir(child_dir_case_insensitive(root_export, "Pixcake"))
    for group_name in ("portrait",):
        group_root = base_dir / group_name
        if not group_root.exists():
            continue
        try:
            for child in group_root.iterdir():
                if child.is_dir():
                    export_dir = child / "raw" / "Export"
                    add_dir(export_dir)
                    add_dir(child_dir_case_insensitive(export_dir, "Pixcake"))
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


def files_are_byte_identical(left: Path, right: Path) -> bool:
    try:
        if left.stat().st_size != right.stat().st_size:
            return False
        return _file_digest(left) == _file_digest(right)
    except OSError:
        return False


def _file_digest(path: Path) -> bytes:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


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


def matching_hif_candidates(
    base_dir: Path,
    selected_stems: set[str],
) -> dict[str, list[Path]]:
    candidates: dict[str, list[Path]] = {}
    seen_paths: set[Path] = set()
    for search_dir in hif_search_directories(base_dir):
        try:
            for file_path in sorted(
                search_dir.iterdir(),
                key=lambda path: path.name.casefold(),
            ):
                if not file_path.is_file():
                    continue
                stem = file_path.stem.lower()
                if stem.startswith("."):
                    continue
                if stem not in selected_stems or file_path.suffix.lower() not in HIF_EXTS:
                    continue
                real = file_path.resolve()
                if real in seen_paths:
                    continue
                seen_paths.add(real)
                candidates.setdefault(stem, []).append(file_path)
        except PermissionError:
            print(f"   Permission denied: {search_dir}")
            continue
    for paths in candidates.values():
        paths.sort(key=lambda path: str(path).casefold())
    return candidates


def matching_hif_files(base_dir: Path, selected_stems: set[str]) -> dict[str, Path]:
    candidates = matching_hif_candidates(base_dir, selected_stems)
    return {stem: paths[0] for stem, paths in candidates.items() if paths}


def build_archive_plan(
    base_dirs: list[Path],
    destination_dir: Path,
    *,
    source_root: Path | None = None,
) -> HifArchivePlan:
    bases = tuple(Path(base).expanduser().resolve() for base in base_dirs)
    destination = Path(destination_dir).expanduser().resolve()
    root = (
        Path(source_root).expanduser().resolve()
        if source_root is not None
        else (bases[0] if bases else destination)
    )
    copies: list[HifArchiveItem] = []
    identical_skips: list[HifArchiveItem] = []
    errors: list[str] = []
    sources_by_destination_name: dict[str, Path] = {}

    if source_root is not None and destination_is_inside_source(root, destination):
        errors.append(f"destination is inside source root: {destination}")

    for base in bases:
        if destination_is_inside_source(base, destination):
            errors.append(f"destination is inside source base {base}: {destination}")
            continue

        export_dirs = export_scan_directories(base)
        if not export_dirs:
            errors.append(f"no Lightroom export directories found in {base}")
            continue
        try:
            selected_stems = selected_export_stems(base)
        except PermissionError:
            errors.append(f"permission denied accessing exports in {base}")
            continue
        if not selected_stems:
            errors.append(f"no valid Lightroom export files found in {base}")
            continue

        candidates = matching_hif_candidates(base, selected_stems)
        missing_hif = sorted(selected_stems - set(candidates))
        if missing_hif:
            errors.append(
                f"missing matching HIF files in {base}: {', '.join(missing_hif)}"
            )

        for stem in sorted(candidates):
            stem_candidates = candidates[stem]
            if len(stem_candidates) != 1:
                errors.append(
                    f"ambiguous HIF candidates for {stem} in {base}: "
                    + ", ".join(str(path) for path in stem_candidates)
                )
                continue
            source = stem_candidates[0]
            destination_name = source.name.casefold()
            prior_source = sources_by_destination_name.get(destination_name)
            if prior_source is not None:
                if not files_are_byte_identical(prior_source, source):
                    errors.append(
                        "different source files flatten to the same destination name "
                        f"{source.name}: {prior_source} and {source}"
                    )
                continue

            sources_by_destination_name[destination_name] = source
            destination_path = destination / source.name
            item = HifArchiveItem(source=source, destination=destination_path)
            if destination_path.exists() or destination_path.is_symlink():
                if files_are_byte_identical(source, destination_path):
                    identical_skips.append(item)
                else:
                    errors.append(
                        f"destination conflict for {source.name}: {destination_path}"
                    )
                continue
            copies.append(item)

    return HifArchivePlan(
        source_root=root,
        base_dirs=bases,
        destination_dir=destination,
        copies=tuple(copies),
        identical_skips=tuple(identical_skips),
        errors=tuple(errors),
    )


def execute_archive_plan(plan: HifArchivePlan, *, dry_run: bool = False) -> bool:
    print(f"\n{'='*60}")
    print("FINAL HIF COPIER")
    print(f"{'='*60}")
    print(f"Source root: {plan.source_root}")
    print(f"Destination directory: {plan.destination_dir}")

    for error in plan.errors:
        print(f"   Error: {error}")
    if plan.errors:
        print(f"   Validation failed: {len(plan.errors)} error(s); no files copied")
        return False

    if dry_run:
        for item in plan.copies:
            print(f"   would copy: {item.source} -> {item.destination}")
        for item in plan.identical_skips:
            print(f"   would skip identical: {item.source} -> {item.destination}")
        print(f"   Would copy: {len(plan.copies)} files")
        if plan.identical_skips:
            print(f"   Would skip existing: {len(plan.identical_skips)} files")
        print(f"   Destination: {plan.destination_dir}")
        return bool(plan.copies or plan.identical_skips)

    try:
        plan.destination_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"Error creating destination directory: {exc}")
        return False

    copied_count = 0
    skipped_count = len(plan.identical_skips)
    failed_count = 0
    for item in plan.copies:
        try:
            if item.destination.exists() or item.destination.is_symlink():
                if files_are_byte_identical(item.source, item.destination):
                    skipped_count += 1
                    continue
                print(f"   Conflict appeared after validation: {item.destination}")
                failed_count += 1
                continue
            shutil.copy2(item.source, item.destination)
            print(f"   Copied: {item.source}")
            copied_count += 1
        except OSError as exc:
            print(f"   Failed: {item.source.name} - {exc}")
            failed_count += 1

    print(f"   Successfully copied: {copied_count} files")
    if skipped_count:
        print(f"   Skipped duplicates: {skipped_count} files")
    if failed_count:
        print(f"   Failed to copy: {failed_count} files")
    print(f"   Destination: {plan.destination_dir}")
    return failed_count == 0 and (copied_count > 0 or skipped_count > 0)


def process_files(base_dir: Path, destination_dir: Path, *, dry_run: bool = False) -> bool:
    base_dir = Path(base_dir).expanduser().resolve()
    destination_dir = Path(destination_dir).expanduser().resolve()
    plan = build_archive_plan(
        [base_dir],
        destination_dir,
        source_root=base_dir,
    )
    return execute_archive_plan(plan, dry_run=dry_run)
