from __future__ import annotations

import csv
import html
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image


RAW_EXTS = {
    ".3fr",
    ".arw",
    ".cr2",
    ".cr3",
    ".dng",
    ".nef",
    ".orf",
    ".raf",
    ".raw",
    ".rw2",
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
    ratings: dict[str, int | None] | None = None,
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
                rating=ratings.get(item.stem),
                exposure2012=exposure,
                highlights2012=highlights,
                shadows2012=shadows,
                whites2012=whites,
                blacks2012=blacks,
                contrast2012=contrast,
                rationale=", ".join(dict.fromkeys(rationale)) or "raw histogram baseline",
            )
        )
    return plans


def write_lr_plan_tsv(output: Path, plans: list[LrPlan], *, root: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "path",
        "stem",
        "rating",
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
                    "Exposure2012": f"{item.exposure2012:.2f}",
                    "Highlights2012": item.highlights2012,
                    "Shadows2012": item.shadows2012,
                    "Whites2012": item.whites2012,
                    "Blacks2012": item.blacks2012,
                    "Contrast2012": item.contrast2012,
                    "rationale": item.rationale,
                }
            )


def _format_signed_int(value: int) -> str:
    if value > 0:
        return f"+{value}"
    return str(value)


def _format_signed_float(value: float) -> str:
    if value > 0:
        return f"+{value:.2f}"
    return f"{value:.2f}"


LR_STYLE_PROFILES: dict[str, dict[str, str]] = {
    "travel-rich": {
        "CameraProfile": "Camera ST",
        "Texture": "+6",
        "Clarity2012": "+3",
        "Dehaze": "+2",
        "Vibrance": "+2",
        "Saturation": "0",
        "ParametricHighlights": "+4",
        "ParametricLights": "+6",
        "ParametricDarks": "-4",
        "ParametricShadows": "-2",
        "ToneCurveName2012": "Custom",
        "ToneCurvePV2012": "2, 5, 66, 59, 125, 125, 182, 188, 255, 250",
        "ToneCurvePV2012Red": "0, 0, 255, 255",
        "ToneCurvePV2012Green": "0, 0, 255, 255",
        "ToneCurvePV2012Blue": "0, 0, 255, 255",
        "SaturationAdjustmentYellow": "-1",
        "SaturationAdjustmentGreen": "-2",
        "SaturationAdjustmentAqua": "-2",
        "SaturationAdjustmentBlue": "-3",
        "LuminanceAdjustmentYellow": "+2",
        "LuminanceAdjustmentGreen": "+3",
        "LuminanceAdjustmentBlue": "-1",
        "RedHue": "0",
        "RedSaturation": "+6",
        "GreenHue": "0",
        "GreenSaturation": "+7",
        "BlueHue": "0",
        "BlueSaturation": "+6",
        "ColorGradeMidtoneHue": "0",
        "ColorGradeMidtoneSat": "0",
        "ColorGradeBlending": "50",
        "PostCropVignetteAmount": "-2",
    },
    "flower-rich": {
        "CameraProfile": "Camera ST",
        "Texture": "+6",
        "Clarity2012": "+4",
        "Dehaze": "+2",
        "Vibrance": "+2",
        "Saturation": "0",
        "ParametricHighlights": "+4",
        "ParametricLights": "+6",
        "ParametricDarks": "-4",
        "ParametricShadows": "-2",
        "ToneCurveName2012": "Custom",
        "ToneCurvePV2012": "2, 5, 68, 55, 125, 124, 186, 193, 255, 250",
        "ToneCurvePV2012Red": "0, 0, 255, 255",
        "ToneCurvePV2012Green": "0, 0, 255, 255",
        "ToneCurvePV2012Blue": "0, 0, 255, 255",
        "HueAdjustmentRed": "0",
        "HueAdjustmentOrange": "0",
        "HueAdjustmentYellow": "0",
        "HueAdjustmentGreen": "0",
        "HueAdjustmentAqua": "0",
        "HueAdjustmentBlue": "0",
        "HueAdjustmentPurple": "0",
        "HueAdjustmentMagenta": "0",
        "SaturationAdjustmentRed": "0",
        "SaturationAdjustmentOrange": "0",
        "SaturationAdjustmentYellow": "-2",
        "SaturationAdjustmentGreen": "-3",
        "SaturationAdjustmentAqua": "-3",
        "SaturationAdjustmentBlue": "-4",
        "SaturationAdjustmentPurple": "0",
        "SaturationAdjustmentMagenta": "0",
        "LuminanceAdjustmentRed": "0",
        "LuminanceAdjustmentOrange": "0",
        "LuminanceAdjustmentYellow": "+2",
        "LuminanceAdjustmentGreen": "+3",
        "LuminanceAdjustmentAqua": "0",
        "LuminanceAdjustmentBlue": "-1",
        "RedHue": "0",
        "RedSaturation": "+10",
        "GreenHue": "0",
        "GreenSaturation": "+12",
        "BlueHue": "0",
        "BlueSaturation": "+11",
        "ColorGradeMidtoneHue": "0",
        "ColorGradeMidtoneSat": "0",
        "ColorGradeBlending": "50",
        "PostCropVignetteAmount": "-5",
    },
    "sairim-lake-east": {
        "CameraProfile": "Camera ST",
        "Texture": "+6",
        "Clarity2012": "+4",
        "Dehaze": "+2",
        "Vibrance": "+2",
        "Saturation": "0",
        "ParametricHighlights": "+4",
        "ParametricLights": "+6",
        "ParametricDarks": "-4",
        "ParametricShadows": "-2",
        "ToneCurveName2012": "Custom",
        "ToneCurvePV2012": "2, 5, 65, 62, 125, 124, 186, 193, 255, 250",
        "ToneCurvePV2012Red": "0, 0, 255, 255",
        "ToneCurvePV2012Green": "0, 0, 255, 255",
        "ToneCurvePV2012Blue": "0, 0, 255, 255",
        "SaturationAdjustmentYellow": "-2",
        "SaturationAdjustmentGreen": "-3",
        "SaturationAdjustmentAqua": "-3",
        "SaturationAdjustmentBlue": "-4",
        "LuminanceAdjustmentYellow": "+2",
        "LuminanceAdjustmentGreen": "+3",
        "LuminanceAdjustmentBlue": "-1",
        "RedHue": "0",
        "RedSaturation": "+4",
        "GreenHue": "0",
        "GreenSaturation": "+2",
        "BlueHue": "0",
        "BlueSaturation": "+6",
        "ColorGradeMidtoneHue": "0",
        "ColorGradeMidtoneSat": "0",
        "ColorGradeBlending": "50",
        "PostCropVignetteAmount": "-5",
    },
    "bayanbulak-nine-bends": {
        "CameraProfile": "Adobe Standard",
        "Texture": "+6",
        "Clarity2012": "+4",
        "Dehaze": "+6",
        "Vibrance": "+2",
        "Saturation": "0",
        "ParametricHighlights": "0",
        "ParametricLights": "0",
        "ParametricDarks": "0",
        "ParametricShadows": "0",
        "ToneCurveName2012": "Custom",
        "ToneCurvePV2012": "2, 5, 66, 59, 125, 125, 182, 188, 255, 250",
        "ToneCurvePV2012Red": "0, 0, 255, 255",
        "ToneCurvePV2012Green": "0, 0, 255, 255",
        "ToneCurvePV2012Blue": "0, 0, 255, 255",
        "SaturationAdjustmentYellow": "+17",
        "SaturationAdjustmentGreen": "-3",
        "SaturationAdjustmentAqua": "-3",
        "SaturationAdjustmentBlue": "-4",
        "LuminanceAdjustmentYellow": "+2",
        "LuminanceAdjustmentGreen": "+3",
        "LuminanceAdjustmentBlue": "-1",
        "RedHue": "0",
        "RedSaturation": "+4",
        "GreenHue": "0",
        "GreenSaturation": "+14",
        "BlueHue": "0",
        "BlueSaturation": "+7",
        "ColorGradeMidtoneHue": "0",
        "ColorGradeMidtoneSat": "0",
        "ColorGradeBlending": "50",
        "PostCropVignetteAmount": "-5",
    },
}


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
            "PerspectiveUpright": "0",
            "Sharpness": "40",
            "LuminanceSmoothing": "0",
            "ColorNoiseReduction": "25",
            "HasSettings": "True",
            "AlreadyApplied": "False",
        }
    )
    _enforce_fixed_lr_rules(fields)
    return fields


def write_lr_xmp_sidecar(raw_file: Path, fields: dict[str, str], *, rating: int | None) -> None:
    raw_file = Path(raw_file)
    output = raw_file.with_suffix(".xmp")
    output.parent.mkdir(parents=True, exist_ok=True)
    rating_value = "" if rating is None else f' xmp:Rating="{rating}"'
    crs_attrs = "\n".join(
        f'   crs:{html.escape(key)}="{html.escape(value, quote=True)}"'
        for key, value in fields.items()
        if key not in TONE_CURVE_FIELDS
    )
    curve_blocks = "\n".join(
        _tone_curve_block(key, value)
        for key, value in fields.items()
        if key in TONE_CURVE_FIELDS
    )
    text = f'''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
   xmlns:xmp="http://ns.adobe.com/xap/1.0/"
   xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
   xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
   xmlns:dc="http://purl.org/dc/elements/1.1/"
   xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/"{rating_value}
{crs_attrs}
   photoshop:SidecarForExtension="{html.escape(raw_file.suffix.lstrip('.').upper(), quote=True)}"
   dc:format="image/x-sony-arw"
   xmpMM:PreservedFileName="{html.escape(raw_file.name, quote=True)}">
{curve_blocks}
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
'''
    output.write_text(text, encoding="utf-8")


def _tone_curve_block(key: str, value: str) -> str:
    numbers = [item.strip() for item in value.split(",")]
    pairs = [
        ", ".join(numbers[index : index + 2])
        for index in range(0, len(numbers), 2)
        if len(numbers[index : index + 2]) == 2
    ]
    items = "\n".join(f"     <rdf:li>{html.escape(pair)}</rdf:li>" for pair in pairs)
    return f"""   <crs:{html.escape(key)}>
    <rdf:Seq>
{items}
    </rdf:Seq>
   </crs:{html.escape(key)}>"""


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
        rgb = raw.postprocess(
            use_camera_wb=True,
            no_auto_bright=True,
            output_color=_rawpy_srgb_colorspace(),
            output_bps=8,
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb).save(destination, format="JPEG", quality=quality, subsampling=0)
