from __future__ import annotations

import csv
import io
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image

from media_toolkit.style_profiles import lr_style_profiles


RAW_EXTS = {
    ".3fr",
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
}

XMPMETA_NS = "adobe:ns:meta/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
XMP_NS = "http://ns.adobe.com/xap/1.0/"
CRS_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"
PHOTOSHOP_NS = "http://ns.adobe.com/photoshop/1.0/"
DC_NS = "http://purl.org/dc/elements/1.1/"
XMPMM_NS = "http://ns.adobe.com/xap/1.0/mm/"

XMP_NAMESPACES = {
    "x": XMPMETA_NS,
    "rdf": RDF_NS,
    "xmp": XMP_NS,
    "crs": CRS_NS,
    "photoshop": PHOTOSHOP_NS,
    "dc": DC_NS,
    "xmpMM": XMPMM_NS,
}

for _prefix, _uri in XMP_NAMESPACES.items():
    ET.register_namespace(_prefix, _uri)

RAW_XMP_FORMATS = {
    ".arw": "image/x-sony-arw",
    ".cr2": "image/x-canon-cr2",
    ".cr3": "image/x-canon-cr3",
    ".dng": "image/x-adobe-dng",
    ".nef": "image/x-nikon-nef",
    ".orf": "image/x-olympus-orf",
    ".raf": "image/x-fuji-raf",
    ".rw2": "image/x-panasonic-rw2",
}


@dataclass(frozen=True)
class RawStats:
    path: Path
    stem: str
    width: int
    height: int
    black_level: int
    white_level: int
    p01: float
    p50: float
    p95: float
    p99: float
    p999: float
    clip_ratio: float
    shadow_ratio: float
    channel_clip_ratios: dict[str, float]
    camera_wb: list[float]
    daylight_wb: list[float]


@dataclass(frozen=True)
class LrPlan:
    path: Path
    stem: str
    rating: int | None
    exposure2012: float
    highlights2012: int
    shadows2012: int
    whites2012: int
    blacks2012: int
    contrast2012: int
    rationale: str
    plan_style: str = "travel"


def _default_imread():
    import rawpy

    return rawpy.imread


def _rawpy_srgb_colorspace():
    import rawpy

    return rawpy.ColorSpace.sRGB


def _as_float_list(value: object) -> list[float]:
    if value is None:
        return []
    return [float(item) for item in value]


def _format_float(value: float) -> str:
    return f"{value:.6f}"


def _format_float_list(values: Iterable[float]) -> str:
    return ",".join(f"{value:.6f}" for value in values)


def _format_channel_ratios(values: dict[str, float]) -> str:
    return ",".join(f"{key}:{values[key]:.6f}" for key in sorted(values, key=str))


def _black_level(raw) -> int:
    levels = getattr(raw, "black_level_per_channel", None) or [0]
    return int(min(levels))


def _white_level(raw) -> int:
    per_channel = getattr(raw, "camera_white_level_per_channel", None)
    if per_channel:
        return int(min(per_channel))
    return int(getattr(raw, "white_level"))


def analyze_raw(
    path: Path,
    *,
    imread: Callable[[str], object] | None = None,
) -> RawStats:
    reader = imread or _default_imread()
    with reader(str(path)) as raw:
        image = np.asarray(raw.raw_image_visible, dtype=np.float64)
        black = _black_level(raw)
        white = _white_level(raw)
        usable_range = max(1, white - black)
        normalized = np.clip((image - black) / usable_range, 0.0, 1.0)

        p01, p50, p95, p99, p999 = np.percentile(
            normalized,
            [1, 50, 95, 99, 99.9],
        )
        clip_mask = normalized >= 0.995
        shadow_mask = normalized <= 0.005
        colors = getattr(raw, "raw_colors_visible", None)
        channel_clip_ratios: dict[str, float] = {}
        if colors is not None:
            color_array = np.asarray(colors)
            for channel in sorted(np.unique(color_array).tolist()):
                mask = color_array == channel
                total = int(mask.sum())
                if total:
                    channel_clip_ratios[str(int(channel))] = float((clip_mask & mask).sum() / total)

        height, width = normalized.shape[:2]
        return RawStats(
            path=Path(path),
            stem=Path(path).stem,
            width=int(width),
            height=int(height),
            black_level=black,
            white_level=white,
            p01=float(p01),
            p50=float(p50),
            p95=float(p95),
            p99=float(p99),
            p999=float(p999),
            clip_ratio=float(clip_mask.mean()),
            shadow_ratio=float(shadow_mask.mean()),
            channel_clip_ratios=channel_clip_ratios,
            camera_wb=_as_float_list(getattr(raw, "camera_whitebalance", None)),
            daylight_wb=_as_float_list(getattr(raw, "daylight_whitebalance", None)),
        )


def write_raw_stats_tsv(output: Path, stats: list[RawStats], *, root: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "path",
        "stem",
        "width",
        "height",
        "black_level",
        "white_level",
        "p01",
        "p50",
        "p95",
        "p99",
        "p999",
        "clip_ratio",
        "shadow_ratio",
        "channel_clip_ratios",
        "camera_wb",
        "daylight_wb",
    ]
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for item in stats:
            try:
                rel_path = item.path.resolve().relative_to(root.resolve())
            except ValueError:
                rel_path = item.path
            writer.writerow(
                {
                    "path": str(rel_path),
                    "stem": item.stem,
                    "width": item.width,
                    "height": item.height,
                    "black_level": item.black_level,
                    "white_level": item.white_level,
                    "p01": _format_float(item.p01),
                    "p50": _format_float(item.p50),
                    "p95": _format_float(item.p95),
                    "p99": _format_float(item.p99),
                    "p999": _format_float(item.p999),
                    "clip_ratio": _format_float(item.clip_ratio),
                    "shadow_ratio": _format_float(item.shadow_ratio),
                    "channel_clip_ratios": _format_channel_ratios(item.channel_clip_ratios),
                    "camera_wb": _format_float_list(item.camera_wb),
                    "daylight_wb": _format_float_list(item.daylight_wb),
                }
            )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _target_median(stats: list[RawStats]) -> float:
    medians = sorted(item.p50 for item in stats if item.p50 > 0)
    if not medians:
        return 0.30
    middle = len(medians) // 2
    if len(medians) % 2:
        value = medians[middle]
    else:
        value = (medians[middle - 1] + medians[middle]) / 2
    return _clamp(value, 0.24, 0.36)


def _highlight_value(item: RawStats, style: str, rationale: list[str]) -> int:
    if item.clip_ratio >= 0.01 or item.p999 >= 0.998:
        rationale.append("highlight clipping")
        return -90
    if item.clip_ratio >= 0.002 or item.p999 >= 0.99 or item.p99 >= 0.96:
        rationale.append("strong highlight protection")
        return -82 if style == "flower" else -70
    if style == "flower":
        return -78
    if item.p99 <= 0.84:
        rationale.append("low highlight headroom use")
        return -45
    return -58


def _shadow_value(item: RawStats, style: str, rationale: list[str]) -> int:
    if style == "flower":
        if item.shadow_ratio >= 0.08 or item.p01 <= 0.003:
            rationale.append("dense foreground shadows")
            return 75
        return 50
    if item.shadow_ratio >= 0.08 or item.p01 <= 0.003:
        rationale.append("shadow clipping risk")
        return 38
    if item.shadow_ratio >= 0.03 or item.p01 <= 0.01:
        rationale.append("shadow recovery")
        return 24
    return 12


def build_lr_plans(
    stats: list[RawStats],
    ratings: dict[object, int | None] | None = None,
    *,
    style: str = "travel",
) -> list[LrPlan]:
    if style not in {"travel", "flower"}:
        raise ValueError(f"unknown LR plan style: {style}")
    if not stats:
        return []

    ratings = ratings or {}
    target = _target_median(stats)
    plans: list[LrPlan] = []
    for item in stats:
        rationale: list[str] = []
        exposure = math.log2(target / max(item.p50, 0.01))
        exposure = round(_clamp(exposure, -0.75, 0.75), 2)
        if exposure > 0.05:
            rationale.append("batch exposure lift")
        elif exposure < -0.05:
            rationale.append("batch exposure pull")

        highlights = _highlight_value(item, style, rationale)
        shadows = _shadow_value(item, style, rationale)

        if item.p999 >= 0.995 or item.clip_ratio >= 0.005:
            whites = -18
            rationale.append("white point restraint")
        elif item.p99 <= 0.82:
            whites = 8
            rationale.append("unused white headroom")
        else:
            whites = -4 if style == "flower" else 0

        if item.p01 <= 0.003 or item.shadow_ratio >= 0.08:
            blacks = 8 if style == "flower" else 5
            rationale.append("lift blocked blacks")
        elif item.p01 >= 0.035 and item.shadow_ratio <= 0.005:
            blacks = -8
            rationale.append("restore black anchor")
        else:
            blacks = 2 if style == "flower" else 0

        contrast = -12 if style == "flower" else 0
        if style == "flower":
            rationale.append("flower-field soft contrast")

        plans.append(
            LrPlan(
                path=item.path,
                stem=item.stem,
                rating=_rating_for_stats_item(ratings, item),
                exposure2012=exposure,
                highlights2012=highlights,
                shadows2012=shadows,
                whites2012=whites,
                blacks2012=blacks,
                contrast2012=contrast,
                rationale=", ".join(dict.fromkeys(rationale)) or "raw histogram baseline",
                plan_style=style,
            )
        )
    return plans


def _rating_for_stats_item(
    ratings: dict[object, int | None],
    item: RawStats,
) -> int | None:
    for key in (
        item.path.resolve(),
        item.path,
        str(item.path.resolve()),
        str(item.path),
        item.stem,
    ):
        if key in ratings:
            return ratings[key]
    return None


def write_lr_plan_tsv(output: Path, plans: list[LrPlan], *, root: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "path",
        "stem",
        "rating",
        "plan_style",
        "Exposure2012",
        "Highlights2012",
        "Shadows2012",
        "Whites2012",
        "Blacks2012",
        "Contrast2012",
        "rationale",
    ]
    with output.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for item in plans:
            try:
                rel_path = item.path.resolve().relative_to(root.resolve())
            except ValueError:
                rel_path = item.path
            writer.writerow(
                {
                    "path": str(rel_path),
                    "stem": item.stem,
                    "rating": "" if item.rating is None else item.rating,
                    "plan_style": item.plan_style,
                    "Exposure2012": f"{item.exposure2012:.2f}",
                    "Highlights2012": item.highlights2012,
                    "Shadows2012": item.shadows2012,
                    "Whites2012": item.whites2012,
                    "Blacks2012": item.blacks2012,
                    "Contrast2012": item.contrast2012,
                    "rationale": item.rationale,
                }
            )


LR_PLAN_FIELDS = (
    "path",
    "stem",
    "rating",
    "plan_style",
    "Exposure2012",
    "Highlights2012",
    "Shadows2012",
    "Whites2012",
    "Blacks2012",
    "Contrast2012",
    "rationale",
)


def resolve_raw_path(root: Path, value: str, *, context: str) -> Path:
    root = Path(root).resolve()
    relative = Path(value)
    if not value.strip() or relative.is_absolute():
        raise ValueError(f"{context}: RAW path is outside the shoot directory: {value!r}")
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"{context}: RAW path is outside the shoot directory: {value!r}"
        ) from exc
    if not candidate.is_file():
        raise ValueError(f"{context}: RAW file does not exist: {value!r}")
    if candidate.suffix.lower() not in RAW_EXTS:
        raise ValueError(f"{context}: unsupported RAW file extension: {value!r}")
    return candidate


def _plan_number(
    row: dict[str, str],
    field: str,
    *,
    line_number: int,
    integer: bool,
) -> float | int:
    value = (row.get(field) or "").strip()
    try:
        parsed = int(value) if integer else float(value)
    except ValueError as exc:
        kind = "integer" if integer else "number"
        raise ValueError(f"plan row {line_number}: {field} must be a {kind}") from exc
    if not math.isfinite(float(parsed)):
        raise ValueError(f"plan row {line_number}: {field} must be finite")
    minimum, maximum = (-100, 100) if integer else (-5.0, 5.0)
    if parsed < minimum or parsed > maximum:
        raise ValueError(
            f"plan row {line_number}: {field} must be between {minimum} and {maximum}"
        )
    return parsed


def read_lr_plan_tsv(path: Path, *, root: Path) -> list[LrPlan]:
    plan_path = Path(path)
    if not plan_path.is_file():
        raise ValueError(f"LR plan does not exist: {plan_path}")

    plans: list[LrPlan] = []
    seen: set[Path] = set()
    with plan_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = [field for field in LR_PLAN_FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"LR plan is missing column(s): {', '.join(missing)}")
        for line_number, row in enumerate(reader, start=2):
            raw_file = resolve_raw_path(
                root,
                row.get("path") or "",
                context=f"plan row {line_number}",
            )
            if raw_file in seen:
                raise ValueError(f"plan row {line_number}: duplicate RAW path: {row.get('path')!r}")
            seen.add(raw_file)

            stem = (row.get("stem") or "").strip()
            if stem != raw_file.stem:
                raise ValueError(
                    f"plan row {line_number}: stem {stem!r} does not match {raw_file.stem!r}"
                )
            rating_text = (row.get("rating") or "").strip()
            if rating_text:
                try:
                    rating = int(rating_text)
                except ValueError as exc:
                    raise ValueError(
                        f"plan row {line_number}: rating must be an integer from 0 to 5"
                    ) from exc
                if not 0 <= rating <= 5:
                    raise ValueError(
                        f"plan row {line_number}: rating must be an integer from 0 to 5"
                    )
            else:
                rating = None

            plan_style = (row.get("plan_style") or "").strip()
            if plan_style not in {"travel", "flower"}:
                raise ValueError(
                    f"plan row {line_number}: plan_style must be travel or flower"
                )

            plans.append(
                LrPlan(
                    path=raw_file,
                    stem=stem,
                    rating=rating,
                    exposure2012=float(
                        _plan_number(
                            row,
                            "Exposure2012",
                            line_number=line_number,
                            integer=False,
                        )
                    ),
                    highlights2012=int(
                        _plan_number(
                            row,
                            "Highlights2012",
                            line_number=line_number,
                            integer=True,
                        )
                    ),
                    shadows2012=int(
                        _plan_number(
                            row,
                            "Shadows2012",
                            line_number=line_number,
                            integer=True,
                        )
                    ),
                    whites2012=int(
                        _plan_number(
                            row,
                            "Whites2012",
                            line_number=line_number,
                            integer=True,
                        )
                    ),
                    blacks2012=int(
                        _plan_number(
                            row,
                            "Blacks2012",
                            line_number=line_number,
                            integer=True,
                        )
                    ),
                    contrast2012=int(
                        _plan_number(
                            row,
                            "Contrast2012",
                            line_number=line_number,
                            integer=True,
                        )
                    ),
                    rationale=(row.get("rationale") or "").strip(),
                    plan_style=plan_style,
                )
            )
    if not plans:
        raise ValueError("LR plan contains no rows")
    return plans


def _format_signed_int(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def _format_signed_float(value: float) -> str:
    if value > 0:
        return f"+{value:.2f}"
    return f"{value:.2f}"


LR_STYLE_PROFILES: dict[str, dict[str, str]] = lr_style_profiles()


WB_FIELDS = {"WhiteBalance", "Temperature", "Tint"}
TONE_CURVE_FIELDS = {
    "ToneCurvePV2012",
    "ToneCurvePV2012Red",
    "ToneCurvePV2012Green",
    "ToneCurvePV2012Blue",
}


def _enforce_fixed_lr_rules(fields: dict[str, str]) -> None:
    for key in WB_FIELDS:
        fields.pop(key, None)
    try:
        vignette = int(fields.get("PostCropVignetteAmount", "0"))
    except ValueError:
        fields["PostCropVignetteAmount"] = "0"
    else:
        if vignette < -7:
            fields["PostCropVignetteAmount"] = "-7"


def build_lr_xmp_fields(plan: LrPlan, *, style: str = "travel-rich") -> dict[str, str]:
    try:
        fields = dict(LR_STYLE_PROFILES[style])
    except KeyError as exc:
        raise ValueError(f"unknown LR XMP style: {style}") from exc

    fields.update(
        {
            "Exposure2012": _format_signed_float(plan.exposure2012),
            "Highlights2012": _format_signed_int(plan.highlights2012),
            "Shadows2012": _format_signed_int(plan.shadows2012),
            "Whites2012": _format_signed_int(plan.whites2012),
            "Blacks2012": _format_signed_int(plan.blacks2012),
            "Contrast2012": _format_signed_int(plan.contrast2012),
            "ProcessVersion": "15.4",
            "LensProfileEnable": "1",
            "LensProfileSetup": "Auto",
            "LensProfileDistortionScale": "100",
            "LensProfileVignettingScale": "100",
            "AutoLateralCA": "1",
            "HasSettings": "True",
            "AlreadyApplied": "False",
        }
    )
    _enforce_fixed_lr_rules(fields)
    if any(part.casefold() == "panorama" for part in plan.path.parts):
        fields["PostCropVignetteAmount"] = "0"
    return fields


def xmp_format_for_raw(raw_file: Path) -> str:
    suffix = Path(raw_file).suffix.lower()
    return RAW_XMP_FORMATS.get(suffix, f"image/x-{suffix.lstrip('.')}")


def _split_xmp_packet(text: str) -> tuple[str, str, str]:
    match = re.search(r"<(?P<prefix>[A-Za-z_][\w.-]*:)?xmpmeta\b", text)
    if not match:
        raise ValueError("XMP does not contain an xmpmeta root element")
    tag = f"{match.group('prefix') or ''}xmpmeta"
    closing = f"</{tag}>"
    end = text.find(closing, match.start())
    if end < 0:
        raise ValueError("XMP xmpmeta root element is not closed")
    end += len(closing)
    return text[: match.start()], text[match.start() : end], text[end:]


def _register_document_namespaces(root_text: str) -> None:
    try:
        declarations = ET.iterparse(io.StringIO(root_text), events=("start-ns",))
        for _event, (prefix, uri) in declarations:
            if prefix == "xml" or re.fullmatch(r"ns\d+", prefix or ""):
                continue
            ET.register_namespace(prefix or "", uri)
    except (ET.ParseError, ValueError) as exc:
        raise ValueError(f"invalid XMP XML: {exc}") from exc


def _parse_xmp(text: str) -> tuple[str, ET.Element, str]:
    prefix, root_text, suffix = _split_xmp_packet(text)
    _register_document_namespaces(root_text)
    try:
        parser = ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        root = ET.fromstring(root_text, parser=parser)
    except ET.ParseError as exc:
        raise ValueError(f"invalid XMP XML: {exc}") from exc
    return prefix, root, suffix


def _new_xmp() -> tuple[str, ET.Element, str]:
    root = ET.Element(f"{{{XMPMETA_NS}}}xmpmeta")
    rdf = ET.SubElement(root, f"{{{RDF_NS}}}RDF")
    ET.SubElement(rdf, f"{{{RDF_NS}}}Description", {f"{{{RDF_NS}}}about": ""})
    prefix = '<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    suffix = '\n<?xpacket end="w"?>\n'
    return prefix, root, suffix


def _xmp_description(root: ET.Element) -> ET.Element:
    rdf = root.find(f"{{{RDF_NS}}}RDF")
    if rdf is None:
        rdf = root.find(f".//{{{RDF_NS}}}RDF")
    if rdf is None:
        raise ValueError("XMP does not contain rdf:RDF")
    for child in rdf:
        if child.tag == f"{{{RDF_NS}}}Description":
            return child
    return ET.SubElement(rdf, f"{{{RDF_NS}}}Description", {f"{{{RDF_NS}}}about": ""})


def _set_tone_curve(description: ET.Element, key: str, value: str) -> None:
    tag = f"{{{CRS_NS}}}{key}"
    description.attrib.pop(tag, None)
    curve = next((child for child in description if child.tag == tag), None)
    if curve is None:
        curve = ET.SubElement(description, tag)
    else:
        curve.clear()
    sequence = ET.SubElement(curve, f"{{{RDF_NS}}}Seq")
    numbers = [item.strip() for item in value.split(",")]
    for index in range(0, len(numbers), 2):
        pair = numbers[index : index + 2]
        if len(pair) == 2:
            ET.SubElement(sequence, f"{{{RDF_NS}}}li").text = ", ".join(pair)


def _set_scalar_property(description: ET.Element, tag: str, value: str) -> None:
    for child in list(description):
        if child.tag == tag:
            description.remove(child)
    description.set(tag, value)


def _atomic_write_text(output: Path, text: str) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(output.parent),
        prefix=f".{output.name}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if output.exists():
            os.chmod(temporary, output.stat().st_mode & 0o777)
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_lr_xmp_sidecar(raw_file: Path, fields: dict[str, str], *, rating: int | None) -> None:
    raw_file = Path(raw_file)
    output = raw_file.with_suffix(".xmp")
    if output.exists():
        prefix, root, suffix = _parse_xmp(output.read_text(encoding="utf-8", errors="strict"))
    else:
        prefix, root, suffix = _new_xmp()
    description = _xmp_description(root)

    if rating is not None:
        if not 0 <= rating <= 5:
            raise ValueError("rating must be an integer from 0 to 5")
        _set_scalar_property(description, f"{{{XMP_NS}}}Rating", str(rating))
    for key, value in fields.items():
        if key in TONE_CURVE_FIELDS:
            _set_tone_curve(description, key, value)
        else:
            _set_scalar_property(description, f"{{{CRS_NS}}}{key}", str(value))
    _set_scalar_property(
        description,
        f"{{{PHOTOSHOP_NS}}}SidecarForExtension",
        raw_file.suffix.lstrip(".").upper(),
    )
    _set_scalar_property(
        description,
        f"{{{DC_NS}}}format",
        xmp_format_for_raw(raw_file),
    )
    _set_scalar_property(
        description,
        f"{{{XMPMM_NS}}}PreservedFileName",
        raw_file.name,
    )

    root_text = ET.tostring(root, encoding="unicode", short_empty_elements=True)
    _atomic_write_text(output, f"{prefix}{root_text}{suffix}")


def write_rating_xmp_sidecar(raw_file: Path, rating: int) -> None:
    write_lr_xmp_sidecar(
        raw_file,
        {"HasSettings": "True", "AlreadyApplied": "False"},
        rating=rating,
    )


def read_xmp_properties(path: Path) -> dict[str, str]:
    xmp_path = Path(path)
    if not xmp_path.is_file():
        raise ValueError(f"XMP file does not exist: {xmp_path}")
    _prefix, root, _suffix = _parse_xmp(
        xmp_path.read_text(encoding="utf-8", errors="strict")
    )
    description = _xmp_description(root)
    properties: dict[str, str] = {}
    for prefix, namespace in XMP_NAMESPACES.items():
        if prefix in {"x", "rdf"}:
            continue
        for name, value in description.attrib.items():
            namespace_prefix = f"{{{namespace}}}"
            if name.startswith(namespace_prefix):
                properties[f"{prefix}:{name[len(namespace_prefix):]}"] = value
        for child in description:
            namespace_prefix = f"{{{namespace}}}"
            if (
                isinstance(child.tag, str)
                and child.tag.startswith(namespace_prefix)
                and child.text
            ):
                key = f"{prefix}:{child.tag[len(namespace_prefix):]}"
                properties.setdefault(key, child.text.strip())
    return properties


def read_xmp_rating_strict(path: Path) -> int | None:
    xmp_path = Path(path)
    if not xmp_path.exists():
        return None
    properties = read_xmp_properties(xmp_path)
    value = properties.get("xmp:Rating")
    if value is None:
        return None
    try:
        rating = int(value)
    except ValueError as exc:
        raise ValueError(f"invalid XMP rating: {value!r}") from exc
    if not 0 <= rating <= 5:
        raise ValueError(f"invalid XMP rating: {rating}; expected 0..5")
    return rating


def read_xmp_rating(path: Path) -> int | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r'\bxmp:Rating="(-?\d+)"', text)
    if not match:
        match = re.search(r"<(?:[^:>]+:)?Rating>\s*(-?\d+)\s*</(?:[^:>]+:)?Rating>", text)
    if not match:
        return None
    return int(match.group(1))


def rating_matches(value: int | None, expression: str | None) -> bool:
    if expression is None:
        return True
    if value is None:
        return False
    match = re.fullmatch(r"\s*(>=|<=|>|<|=|==)?\s*(-?\d+)\s*", expression)
    if not match:
        raise ValueError(f"invalid rating filter: {expression}")
    operator = match.group(1) or "=="
    target = int(match.group(2))
    if operator == ">=":
        return value >= target
    if operator == "<=":
        return value <= target
    if operator == ">":
        return value > target
    if operator == "<":
        return value < target
    return value == target


def collect_raw_files(root: Path, *, rating_filter: str | None = None) -> list[Path]:
    root = Path(root)
    raws = sorted(
        [
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in RAW_EXTS
        ],
        key=lambda path: str(path).lower(),
    )
    if rating_filter is None:
        return raws
    return [
        path
        for path in raws
        if rating_matches(read_xmp_rating(path.with_suffix(".xmp")), rating_filter)
    ]


def render_raw_to_jpeg(
    source: Path,
    destination: Path,
    *,
    quality: int = 96,
    imread: Callable[[str], object] | None = None,
) -> None:
    reader = imread or _default_imread()
    with reader(str(source)) as raw:
        postprocess_options = dict(
            use_camera_wb=True,
            no_auto_bright=True,
            output_bps=8,
        )
        try:
            postprocess_options["output_color"] = _rawpy_srgb_colorspace()
        except ModuleNotFoundError:
            if imread is None:
                raise
        rgb = raw.postprocess(**postprocess_options)
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(destination, format="JPEG", quality=quality, subsampling=0)
