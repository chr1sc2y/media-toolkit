from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
import re
from typing import Any

from media_toolkit.final_hif_archive import EXPORT_EXTS, export_scan_directories


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
    "SaturationAdjustmentBlue",
    "SaturationAdjustmentGreen",
    "LuminanceAdjustmentBlue",
    "RedSaturation",
    "GreenSaturation",
    "BlueSaturation",
    "PostCropVignetteAmount",
    "PerspectiveUpright",
    "ToneCurvePV2012",
)


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
    missing_xmp: list[str] = field(default_factory=list)
    field_values: dict[str, list[str]] = field(default_factory=dict)
    samples: list[LearnedSample] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _extract_field(text: str, field: str) -> str | None:
    attr_match = re.search(rf"\bcrs:{re.escape(field)}=\"([^\"]*)\"", text)
    if attr_match:
        return attr_match.group(1)
    block_match = re.search(
        rf"<crs:{re.escape(field)}>\s*(.*?)\s*</crs:{re.escape(field)}>",
        text,
        flags=re.DOTALL,
    )
    if not block_match:
        return None
    values = re.findall(r"<rdf:li>\s*([^<]+?)\s*</rdf:li>", block_match.group(1))
    return " / ".join(values) if values else block_match.group(1).strip()


def read_style_fields(xmp_path: Path, fields: tuple[str, ...] = STYLE_FIELDS) -> dict[str, str]:
    text = xmp_path.read_text(encoding="utf-8", errors="replace")
    extracted: dict[str, str] = {}
    for field in fields:
        value = _extract_field(text, field)
        if value is not None:
            extracted[field] = value
    return extracted


def _iter_export_files(root: Path) -> list[Path]:
    exports: list[Path] = []
    for export_dir in export_scan_directories(root):
        exports.extend(
            sorted(
                [
                    path
                    for path in export_dir.iterdir()
                    if path.is_file()
                    and not path.stem.startswith(".")
                    and path.suffix.lower() in EXPORT_EXTS
                ],
                key=lambda path: path.name.lower(),
            )
        )
    return exports


def learn_style_from_directory(root: Path, *, scene: str) -> StyleLearningReport:
    root = Path(root).expanduser().resolve()
    missing: list[str] = []
    samples: list[LearnedSample] = []
    field_values: dict[str, set[str]] = defaultdict(set)

    for export_path in _iter_export_files(root):
        raw_dir = export_path.parent.parent
        xmp_path = raw_dir / f"{export_path.stem}.xmp"
        try:
            rel_export = str(export_path.relative_to(root))
        except ValueError:
            rel_export = str(export_path)
        if not xmp_path.exists():
            missing.append(rel_export)
            continue
        fields = read_style_fields(xmp_path)
        for key, value in fields.items():
            field_values[key].add(value)
        try:
            rel_xmp = str(xmp_path.relative_to(root))
        except ValueError:
            rel_xmp = str(xmp_path)
        samples.append(
            LearnedSample(
                export_path=rel_export,
                xmp_path=rel_xmp,
                fields=fields,
            )
        )

    return StyleLearningReport(
        path=str(root),
        scene=scene,
        sample_count=len(samples),
        missing_xmp=missing,
        field_values={
            key: sorted(values)
            for key, values in sorted(field_values.items())
        },
        samples=samples,
    )


def render_style_learning_report(report: StyleLearningReport) -> str:
    lines = [
        f"Style learning report: {report.path}",
        f"scene: {report.scene}",
        f"samples: {report.sample_count}",
        f"missing_xmp: {len(report.missing_xmp)}",
    ]
    if report.missing_xmp:
        lines.append("missing xmp:")
        lines.extend(f"- {path}" for path in report.missing_xmp)
    if report.field_values:
        lines.append("field values:")
        for key, values in report.field_values.items():
            preview = ", ".join(values[:5])
            suffix = "" if len(values) <= 5 else f" ... (+{len(values) - 5})"
            lines.append(f"- {key}: {preview}{suffix}")
    return "\n".join(lines)
