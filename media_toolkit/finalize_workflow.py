from __future__ import annotations

from pathlib import Path

from media_toolkit import final_hif_archive
from media_toolkit.photos_import import import_exports_to_photos


DEFAULT_PHOTOS_ALBUM = "Sony"


def copy_destination_is_inside_source(source: Path, destination: Path) -> bool:
    return final_hif_archive.destination_is_inside_source(source, destination)


def find_finalize_directories(root: Path) -> list[Path]:
    directories = final_hif_archive.find_directories_with_raw(root)
    selected: list[Path] = []
    for directory in directories:
        if any(_is_group_child_of(directory, parent) for parent in selected):
            continue
        selected.append(directory)
    return selected


def _is_group_child_of(directory: Path, parent: Path) -> bool:
    try:
        relative = directory.relative_to(parent)
    except ValueError:
        return False
    parts = relative.parts
    return len(parts) >= 2 and parts[0] in {"portrait", "panorama"}


def finalize_directory(
    base_dir: Path,
    *,
    copy_to: Path | None,
    scene: str,
    photos_album: str | None = None,
    photos_dry_run: bool = False,
    dry_run: bool = False,
) -> bool:
    base_dir = Path(base_dir).expanduser().resolve()
    print(f"Finalizing scene: {scene}")
    success = True
    if copy_to is not None:
        success = final_hif_archive.process_files(base_dir, copy_to, dry_run=dry_run) and success
    if photos_album:
        success = import_exports_to_photos(
            base_dir,
            album=photos_album,
            dry_run=photos_dry_run or dry_run,
        ) and success
    return success
