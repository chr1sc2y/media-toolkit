from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from statistics import mean
from typing import Any

from PIL import Image

from media_toolkit.final_hif_archive import (
    EXPORT_EXTS,
    child_dir_case_insensitive,
    display_relative,
    find_directories_with_raw,
)

HIF_EXTS = {".hif", ".heif", ".heic"}
RAW_EXTS = {".arw", ".cr2", ".cr3", ".dng", ".nef", ".orf", ".raf", ".raw", ".rw2"}


class HifPruneMode(str, Enum):
    PLAN = "plan"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class HifPruneItem:
    path: Path
    action: str
    reason: str
    representative: Path | None = None


@dataclass(frozen=True)
class HifPrunePlan:
    root: Path
    keep: list[HifPruneItem]
    delete: list[HifPruneItem]
    warnings: list[HifPruneItem]


@dataclass(frozen=True)
class HifPruneResult:
    manifest_path: Path
    deleted_count: int
    planned_delete_count: int


@dataclass(frozen=True)
class _ImageFingerprint:
    bits: tuple[int, ...]
    average_rgb: tuple[float, float, float]


def build_prune_plan(root: Path) -> HifPrunePlan:
    root = Path(root).expanduser().resolve()
    protected_stems = _protected_export_stems(root)
    files = _collect_source_hifs(root)
    keep: list[HifPruneItem] = []
    delete: list[HifPruneItem] = []
    warnings: list[HifPruneItem] = []
    representatives: list[tuple[Path, _ImageFingerprint]] = []

    for file_path in files:
        stem = file_path.stem.lower()
        protected_reason = _protected_reason(root, file_path, protected_stems)
        fingerprint = _fingerprint(file_path)
        if fingerprint is None:
            warnings.append(
                HifPruneItem(
                    path=file_path,
                    action="keep",
                    reason="unreadable-image-kept",
                )
            )
            continue
        if protected_reason is not None:
            keep.append(HifPruneItem(path=file_path, action="keep", reason=protected_reason))
            representatives.append((file_path, fingerprint))
            continue

        duplicate = _find_duplicate_representative(file_path, fingerprint, representatives)
        if duplicate is not None:
            delete.append(
                HifPruneItem(
                    path=file_path,
                    action="delete",
                    reason="near-duplicate-hif-only",
                    representative=duplicate,
                )
            )
            continue

        keep.append(HifPruneItem(path=file_path, action="keep", reason="hif-only-representative"))
        representatives.append((file_path, fingerprint))

    return HifPrunePlan(root=root, keep=keep, delete=delete, warnings=warnings)


def execute_prune_plan(
    plan: HifPrunePlan,
    *,
    mode: HifPruneMode,
    manifest_path: Path | None = None,
    dry_run: bool = False,
) -> HifPruneResult:
    manifest_path = (
        Path(manifest_path)
        if manifest_path is not None
        else plan.root / "hif_prune_manifest.json"
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    deleted_count = 0
    delete_items = []

    for item in plan.delete:
        action = "would-delete" if dry_run or mode == HifPruneMode.PLAN else "deleted"
        if action == "deleted":
            item.path.unlink()
            deleted_count += 1
        delete_items.append(_item_to_dict(plan.root, item, action=action))

    payload = {
        "mode": mode.value,
        "dry_run": dry_run,
        "root": str(plan.root),
        "planned_delete_count": len(plan.delete),
        "deleted_count": deleted_count,
        "keep": [_item_to_dict(plan.root, item) for item in plan.keep],
        "delete": delete_items,
        "warnings": [_item_to_dict(plan.root, item) for item in plan.warnings],
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    _write_tsv_manifest(manifest_path.with_suffix(".tsv"), payload)
    return HifPruneResult(
        manifest_path=manifest_path,
        deleted_count=deleted_count,
        planned_delete_count=len(plan.delete),
    )


def _collect_source_hifs(root: Path) -> list[Path]:
    files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in HIF_EXTS
        and any(part.lower() == "hif" for part in path.relative_to(root).parts[:-1])
    ]
    return sorted(files, key=lambda path: str(path.relative_to(root)).lower())


def _protected_export_stems(root: Path) -> set[str]:
    stems: set[str] = set()
    bases = find_directories_with_raw(root)
    if not bases and (root / "raw").is_dir():
        bases = [root]
    for base in bases:
        for export_dir in _export_dirs_for_base(base):
            try:
                for file_path in export_dir.iterdir():
                    if file_path.is_file() and file_path.suffix.lower() in EXPORT_EXTS:
                        stems.add(file_path.stem.lower())
            except (FileNotFoundError, PermissionError):
                continue
    return stems


def _export_dirs_for_base(base: Path) -> list[Path]:
    export_dirs: list[Path] = []
    root_export = base / "raw" / "Export"
    for path in (root_export, child_dir_case_insensitive(root_export, "Pixcake")):
        if path.is_dir():
            export_dirs.append(path)
    portrait_root = base / "portrait"
    if portrait_root.is_dir():
        for child in sorted(portrait_root.iterdir()):
            export_dir = child / "raw" / "Export"
            for path in (export_dir, child_dir_case_insensitive(export_dir, "Pixcake")):
                if path.is_dir():
                    export_dirs.append(path)
    return export_dirs


def _protected_reason(root: Path, file_path: Path, protected_stems: set[str]) -> str | None:
    if _is_panorama_hif(root, file_path):
        return "panorama-source-hif"
    if file_path.stem.lower() in protected_stems:
        return "export-selected-hif"
    if _has_sibling_raw(file_path):
        return "raw-backed-hif"
    return None


def _is_panorama_hif(root: Path, file_path: Path) -> bool:
    parts = tuple(part.lower() for part in file_path.relative_to(root).parts)
    return "panorama" in parts and "hif" in parts


def _has_sibling_raw(file_path: Path) -> bool:
    if file_path.parent.name.lower() != "hif":
        return False
    raw_dir = file_path.parent.parent / "raw"
    if not raw_dir.is_dir():
        return False
    stem = file_path.stem.lower()
    return any(
        candidate.is_file()
        and candidate.stem.lower() == stem
        and candidate.suffix.lower() in RAW_EXTS
        for candidate in raw_dir.iterdir()
    )


def _fingerprint(file_path: Path) -> _ImageFingerprint | None:
    try:
        with Image.open(file_path) as image:
            rgb = image.convert("RGB")
            tiny = rgb.resize((8, 8)).convert("L")
            values = list(tiny.getdata())
            threshold = mean(values)
            bits = tuple(1 if value >= threshold else 0 for value in values)
            color = rgb.resize((1, 1)).getpixel((0, 0))
            return _ImageFingerprint(
                bits=bits,
                average_rgb=(float(color[0]), float(color[1]), float(color[2])),
            )
    except Exception:
        return None


def _find_duplicate_representative(
    file_path: Path,
    fingerprint: _ImageFingerprint,
    representatives: list[tuple[Path, _ImageFingerprint]],
) -> Path | None:
    for representative, representative_fingerprint in reversed(representatives[-8:]):
        if not _nearby_filename(file_path, representative):
            continue
        if _similar(fingerprint, representative_fingerprint, strict=_is_portrait_path(file_path)):
            return representative
    return None


def _nearby_filename(left: Path, right: Path) -> bool:
    left_number = _numeric_suffix(left.stem)
    right_number = _numeric_suffix(right.stem)
    if left_number is None or right_number is None:
        return left.parent == right.parent
    return abs(left_number - right_number) <= 3


def _numeric_suffix(value: str) -> int | None:
    match = re.search(r"(\d+)$", value)
    if match is None:
        return None
    return int(match.group(1))


def _is_portrait_path(path: Path) -> bool:
    return any(part.lower() == "portrait" for part in path.parts)


def _similar(
    left: _ImageFingerprint,
    right: _ImageFingerprint,
    *,
    strict: bool,
) -> bool:
    bit_distance = sum(1 for left_bit, right_bit in zip(left.bits, right.bits) if left_bit != right_bit)
    color_distance = sum(
        abs(left_value - right_value)
        for left_value, right_value in zip(left.average_rgb, right.average_rgb)
    ) / 3
    return bit_distance <= (1 if strict else 3) and color_distance <= (6 if strict else 14)


def _item_to_dict(root: Path, item: HifPruneItem, *, action: str | None = None) -> dict[str, Any]:
    payload = {
        "path": display_relative(root, item.path),
        "action": action if action is not None else item.action,
        "reason": item.reason,
    }
    if item.representative is not None:
        payload["representative"] = display_relative(root, item.representative)
    return payload


def _write_tsv_manifest(path: Path, payload: dict[str, Any]) -> None:
    lines = ["action\treason\tpath\trepresentative"]
    for group in ("keep", "delete", "warnings"):
        for item in payload[group]:
            lines.append(
                "\t".join(
                    [
                        item["action"],
                        item["reason"],
                        item["path"],
                        item.get("representative", ""),
                    ]
                )
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
