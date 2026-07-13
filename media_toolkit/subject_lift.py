from __future__ import annotations

import csv
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from media_toolkit import rawpy_tools


PREVIEW_EXTENSIONS = {".hif", ".heif", ".heic"}
CORRECTION_NAME = "Media Toolkit Subject Lift"
PLAN_FIELDS = (
    "path",
    "rating",
    "preview",
    "p01",
    "p50",
    "p95",
    "p99",
    "p999",
    "clip_ratio",
    "shadow_ratio",
    "action",
    "subject_exposure",
    "subject_contrast",
    "subject_highlights",
    "subject_shadows",
    "subject_whites",
    "subject_blacks",
    "rationale",
)


@dataclass(frozen=True)
class PortraitCandidate:
    raw_path: Path
    preview_path: Path
    rating: int


@dataclass(frozen=True)
class SubjectAdjustment:
    path: Path
    rating: int
    action: str
    exposure: float
    contrast: int
    highlights: int
    shadows: int
    whites: int
    blacks: int
    rationale: str


def _numbered_group_dirs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.iterdir() if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
    )


def _previews_by_stem(directory: Path) -> dict[str, list[Path]]:
    previews: dict[str, list[Path]] = {}
    if not directory.is_dir():
        return previews
    for path in sorted(directory.iterdir(), key=lambda item: item.name.casefold()):
        if path.is_file() and path.suffix.casefold() in PREVIEW_EXTENSIONS:
            previews.setdefault(path.stem.casefold(), []).append(path)
    return previews


def discover_candidates(
    root: Path,
    rating_expression: str = ">=3",
) -> list[PortraitCandidate]:
    root = Path(root).resolve()
    candidates: list[PortraitCandidate] = []
    for group_dir in _numbered_group_dirs(root / "portrait"):
        raw_dir = group_dir / "raw"
        previews = _previews_by_stem(group_dir / "hif")
        if not raw_dir.is_dir():
            continue
        raw_files = sorted(
            (
                path
                for path in raw_dir.iterdir()
                if path.is_file() and path.suffix.casefold() in rawpy_tools.RAW_EXTS
            ),
            key=lambda path: path.name.casefold(),
        )
        for raw_path in raw_files:
            rating = rawpy_tools.read_xmp_rating_strict(raw_path.with_suffix(".xmp"))
            if not rawpy_tools.rating_matches(rating, rating_expression):
                continue
            matches = previews.get(raw_path.stem.casefold(), [])
            relative = raw_path.relative_to(root)
            if not matches:
                raise ValueError(f"{relative}: missing HIF/HEIF/HEIC preview")
            if len(matches) > 1:
                raise ValueError(f"{relative}: multiple matching HIF/HEIF/HEIC previews")
            candidates.append(PortraitCandidate(raw_path, matches[0], rating))
    return candidates


def _format_stat(value: float) -> str:
    return f"{value:.6f}".rstrip("0").rstrip(".")


def write_plan_template(
    output: Path,
    root: Path,
    candidates: list[PortraitCandidate],
    stats_by_path: dict[Path, object],
    preview_names: dict[Path, str],
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PLAN_FIELDS, delimiter="\t")
        writer.writeheader()
        for candidate in candidates:
            stats = stats_by_path[candidate.raw_path.resolve()]
            writer.writerow(
                {
                    "path": candidate.raw_path.relative_to(root).as_posix(),
                    "rating": candidate.rating,
                    "preview": preview_names[candidate.raw_path.resolve()],
                    "p01": _format_stat(stats.p01),
                    "p50": _format_stat(stats.p50),
                    "p95": _format_stat(stats.p95),
                    "p99": _format_stat(stats.p99),
                    "p999": _format_stat(stats.p999),
                    "clip_ratio": _format_stat(stats.clip_ratio),
                    "shadow_ratio": _format_stat(stats.shadow_ratio),
                }
            )


ADJUSTMENT_RANGES = {
    "subject_exposure": (0.0, 0.6),
    "subject_contrast": (0, 25),
    "subject_highlights": (-40, 10),
    "subject_shadows": (-10, 35),
    "subject_whites": (-20, 20),
    "subject_blacks": (-25, 10),
}


def _parse_number(row_number: int, row: dict[str, str], field: str) -> float:
    value = row.get(field, "").strip()
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric") from exc
    minimum, maximum = ADJUSTMENT_RANGES[field]
    if not minimum <= number <= maximum:
        raise ValueError(
            f"row {row_number}: {field} out of range {minimum}..{maximum}: {number}"
        )
    return number


def _parse_integer(row_number: int, row: dict[str, str], field: str) -> int:
    number = _parse_number(row_number, row, field)
    if not number.is_integer():
        raise ValueError(f"row {row_number}: {field} must be an integer")
    return int(number)


def read_reviewed_plan(plan_path: Path, root: Path) -> list[SubjectAdjustment]:
    root = Path(root).resolve()
    adjustments: list[SubjectAdjustment] = []
    seen: set[Path] = set()
    with Path(plan_path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if tuple(reader.fieldnames or ()) != PLAN_FIELDS:
            raise ValueError("subject plan has an invalid header")
        for row_number, row in enumerate(reader, start=2):
            relative = Path(row.get("path", "").strip())
            if not relative.as_posix() or relative.is_absolute() or ".." in relative.parts:
                raise ValueError(f"row {row_number}: invalid plan path")
            path = (root / relative).resolve()
            if not path.is_relative_to(root):
                raise ValueError(f"row {row_number}: plan path escapes shoot directory")
            if path in seen:
                raise ValueError(f"duplicate plan path: {relative.as_posix()}")
            seen.add(path)
            try:
                rating = int(row.get("rating", "").strip())
            except ValueError as exc:
                raise ValueError(f"row {row_number}: rating must be an integer") from exc
            action = row.get("action", "").strip().casefold()
            if action not in {"apply", "skip"}:
                raise ValueError(f"row {row_number}: action must be apply or skip")
            rationale = row.get("rationale", "").strip()
            if not rationale:
                raise ValueError(f"row {row_number}: rationale is required")
            exposure = _parse_number(row_number, row, "subject_exposure")
            contrast = _parse_integer(row_number, row, "subject_contrast")
            highlights = _parse_integer(row_number, row, "subject_highlights")
            shadows = _parse_integer(row_number, row, "subject_shadows")
            whites = _parse_integer(row_number, row, "subject_whites")
            blacks = _parse_integer(row_number, row, "subject_blacks")
            values = (exposure, contrast, highlights, shadows, whites, blacks)
            if action == "skip" and any(value != 0 for value in values):
                raise ValueError(f"row {row_number}: skip row must use zero adjustments")
            adjustments.append(
                SubjectAdjustment(
                    path,
                    rating,
                    action,
                    exposure,
                    contrast,
                    highlights,
                    shadows,
                    whites,
                    blacks,
                    rationale,
                )
            )
    return adjustments


def validate_reviewed_plan(
    root: Path,
    adjustments: list[SubjectAdjustment],
    rating_expression: str = ">=3",
) -> list[tuple[PortraitCandidate, SubjectAdjustment]]:
    root = Path(root).resolve()
    candidates = discover_candidates(root, rating_expression)
    candidates_by_path = {candidate.raw_path.resolve(): candidate for candidate in candidates}
    adjustments_by_path = {adjustment.path.resolve(): adjustment for adjustment in adjustments}
    missing = sorted(set(candidates_by_path) - set(adjustments_by_path))
    if missing:
        raise ValueError(f"missing eligible path: {missing[0].relative_to(root)}")
    extra = sorted(set(adjustments_by_path) - set(candidates_by_path))
    if extra:
        try:
            label = extra[0].relative_to(root)
        except ValueError:
            label = extra[0]
        raise ValueError(f"unexpected plan path: {label}")
    pairs = []
    for candidate in candidates:
        adjustment = adjustments_by_path[candidate.raw_path.resolve()]
        if adjustment.rating != candidate.rating:
            raise ValueError(
                f"{candidate.raw_path.relative_to(root)}: rating changed "
                f"({adjustment.rating} -> {candidate.rating})"
            )
        pairs.append((candidate, adjustment))
    return pairs


def _crs(name: str) -> str:
    return f"{{{rawpy_tools.CRS_NS}}}{name}"


def _rdf(name: str) -> str:
    return f"{{{rawpy_tools.RDF_NS}}}{name}"


def _format_local(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in {"", "-0"} else text


def _remove_owned_correction(description: ET.Element) -> tuple[ET.Element | None, ET.Element | None]:
    group = description.find(_crs("MaskGroupBasedCorrections"))
    if group is None:
        return None, None
    sequence = group.find(_rdf("Seq"))
    if sequence is None:
        return group, None
    for item in list(sequence):
        correction = next(
            (child for child in item if child.tag == _rdf("Description")),
            None,
        )
        if correction is not None and correction.get(_crs("CorrectionName")) == CORRECTION_NAME:
            sequence.remove(item)
    if not list(sequence):
        description.remove(group)
        return None, None
    return group, sequence


def _new_id() -> str:
    return uuid.uuid4().hex.upper()


def write_subject_adjustment(
    raw_path: Path,
    adjustment: SubjectAdjustment,
    id_factory: Callable[[], str] = _new_id,
) -> None:
    xmp_path = Path(raw_path).with_suffix(".xmp")
    prefix, root, suffix = rawpy_tools._parse_xmp(
        xmp_path.read_text(encoding="utf-8", errors="strict")
    )
    description = rawpy_tools._xmp_description(root)
    group, sequence = _remove_owned_correction(description)
    if adjustment.action == "apply":
        if group is None:
            group = ET.SubElement(description, _crs("MaskGroupBasedCorrections"))
            sequence = ET.SubElement(group, _rdf("Seq"))
        if sequence is None:
            sequence = ET.SubElement(group, _rdf("Seq"))
        item = ET.SubElement(sequence, _rdf("li"))
        local_values = {
            "LocalExposure2012": adjustment.exposure,
            "LocalContrast2012": adjustment.contrast / 100,
            "LocalHighlights2012": adjustment.highlights / 100,
            "LocalShadows2012": adjustment.shadows / 100,
            "LocalWhites2012": adjustment.whites / 100,
            "LocalBlacks2012": adjustment.blacks / 100,
        }
        attributes = {
            _crs("What"): "Correction",
            _crs("CorrectionAmount"): "1",
            _crs("CorrectionActive"): "true",
            _crs("CorrectionName"): CORRECTION_NAME,
            _crs("CorrectionSyncID"): id_factory(),
            _crs("LocalExposure"): "0",
            _crs("LocalHue"): "0",
            _crs("LocalSaturation"): "0",
            _crs("LocalContrast"): "0",
            _crs("LocalClarity"): "0",
            _crs("LocalSharpness"): "0",
            _crs("LocalBrightness"): "0",
            _crs("LocalToningHue"): "0",
            _crs("LocalToningSaturation"): "0",
            _crs("LocalClarity2012"): "0",
            _crs("LocalDehaze"): "0",
            _crs("LocalLuminanceNoise"): "0",
            _crs("LocalMoire"): "0",
            _crs("LocalDefringe"): "0",
            _crs("LocalTemperature"): "0",
            _crs("LocalTint"): "0",
            _crs("LocalTexture"): "0",
            _crs("LocalGrain"): "0",
            _crs("LocalCurveRefineSaturation"): "100",
        }
        attributes.update(
            {_crs(name): _format_local(value) for name, value in local_values.items()}
        )
        correction = ET.SubElement(item, _rdf("Description"), attributes)
        masks = ET.SubElement(correction, _crs("CorrectionMasks"))
        mask_sequence = ET.SubElement(masks, _rdf("Seq"))
        ET.SubElement(
            mask_sequence,
            _rdf("li"),
            {
                _crs("What"): "Mask/Image",
                _crs("MaskActive"): "true",
                _crs("MaskName"): "Subject 1",
                _crs("MaskBlendMode"): "0",
                _crs("MaskInverted"): "false",
                _crs("MaskSyncID"): id_factory(),
                _crs("MaskValue"): "1",
                _crs("MaskVersion"): "1",
                _crs("MaskSubType"): "1",
                _crs("ReferencePoint"): "0.500000 0.500000",
                _crs("ErrorReason"): "0",
            },
        )
    root_text = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    rawpy_tools._atomic_write_text(xmp_path, f"{prefix}{root_text}{suffix}")
