from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path, PurePosixPath
from statistics import mean
from typing import Any, Optional

from PIL import Image

from media_toolkit.final_hif_archive import (
    EXPORT_EXTS,
    child_dir_case_insensitive,
    find_directories_with_raw,
)
from media_toolkit.rawpy_tools import RAW_EXTS

HIF_EXTS = {".hif", ".heif", ".heic"}


class HifPruneMode(str, Enum):
    PLAN = "plan"
    AGGRESSIVE = "aggressive"


@dataclass(frozen=True)
class HifPruneItem:
    path: Path
    action: str
    reason: str
    representative: Optional[Path] = None


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


class PrunePlanValidationError(RuntimeError):
    """Raised before deletion when a reviewed plan is stale or unsafe."""


class PruneExecutionError(RuntimeError):
    """Raised after a deletion attempt fails and the audit is updated."""


PLAN_SCHEMA = "media-toolkit/hif-prune-plan"
EXECUTION_SCHEMA = "media-toolkit/hif-prune-execution"
SCHEMA_VERSION = 1


def build_prune_plan(root: Path) -> HifPrunePlan:
    root = Path(root).expanduser().resolve()
    heif_decoder_available()
    protected_stems = _protected_export_stems(root)
    files = _collect_source_hifs(root)
    keep: list[HifPruneItem] = []
    delete: list[HifPruneItem] = []
    warnings = [
        HifPruneItem(
            path=file_path,
            action="keep",
            reason="noncanonical-hif-kept",
        )
        for file_path in _collect_noncanonical_hifs(root, set(files))
    ]
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
    manifest_path: Optional[Path] = None,
    dry_run: bool = False,
    confirmed: bool = False,
) -> HifPruneResult:
    del confirmed
    if mode != HifPruneMode.PLAN:
        raise ValueError(
            "aggressive HIF pruning must apply a reviewed JSON plan; "
            "use apply_reviewed_prune_plan"
        )

    manifest_path = (
        Path(manifest_path)
        if manifest_path is not None
        else plan.root / "hif_prune_manifest.json"
    )
    payload = {
        "schema": PLAN_SCHEMA,
        "version": SCHEMA_VERSION,
        "status": "review-required",
        "created_at": _utc_now(),
        "mode": mode.value,
        "dry_run": dry_run,
        "root": str(plan.root),
        "planned_delete_count": len(plan.delete),
        "deleted_count": 0,
        "keep": [_item_to_plan_dict(plan.root, item) for item in plan.keep],
        "delete": [
            _item_to_plan_dict(plan.root, item, action="would-delete")
            for item in plan.delete
        ],
        "warnings": [_item_to_plan_dict(plan.root, item) for item in plan.warnings],
    }
    _atomic_write_json(manifest_path, payload)
    _write_tsv_manifest(manifest_path.with_suffix(".tsv"), payload)
    return HifPruneResult(
        manifest_path=manifest_path,
        deleted_count=0,
        planned_delete_count=len(plan.delete),
    )


def apply_reviewed_prune_plan(
    reviewed_manifest_path: Path,
    *,
    root: Path,
    manifest_path: Optional[Path] = None,
    confirmed: bool = False,
) -> HifPruneResult:
    if not confirmed:
        raise ValueError("aggressive HIF pruning requires explicit confirmation")
    if not heif_decoder_available():
        raise RuntimeError(
            "aggressive HIF pruning requires an installed Pillow HEIF decoder"
        )

    root = Path(root).expanduser().resolve()
    reviewed_manifest_path = Path(reviewed_manifest_path).expanduser().resolve()
    reviewed_bytes = reviewed_manifest_path.read_bytes()
    reviewed_payload = json.loads(reviewed_bytes.decode("utf-8"))
    if manifest_path is None:
        manifest_path = reviewed_manifest_path.with_name(
            reviewed_manifest_path.stem + ".execution.json"
        )
    else:
        manifest_path = Path(manifest_path).expanduser().resolve()
    if manifest_path in {
        reviewed_manifest_path,
        reviewed_manifest_path.with_suffix(".tsv"),
    }:
        raise ValueError(
            "execution manifest must not overwrite the reviewed plan or its TSV"
        )

    raw_delete = (
        reviewed_payload.get("delete", [])
        if isinstance(reviewed_payload, dict)
        else []
    )
    audit_items = _execution_audit_items(raw_delete)
    audit = {
        "schema": EXECUTION_SCHEMA,
        "version": SCHEMA_VERSION,
        "status": "validating",
        "started_at": _utc_now(),
        "completed_at": None,
        "root": str(root),
        "source_plan": str(reviewed_manifest_path),
        "source_plan_sha256": hashlib.sha256(reviewed_bytes).hexdigest(),
        "planned_delete_count": len(audit_items),
        "deleted_count": 0,
        "errors": [],
        "delete": audit_items,
    }

    validated, errors = _validate_reviewed_plan(reviewed_payload, root)
    if errors:
        audit["status"] = "validation-failed"
        audit["completed_at"] = _utc_now()
        audit["errors"] = errors
        _atomic_write_json(manifest_path, audit)
        raise PrunePlanValidationError("; ".join(errors))

    audit["status"] = "in-progress"
    _atomic_write_json(manifest_path, audit)
    deleted_count = 0
    for index, candidate in enumerate(validated):
        try:
            candidate.unlink()
        except OSError as exc:
            audit_items[index]["status"] = "failed"
            audit_items[index]["error"] = f"{type(exc).__name__}: {exc}"
            audit["status"] = "partial-failure" if deleted_count else "failed"
            audit["completed_at"] = _utc_now()
            audit["errors"].append(
                f"delete failed for {audit_items[index]['path']}: "
                f"{type(exc).__name__}: {exc}"
            )
            _atomic_write_json(manifest_path, audit)
            raise PruneExecutionError(audit["errors"][-1]) from exc

        deleted_count += 1
        audit_items[index]["status"] = "deleted"
        audit_items[index]["deleted_at"] = _utc_now()
        audit["deleted_count"] = deleted_count
        _atomic_write_json(manifest_path, audit)

    audit["status"] = "completed"
    audit["completed_at"] = _utc_now()
    _atomic_write_json(manifest_path, audit)
    return HifPruneResult(
        manifest_path=manifest_path,
        deleted_count=deleted_count,
        planned_delete_count=len(validated),
    )


def _collect_source_hifs(root: Path) -> list[Path]:
    files: set[Path] = set()
    for directory in _canonical_hif_directories(root):
        try:
            files.update(
                path
                for path in directory.iterdir()
                if path.is_file()
                and not path.is_symlink()
                and path.suffix.lower() in HIF_EXTS
            )
        except (FileNotFoundError, PermissionError):
            continue
    return sorted(files, key=lambda path: str(path.relative_to(root)).lower())


def _canonical_hif_directories(root: Path) -> list[Path]:
    candidates = find_directories_with_raw(root)
    if (root / "hif").is_dir() and root not in candidates:
        candidates.append(root)
    candidates.sort(key=lambda path: (len(path.relative_to(root).parts), str(path)))

    bases = [
        candidate
        for candidate in candidates
        if not _is_group_descendant(root, candidate)
    ]

    directories: set[Path] = set()
    for base in bases:
        direct = base / "hif"
        if direct.is_dir():
            directories.add(direct)
        for group_name in ("portrait", "panorama"):
            group_root = base / group_name
            try:
                children = list(group_root.iterdir())
            except (FileNotFoundError, PermissionError):
                continue
            for child in children:
                grouped = child / "hif"
                if child.is_dir() and grouped.is_dir():
                    directories.add(grouped)
    return sorted(directories, key=lambda path: str(path.relative_to(root)).lower())


def _is_group_descendant(root: Path, path: Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return True
    return any(part.lower() in {"portrait", "panorama"} for part in parts)


def _collect_noncanonical_hifs(root: Path, canonical: set[Path]) -> list[Path]:
    canonical_resolved = {path.resolve() for path in canonical}
    files = []
    for path in root.rglob("*"):
        if (
            not path.is_file()
            or path.is_symlink()
            or path.suffix.lower() not in HIF_EXTS
        ):
            continue
        relative = path.relative_to(root)
        if not any(part.lower() == "hif" for part in relative.parts[:-1]):
            continue
        if path.resolve() not in canonical_resolved:
            files.append(path)
    return sorted(files, key=lambda path: str(path.relative_to(root)).lower())


def heif_decoder_available() -> bool:
    if _registered_heif_decoder_available():
        return True
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except Exception:
        return False
    return _registered_heif_decoder_available()


def _registered_heif_decoder_available() -> bool:
    registered = Image.registered_extensions()
    return any(
        str(registered.get(extension, "")).upper() in {"HEIF", "HEIC"}
        for extension in HIF_EXTS
    )


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


def _protected_reason(
    root: Path,
    file_path: Path,
    protected_stems: set[str],
) -> Optional[str]:
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


def _fingerprint(file_path: Path) -> Optional[_ImageFingerprint]:
    try:
        with Image.open(file_path) as image:
            rgb = image.convert("RGB")
            tiny = rgb.resize((8, 8)).convert("L")
            flattened = getattr(tiny, "get_flattened_data", None)
            values = list(flattened() if flattened is not None else tiny.getdata())
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
) -> Optional[Path]:
    for representative, representative_fingerprint in reversed(representatives[-8:]):
        if not _nearby_filename(file_path, representative):
            continue
        if _similar(fingerprint, representative_fingerprint, strict=_is_portrait_path(file_path)):
            return representative
    return None


def _nearby_filename(left: Path, right: Path) -> bool:
    if left.parent != right.parent:
        return False
    left_number = _numeric_suffix(left.stem)
    right_number = _numeric_suffix(right.stem)
    if left_number is None or right_number is None:
        return True
    return abs(left_number - right_number) <= 3


def _numeric_suffix(value: str) -> Optional[int]:
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


def _item_to_plan_dict(
    root: Path,
    item: HifPruneItem,
    *,
    action: Optional[str] = None,
) -> dict[str, Any]:
    payload = _identity_record(root, item.path)
    payload.update({
        "action": action if action is not None else item.action,
        "reason": item.reason,
    })
    if item.representative is not None:
        payload["representative"] = _identity_record(root, item.representative)
    return payload


def _identity_record(root: Path, path: Path) -> dict[str, Any]:
    relative = _safe_relative_path(root, path)
    stat_before = path.stat()
    sha256 = _sha256_file(path)
    stat_after = path.stat()
    if (
        stat_before.st_size != stat_after.st_size
        or stat_before.st_mtime_ns != stat_after.st_mtime_ns
    ):
        raise OSError(f"file changed while recording plan identity: {relative}")
    return {
        "path": relative,
        "size": stat_after.st_size,
        "sha256": sha256,
    }


def _safe_relative_path(root: Path, path: Path) -> str:
    root = root.resolve()
    path = path.resolve(strict=True)
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path is outside prune root: {path}") from exc
    if not relative.parts:
        raise ValueError("file path cannot equal prune root")
    return relative.as_posix()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _execution_audit_items(raw_delete: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_delete, list):
        return []
    items = []
    for record in raw_delete:
        path = record.get("path") if isinstance(record, dict) else None
        representative = record.get("representative") if isinstance(record, dict) else None
        representative_path = (
            representative.get("path") if isinstance(representative, dict) else None
        )
        items.append(
            {
                "path": path if isinstance(path, str) else "<invalid>",
                "representative": (
                    representative_path
                    if isinstance(representative_path, str)
                    else "<invalid>"
                ),
                "status": "not-attempted",
            }
        )
    return items


def _validate_reviewed_plan(
    payload: Any,
    root: Path,
) -> tuple[list[Path], list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [], ["reviewed plan must be a JSON object"]
    if payload.get("schema") != PLAN_SCHEMA:
        errors.append(f"unexpected plan schema: {payload.get('schema')!r}")
    if payload.get("version") != SCHEMA_VERSION:
        errors.append(f"unsupported plan version: {payload.get('version')!r}")
    if payload.get("status") != "review-required":
        errors.append(f"plan status is not review-required: {payload.get('status')!r}")
    if payload.get("mode") != HifPruneMode.PLAN.value:
        errors.append(f"reviewed manifest is not a plan: {payload.get('mode')!r}")

    recorded_root = payload.get("root")
    if not isinstance(recorded_root, str):
        errors.append("plan root must be a string")
    else:
        try:
            if Path(recorded_root).expanduser().resolve() != root:
                errors.append(
                    f"plan root does not match requested root: {recorded_root!r}"
                )
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"invalid plan root: {exc}")

    raw_delete = payload.get("delete")
    if not isinstance(raw_delete, list):
        errors.append("plan delete field must be a list")
        return [], errors
    if payload.get("planned_delete_count") != len(raw_delete):
        errors.append("planned_delete_count does not match delete records")

    current_sources = {path.resolve() for path in _collect_source_hifs(root)}
    protected_stems = _protected_export_stems(root)
    validated: list[Path] = []
    relationships: list[tuple[int, Path, Path]] = []
    seen: set[Path] = set()
    for index, record in enumerate(raw_delete):
        prefix = f"delete[{index}]"
        if not isinstance(record, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if record.get("action") != "would-delete":
            errors.append(f"{prefix} action must be would-delete")
        if record.get("reason") != "near-duplicate-hif-only":
            errors.append(f"{prefix} has unexpected delete reason")
        try:
            candidate = _resolve_reviewed_path(root, record.get("path"))
            _validate_hif_identity(prefix, record, candidate, current_sources)
            protected_reason = _protected_reason(root, candidate, protected_stems)
            if protected_reason is not None:
                raise ValueError(f"file is now protected: {protected_reason}")
            if candidate in seen:
                raise ValueError("duplicate delete path")

            representative_record = record.get("representative")
            if not isinstance(representative_record, dict):
                raise ValueError("representative identity is missing")
            representative = _resolve_reviewed_path(
                root, representative_record.get("path")
            )
            _validate_hif_identity(
                f"{prefix}.representative",
                representative_record,
                representative,
                current_sources,
            )
            if representative == candidate:
                raise ValueError("representative must differ from delete candidate")
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"{prefix}: {exc}")
            continue

        seen.add(candidate)
        validated.append(candidate)
        relationships.append((index, candidate, representative))

    delete_paths = set(validated)
    for index, _candidate, representative in relationships:
        if representative in delete_paths:
            errors.append(
                f"delete[{index}]: representative is also a delete candidate"
            )
    return validated, errors


def _resolve_reviewed_path(root: Path, value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError("path must be a non-empty string")
    if "\\" in value:
        raise ValueError("path must use forward slashes")
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("path must be a normalized relative path")
    relative = PurePosixPath(value)
    if relative.is_absolute():
        raise ValueError("path must be relative")

    lexical = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlinked paths are not allowed")
    resolved = lexical.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("path escapes prune root") from exc
    if not resolved.is_file():
        raise ValueError("path is not a regular file")
    return resolved


def _validate_hif_identity(
    prefix: str,
    record: dict[str, Any],
    path: Path,
    current_sources: set[Path],
) -> None:
    if path.suffix.lower() not in HIF_EXTS:
        raise ValueError(f"{prefix} is not a HIF/HEIF/HEIC file")
    if path not in current_sources:
        raise ValueError(f"{prefix} is not in a canonical workflow HIF directory")
    size = record.get("size")
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise ValueError(f"{prefix} size is invalid")
    sha256 = record.get("sha256")
    if not isinstance(sha256, str) or re.fullmatch(r"[0-9a-f]{64}", sha256) is None:
        raise ValueError(f"{prefix} sha256 is invalid")
    current_size = path.stat().st_size
    if current_size != size:
        raise ValueError(
            f"{prefix} size changed (planned {size}, current {current_size})"
        )
    current_sha256 = _sha256_file(path)
    if current_sha256 != sha256:
        raise ValueError(f"{prefix} sha256 changed")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    _atomic_write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
    )


def _atomic_write_text(path: Path, content: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, str(path))
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


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
                        item.get("representative", {}).get("path", "")
                        if isinstance(item.get("representative"), dict)
                        else "",
                    ]
                )
            )
    _atomic_write_text(path, "\n".join(lines) + "\n")
