from __future__ import annotations

from pathlib import Path

from media_toolkit import final_hif_archive
from media_toolkit.photos_import import import_exports_to_photos


DEFAULT_PHOTOS_ALBUM = "Sony"


def copy_destination_is_inside_source(source: Path, destination: Path) -> bool:
    return final_hif_archive.destination_is_inside_source(source, destination)


def find_finalize_directories(root: Path) -> list[Path]:
    root = Path(root).expanduser().resolve()
    directories = final_hif_archive.find_directories_with_raw(root)
    return _collapse_finalize_directories(directories, root, exclude_panorama=True)


def find_photos_import_directories(root: Path) -> list[Path]:
    root = Path(root).expanduser().resolve()
    directories = final_hif_archive.find_directories_with_raw(root)
    return _collapse_finalize_directories(directories, root, exclude_panorama=False)


def is_panorama_finalize_directory(directory: Path) -> bool:
    directory = Path(directory).expanduser().resolve()
    return (
        directory.name.lower() == "panorama"
        or directory.parent.name.lower() == "panorama"
    )


def _collapse_finalize_directories(
    directories: list[Path],
    root: Path,
    *,
    exclude_panorama: bool,
) -> list[Path]:
    selected: list[Path] = []
    for directory in directories:
        if exclude_panorama and _is_panorama_descendant(directory, root):
            continue
        if any(_is_group_child_of(directory, parent) for parent in selected):
            continue
        selected.append(directory)
    return selected


def _is_panorama_descendant(directory: Path, root: Path) -> bool:
    if is_panorama_finalize_directory(directory):
        return True
    try:
        relative = directory.relative_to(root)
    except ValueError:
        return False
    return "panorama" in (part.lower() for part in relative.parts)


def _is_group_child_of(directory: Path, parent: Path) -> bool:
    try:
        relative = directory.relative_to(parent)
    except ValueError:
        return False
    parts = relative.parts
    return len(parts) >= 2 and parts[0].lower() in {"portrait", "panorama"}


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
    archive_success = True
    if copy_to is not None:
        archive_success = final_hif_archive.process_files(
            base_dir,
            copy_to,
            dry_run=dry_run,
        )
    success = archive_success
    photos_preview = photos_dry_run or dry_run
    if photos_album and (archive_success or photos_preview):
        photos_success = import_exports_to_photos(
            base_dir,
            album=photos_album,
            dry_run=photos_preview,
        )
        success = photos_success and success
    return success
