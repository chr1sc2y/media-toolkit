from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import re

from media_toolkit.rawpy_tools import RAW_EXTS

RAW_EXTENSIONS = frozenset(RAW_EXTS)
HIF_EXTENSIONS = {".hif", ".heif", ".heic"}
XMP_EXTENSIONS = {".xmp"}
EXPORT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".dng",
    ".heif",
    ".heic",
}
GROUP_RE = re.compile(r"[1-9][0-9]*\Z")


class ManifestEntry:
    def __init__(self, stem: str, group: str):
        self.stem = stem
        self.group = group


class MoveOperation:
    def __init__(self, source: Path, destination: Path):
        self.source = source
        self.destination = destination


def read_manifest(path: Path) -> list[ManifestEntry]:
    if not path.exists():
        raise FileNotFoundError(f"manifest not found: {path}")

    entries: list[ManifestEntry] = []
    seen: set[str] = set()
    for row_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        if not line.strip():
            continue
        delimiter = "\t" if "\t" in line else ","
        values = [value.strip() for value in line.split(delimiter)]
        if not values or not any(values):
            continue
        if values[0].lower() == "stem":
            continue
        if len(values) < 2 or not values[0]:
            raise ValueError(f"invalid manifest row {row_number}: expected stem and group")
        stem, group = values[0], values[1]
        if not group:
            continue
        stem_key = stem.casefold()
        if stem_key in seen:
            raise ValueError(f"duplicate stem in manifest: {stem}")
        _validate_manifest_values(stem, group)
        seen.add(stem_key)
        entries.append(ManifestEntry(stem, group))

    if not entries:
        raise ValueError("manifest contains no entries")
    return entries


def _validate_manifest_values(stem: str, group: str) -> None:
    if (
        not stem
        or stem in {".", ".."}
        or Path(stem).name != stem
        or "/" in stem
        or "\\" in stem
    ):
        raise ValueError(f"invalid stem in manifest: {stem!r}")
    if not GROUP_RE.fullmatch(group):
        raise ValueError(
            f"invalid group for {stem}: {group!r}; expected a positive integer"
        )


def _matching_files(
    directory: Path,
    stem: str,
    extensions: set[str],
    *,
    recursive: bool = False,
) -> list[Path]:
    if not directory.is_dir():
        return []
    candidates = directory.rglob("*") if recursive else directory.iterdir()
    return sorted(
        path
        for path in candidates
        if path.is_file()
        and path.stem.casefold() == stem.casefold()
        and path.suffix.casefold() in extensions
    )


def _required_single_file(
    directory: Path,
    stem: str,
    extensions: set[str],
    label: str,
) -> Path:
    matches = _matching_files(directory, stem, extensions)
    if not matches:
        expected = "/".join(sorted(extensions))
        raise FileNotFoundError(
            f"missing {label} for {stem}: {directory}/*[{expected}]"
        )
    if len(matches) > 1:
        raise ValueError(
            f"ambiguous {label} for {stem}: "
            + ", ".join(str(path) for path in matches)
        )
    return matches[0]


def build_move_plan(
    root: Path,
    entries: list[ManifestEntry],
    target_dir_name: str,
) -> list[MoveOperation]:
    if target_dir_name not in {"portrait", "panorama"}:
        raise ValueError(f"invalid target directory kind: {target_dir_name!r}")
    operations: list[MoveOperation] = []
    planned_destinations: set[Path] = set()
    planned_sources: set[Path] = set()
    seen_stems: set[str] = set()
    for entry in entries:
        _validate_manifest_values(entry.stem, entry.group)
        stem_key = entry.stem.casefold()
        if stem_key in seen_stems:
            raise ValueError(f"duplicate stem in manifest: {entry.stem}")
        seen_stems.add(stem_key)
        raw_dir = root / "raw"
        hif_dir = root / "hif"
        raw = _required_single_file(
            raw_dir, entry.stem, RAW_EXTENSIONS, "RAW"
        )
        hif = _required_single_file(
            hif_dir, entry.stem, HIF_EXTENSIONS, "HIF"
        )
        group_root = root / target_dir_name / entry.group
        sources_and_destinations = [
            (raw, group_root / "raw" / raw.name),
            (hif, group_root / "hif" / hif.name),
        ]

        sidecars = _matching_files(raw_dir, entry.stem, XMP_EXTENSIONS)
        if len(sidecars) > 1:
            raise ValueError(
                f"ambiguous XMP for {entry.stem}: "
                + ", ".join(str(path) for path in sidecars)
            )
        if sidecars:
            sidecar = sidecars[0]
            sources_and_destinations.append(
                (sidecar, group_root / "raw" / sidecar.name)
            )

        export_root = raw_dir / "Export"
        for export in _matching_files(
            export_root,
            entry.stem,
            EXPORT_EXTENSIONS,
            recursive=True,
        ):
            relative = export.relative_to(export_root)
            sources_and_destinations.append(
                (export, group_root / "raw" / "Export" / relative)
            )

        for source, destination in sources_and_destinations:
            if destination.exists():
                raise FileExistsError(f"destination already exists: {destination}")
            if destination in planned_destinations:
                raise ValueError(f"destination planned more than once: {destination}")
            source_key = source.resolve()
            if source_key in planned_sources:
                raise ValueError(f"source planned more than once: {source}")
            planned_sources.add(source_key)
            planned_destinations.add(destination)
            operations.append(MoveOperation(source, destination))
    return operations


def apply_move_plan(operations: list[MoveOperation]) -> None:
    completed: list[MoveOperation] = []
    try:
        for operation in operations:
            operation.destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(operation.source), str(operation.destination))
            completed.append(operation)
    except OSError as exc:
        rollback_failures: list[str] = []
        for operation in reversed(completed):
            try:
                if not operation.destination.exists():
                    rollback_failures.append(
                        f"missing moved destination {operation.destination}"
                    )
                    continue
                operation.source.parent.mkdir(parents=True, exist_ok=True)
                if operation.source.exists():
                    operation.destination.unlink()
                else:
                    shutil.move(str(operation.destination), str(operation.source))
            except OSError as rollback_exc:
                rollback_failures.append(
                    f"{operation.destination} -> {operation.source}: {rollback_exc}"
                )
        if rollback_failures:
            raise RuntimeError(
                f"move failed: {exc}; rollback incomplete: "
                + "; ".join(rollback_failures)
            ) from exc
        raise RuntimeError(
            f"move failed: {exc}; rolled back {len(completed)} completed move(s)"
        ) from exc


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True)


def summarize(entries: list[ManifestEntry], target_dir_name: str) -> str:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.group] = counts.get(entry.group, 0) + 1
    groups = ", ".join(
        f"{target_dir_name}/{group}={count}" for group, count in sorted(counts.items())
    )
    return f"{len(entries)} pair(s): {groups}"
