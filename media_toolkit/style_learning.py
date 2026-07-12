from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
import html
import os
from pathlib import Path
import re
from statistics import median
from typing import Any, Iterable
import xml.etree.ElementTree as ET

from media_toolkit.final_hif_archive import EXPORT_EXTS, child_dir_case_insensitive
from media_toolkit.style_profiles import get_style_profile, style_profile_ids


# Representative global develop fields. read_style_fields also discovers newer
# global crs:* fields so learning does not silently lag Lightroom schema updates.
STYLE_FIELDS = (
    "CameraProfile",
    "WhiteBalance",
    "Temperature",
    "Tint",
    "Exposure2012",
    "Contrast2012",
    "Highlights2012",
    "Shadows2012",
    "Whites2012",
    "Blacks2012",
    "Texture",
    "Clarity2012",
    "Dehaze",
    "Vibrance",
    "Saturation",
    "ParametricHighlights",
    "ParametricLights",
    "ParametricDarks",
    "ParametricShadows",
    "ToneCurvePV2012",
    "ToneCurvePV2012Red",
    "ToneCurvePV2012Green",
    "ToneCurvePV2012Blue",
    "HueAdjustmentRed",
    "HueAdjustmentOrange",
    "HueAdjustmentYellow",
    "HueAdjustmentGreen",
    "HueAdjustmentAqua",
    "HueAdjustmentBlue",
    "HueAdjustmentPurple",
    "HueAdjustmentMagenta",
    "SaturationAdjustmentRed",
    "SaturationAdjustmentOrange",
    "SaturationAdjustmentYellow",
    "SaturationAdjustmentGreen",
    "SaturationAdjustmentAqua",
    "SaturationAdjustmentBlue",
    "SaturationAdjustmentPurple",
    "SaturationAdjustmentMagenta",
    "LuminanceAdjustmentRed",
    "LuminanceAdjustmentOrange",
    "LuminanceAdjustmentYellow",
    "LuminanceAdjustmentGreen",
    "LuminanceAdjustmentAqua",
    "LuminanceAdjustmentBlue",
    "LuminanceAdjustmentPurple",
    "LuminanceAdjustmentMagenta",
    "RedHue",
    "RedSaturation",
    "GreenHue",
    "GreenSaturation",
    "BlueHue",
    "BlueSaturation",
    "Sharpness",
    "SharpenRadius",
    "SharpenDetail",
    "SharpenEdgeMasking",
    "LuminanceSmoothing",
    "ColorNoiseReduction",
    "LensProfileEnable",
    "LensManualDistortionAmount",
    "PostCropVignetteAmount",
    "PerspectiveUpright",
    "PerspectiveRotate",
    "ToneCurveName2012",
    "AutoLateralCA",
    "LensProfileSetup",
    "ColorNoiseReductionDetail",
    "ColorNoiseReductionSmoothness",
    "GrainAmount",
    "GrainSize",
    "GrainFrequency",
    "PostCropVignetteMidpoint",
    "PostCropVignetteRoundness",
    "PostCropVignetteFeather",
    "PostCropVignetteStyle",
    "PostCropVignetteHighlightContrast",
)
STYLE_FIELD_SET = frozenset(STYLE_FIELDS)
STYLE_FIELD_PREFIXES = (
    "ColorGrade",
    "ColorNoiseReduction",
    "Defringe",
    "Grain",
    "HueAdjustment",
    "LuminanceAdjustment",
    "Parametric",
    "PostCropVignette",
    "SaturationAdjustment",
    "Sharpen",
    "SplitToning",
    "ToneCurvePV2012",
)

NON_STYLE_FIELDS = {
    "AlreadyApplied",
    "ConvertToGrayscale",
    "HasSettings",
    "HasCrop",
    "ProcessVersion",
    "RawFileName",
    "Version",
}
NON_STYLE_PREFIXES = (
    "CircularGradientBasedCorrections",
    "GradientBasedCorrections",
    "MaskGroupBasedCorrections",
    "PaintBasedCorrections",
    "RetouchAreas",
)
SKIP_DISCOVERY_DIRS = {
    ".git",
    ".codex_previews",
    "codex",
    "contact_sheets",
    "featured",
    "outputs",
    "review_jpg",
    "style_learning",
    "work",
}
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
CRS_NS = "http://ns.adobe.com/camera-raw-settings/1.0/"
KNOWN_XML_PREFIXES = {
    "x": "adobe:ns:meta/",
    "rdf": RDF_NS,
    "crs": CRS_NS,
    "xmp": "http://ns.adobe.com/xap/1.0/",
    "photoshop": "http://ns.adobe.com/photoshop/1.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "xmpMM": "http://ns.adobe.com/xap/1.0/mm/",
}


@dataclass(frozen=True)
class LearnedSample:
    export_path: str
    xmp_path: str
    fields: dict[str, str]


@dataclass
class StyleLearningReport:
    path: str
    scene: str
    sample_count: int
    baseline_profile: str | None = None
    missing_xmp: list[str] = field(default_factory=list)
    ignored_xmp: list[str] = field(default_factory=list)
    field_values: dict[str, list[str]] = field(default_factory=dict)
    field_summaries: dict[str, dict[str, Any]] = field(default_factory=dict)
    deviations: dict[str, list[dict[str, str]]] = field(default_factory=dict)
    samples: list[LearnedSample] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _is_style_field(field_name: str) -> bool:
    if field_name in NON_STYLE_FIELDS:
        return False
    if any(field_name.startswith(prefix) for prefix in NON_STYLE_PREFIXES):
        return False
    return field_name in STYLE_FIELD_SET or any(
        field_name.startswith(prefix) for prefix in STYLE_FIELD_PREFIXES
    )


def _with_missing_namespace_declarations(text: str) -> str:
    declarations: list[str] = []
    for prefix, namespace in KNOWN_XML_PREFIXES.items():
        if re.search(rf"\b{re.escape(prefix)}:", text) and not re.search(
            rf"\bxmlns:{re.escape(prefix)}=", text
        ):
            declarations.append(f' xmlns:{prefix}="{namespace}"')
    if not declarations:
        return text
    root_match = re.search(r"<([A-Za-z_][A-Za-z0-9_.:-]*)(?=[\s>/])", text)
    if root_match is None:
        return text
    return text[: root_match.end()] + "".join(declarations) + text[root_match.end() :]


def _expanded_name(value: str) -> tuple[str | None, str]:
    if value.startswith("{") and "}" in value:
        namespace, local_name = value[1:].split("}", 1)
        return namespace, local_name
    if ":" in value:
        prefix, local_name = value.split(":", 1)
        return KNOWN_XML_PREFIXES.get(prefix), local_name
    return None, value


def _element_value(element: ET.Element) -> str:
    list_values = [
        "".join(item.itertext()).strip()
        for item in element.iter()
        if _expanded_name(item.tag) == (RDF_NS, "li")
    ]
    if list_values:
        return " / ".join(html.unescape(value) for value in list_values)
    return html.unescape("".join(element.itertext()).strip())


def _fallback_description_attributes(
    text: str,
    allowed: set[str] | None,
) -> dict[str, str]:
    match = re.search(r"<rdf:Description\b([^>]*)>", text, flags=re.DOTALL)
    if match is None:
        match = re.search(r"<rdf:Description\b([^>]*)/>", text, flags=re.DOTALL)
    if match is None:
        return {}
    extracted: dict[str, str] = {}
    for attribute in re.finditer(
        r'\bcrs:([A-Za-z][A-Za-z0-9_]*)="([^"]*)"', match.group(1)
    ):
        field_name, value = attribute.groups()
        if (allowed is None and _is_style_field(field_name)) or (
            allowed is not None and field_name in allowed
        ):
            extracted[field_name] = html.unescape(value)
    return dict(sorted(extracted.items()))


def read_style_fields(
    xmp_path: Path,
    fields: tuple[str, ...] | None = None,
) -> dict[str, str]:
    text = xmp_path.read_text(encoding="utf-8", errors="replace")
    allowed = set(fields) if fields is not None else None
    try:
        root = ET.fromstring(_with_missing_namespace_declarations(text))
    except ET.ParseError:
        return _fallback_description_attributes(text, allowed)

    description = next(
        (
            element
            for element in root.iter()
            if _expanded_name(element.tag) == (RDF_NS, "Description")
        ),
        None,
    )
    if description is None:
        return {}

    extracted: dict[str, str] = {}
    for attribute_name, value in description.attrib.items():
        namespace, field_name = _expanded_name(attribute_name)
        if namespace != CRS_NS:
            continue
        if (allowed is None and _is_style_field(field_name)) or (
            allowed is not None and field_name in allowed
        ):
            extracted[field_name] = html.unescape(value)

    for child in list(description):
        namespace, field_name = _expanded_name(child.tag)
        if namespace != CRS_NS:
            continue
        if (allowed is None and _is_style_field(field_name)) or (
            allowed is not None and field_name in allowed
        ):
            extracted[field_name] = _element_value(child)
    return dict(sorted(extracted.items()))


def _export_directories(root: Path) -> list[Path]:
    export_dirs: list[Path] = []
    root = root.resolve()
    for dirpath, dirnames, _filenames in os.walk(root):
        current = Path(dirpath)
        try:
            relative_parts = [part.casefold() for part in current.relative_to(root).parts]
        except ValueError:
            relative_parts = []
        dirnames[:] = [
            name
            for name in dirnames
            if name.casefold() not in SKIP_DISCOVERY_DIRS
            and name.casefold() != "panorama"
        ]
        if "panorama" in relative_parts:
            dirnames[:] = []
            continue
        if (
            current.name.casefold() == "export"
            and current.parent.name.casefold() == "raw"
        ):
            export_dirs.append(current)
            dirnames[:] = []
    return sorted(export_dirs, key=lambda path: str(path).casefold())


def _image_files(directory: Path) -> Iterable[Path]:
    if not directory.is_dir():
        return ()
    return (
        path
        for path in sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        if path.is_file()
        and not path.stem.startswith(".")
        and path.suffix.casefold() in EXPORT_EXTS
    )


def _iter_export_files(root: Path) -> list[tuple[Path, Path]]:
    selected: dict[tuple[Path, str], tuple[Path, Path]] = {}
    for export_dir in _export_directories(root):
        raw_dir = export_dir.parent
        pixcake_dir = child_dir_case_insensitive(export_dir, "Pixcake")
        for path in _image_files(pixcake_dir):
            selected[(raw_dir.resolve(), path.stem.casefold())] = (path, raw_dir)
        for path in _image_files(export_dir):
            selected.setdefault(
                (raw_dir.resolve(), path.stem.casefold()),
                (path, raw_dir),
            )
    return sorted(
        selected.values(),
        key=lambda item: (str(item[1]).casefold(), item[0].name.casefold()),
    )


def _relative(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _find_xmp(raw_dir: Path, stem: str) -> Path | None:
    exact = raw_dir / f"{stem}.xmp"
    if exact.is_file():
        return exact
    matches = sorted(
        path
        for path in raw_dir.iterdir()
        if path.is_file()
        and path.stem.casefold() == stem.casefold()
        and path.suffix.casefold() == ".xmp"
    )
    return matches[0] if matches else None


def _number(value: str) -> float | None:
    try:
        return float(value.strip())
    except ValueError:
        return None


def _values_equivalent(left: str, right: str) -> bool:
    left_number = _number(left)
    right_number = _number(right)
    if left_number is not None and right_number is not None:
        return left_number == right_number
    return left == right


def _summaries(
    samples: list[LearnedSample],
    baseline_fields: dict[str, str],
) -> tuple[
    dict[str, list[str]],
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, str]]],
]:
    values: dict[str, list[str]] = defaultdict(list)
    for sample in samples:
        for field_name, value in sample.fields.items():
            values[field_name].append(value)

    field_values: dict[str, list[str]] = {}
    summaries: dict[str, dict[str, Any]] = {}
    deviations: dict[str, list[dict[str, str]]] = {}
    for field_name in sorted(values):
        field_data = values[field_name]
        counts = Counter(field_data)
        unique = sorted(counts)
        field_values[field_name] = unique
        summary: dict[str, Any] = {
            "count": len(field_data),
            "frequencies": {value: counts[value] for value in unique},
            "numeric": None,
            "baseline": baseline_fields.get(field_name),
        }
        numeric_values = [_number(value) for value in field_data]
        if all(value is not None for value in numeric_values):
            numbers = [float(value) for value in numeric_values if value is not None]
            summary["numeric"] = {
                "min": min(numbers),
                "median": float(median(numbers)),
                "max": max(numbers),
            }
        summaries[field_name] = summary

        baseline = baseline_fields.get(field_name)
        if baseline is None:
            continue
        differences = [
            {
                "export_path": sample.export_path,
                "xmp_path": sample.xmp_path,
                "value": sample.fields[field_name],
                "baseline": baseline,
            }
            for sample in samples
            if field_name in sample.fields
            and not _values_equivalent(sample.fields[field_name], baseline)
        ]
        if differences:
            deviations[field_name] = differences
    return field_values, summaries, deviations


def learn_style_from_directory(
    root: Path,
    *,
    scene: str,
    baseline_profile: str | None = None,
) -> StyleLearningReport:
    root = Path(root).expanduser().resolve()
    if baseline_profile is None and scene in style_profile_ids():
        baseline_profile = scene
    baseline_fields = (
        dict(get_style_profile(baseline_profile)["xmp_fields"])
        if baseline_profile
        else {}
    )

    missing: list[str] = []
    ignored: list[str] = []
    samples: list[LearnedSample] = []
    for export_path, raw_dir in _iter_export_files(root):
        rel_export = _relative(root, export_path)
        xmp_path = _find_xmp(raw_dir, export_path.stem)
        if xmp_path is None:
            missing.append(rel_export)
            continue
        fields = read_style_fields(xmp_path)
        rel_xmp = _relative(root, xmp_path)
        if not fields:
            ignored.append(rel_xmp)
            continue
        samples.append(
            LearnedSample(
                export_path=rel_export,
                xmp_path=rel_xmp,
                fields=fields,
            )
        )

    field_values, field_summaries, deviations = _summaries(samples, baseline_fields)
    return StyleLearningReport(
        path=str(root),
        scene=scene,
        sample_count=len(samples),
        baseline_profile=baseline_profile,
        missing_xmp=sorted(missing),
        ignored_xmp=sorted(ignored),
        field_values=field_values,
        field_summaries=field_summaries,
        deviations=deviations,
        samples=samples,
    )


def render_style_learning_report(report: StyleLearningReport) -> str:
    lines = [
        f"Style learning report: {report.path}",
        f"scene: {report.scene}",
        f"baseline: {report.baseline_profile or 'none'}",
        f"samples: {report.sample_count}",
        f"missing_xmp: {len(report.missing_xmp)}",
        f"ignored_non_style_xmp: {len(report.ignored_xmp)}",
    ]
    if report.missing_xmp:
        lines.append("missing xmp:")
        lines.extend(f"- {path}" for path in report.missing_xmp)
    if report.ignored_xmp:
        lines.append("ignored non-style xmp:")
        lines.extend(f"- {path}" for path in report.ignored_xmp)
    if report.field_summaries:
        lines.append("field summaries:")
        for key, summary in report.field_summaries.items():
            frequencies = ", ".join(
                f"{value}×{count}"
                for value, count in summary["frequencies"].items()
            )
            numeric = summary.get("numeric")
            numeric_text = ""
            if numeric:
                numeric_text = (
                    f"; min/median/max={numeric['min']:g}/"
                    f"{numeric['median']:g}/{numeric['max']:g}"
                )
            baseline = summary.get("baseline")
            baseline_text = f"; baseline={baseline}" if baseline is not None else ""
            lines.append(f"- {key}: {frequencies}{numeric_text}{baseline_text}")
    if report.deviations:
        lines.append("baseline deviations:")
        for key, differences in report.deviations.items():
            lines.append(f"- {key}: {len(differences)} sample(s)")
    return "\n".join(lines)
