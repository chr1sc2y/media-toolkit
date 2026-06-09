from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


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
        if stem in seen:
            raise ValueError(f"duplicate stem in manifest: {stem}")
        seen.add(stem)
        entries.append(ManifestEntry(stem, group))

    if not entries:
        raise ValueError("manifest contains no entries")
    return entries


def build_move_plan(root: Path, entries: list[ManifestEntry], target_dir_name: str) -> list[MoveOperation]:
    operations: list[MoveOperation] = []
    for entry in entries:
        raw = root / "raw" / f"{entry.stem}.ARW"
        hif = root / "hif" / f"{entry.stem}.HIF"
        if not raw.exists():
            raise FileNotFoundError(f"missing RAW for {entry.stem}: {raw}")
        if not hif.exists():
            raise FileNotFoundError(f"missing HIF for {entry.stem}: {hif}")

        raw_dest = root / target_dir_name / entry.group / "raw" / raw.name
        hif_dest = root / target_dir_name / entry.group / "hif" / hif.name
        for destination in (raw_dest, hif_dest):
            if destination.exists():
                raise FileExistsError(f"destination already exists: {destination}")
        operations.append(MoveOperation(raw, raw_dest))
        operations.append(MoveOperation(hif, hif_dest))
    return operations


def apply_move_plan(operations: list[MoveOperation]) -> None:
    for operation in operations:
        operation.destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(operation.source), str(operation.destination))


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
