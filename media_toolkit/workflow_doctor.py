from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import shlex
from typing import Literal

from media_toolkit.commands import verify_cull
from media_toolkit.final_hif_archive import (
    destination_is_inside_source,
    export_scan_directories,
    matching_hif_files,
    selected_export_stems,
)


WorkflowName = str
Severity = Literal["info", "warning", "error"]
DecisionStatus = Literal["ready", "blocked", "needs-organize", "needs-lightroom-export"]

RAW_EXTS = {".arw", ".dng", ".cr2", ".cr3", ".nef", ".raf", ".rw2"}
HIF_EXTS = {".hif", ".heif", ".heic"}
EXPORT_EXTS = {".jpg", ".jpeg", ".tif", ".tiff", ".png"}


@dataclass(frozen=True)
class DoctorFinding:
    severity: Severity
    code: str
    message: str


@dataclass
class DoctorReport:
    path: str
    workflow: WorkflowName
    inferred_stage: str
    status: DecisionStatus = "ready"
    summary: dict[str, int] = field(default_factory=dict)
    findings: list[DoctorFinding] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(finding.severity == "error" for finding in self.findings)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["ok"] = self.ok
        return data


def _count_files(directory: Path, exts: set[str]) -> int:
    if not directory.exists():
        return 0
    return sum(
        1
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in exts
    )


def _count_tree(directory: Path, exts: set[str]) -> int:
    if not directory.exists():
        return 0
    return sum(
        1
        for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in exts
    )


def _numbered_group_dirs(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        [path for path in directory.iterdir() if path.is_dir() and path.name.isdigit()],
        key=lambda path: int(path.name),
    )


def _count_group_media(group_root: Path, exts: set[str], bucket: str) -> int:
    return sum(_count_tree(group / bucket, exts) for group in _numbered_group_dirs(group_root))


def _infer_stage(root: Path) -> str:
    if (root / "raw").is_dir() or (root / "hif").is_dir():
        if export_scan_directories(root):
            return "ready-for-finalize"
        if (root / "_contact_sheet.jpg").exists():
            return "initial-cull-reviewed"
        return "organized"
    if _count_files(root, RAW_EXTS) or _count_files(root, HIF_EXTS):
        return "new-import"
    return "unknown"


def _add(report: DoctorReport, severity: Severity, code: str, message: str) -> None:
    report.findings.append(DoctorFinding(severity, code, message))


def inspect_directory(
    root: Path,
    *,
    workflow: WorkflowName = "auto",
    copy_to: Path | None = None,
) -> DoctorReport:
    root = Path(root).expanduser().resolve()
    report = DoctorReport(
        path=str(root),
        workflow=workflow,
        inferred_stage="missing",
    )

    if not root.exists():
        _add(report, "error", "missing-source", f"Directory does not exist: {root}")
        return report
    if not root.is_dir():
        _add(report, "error", "not-directory", f"Path is not a directory: {root}")
        return report

    report.inferred_stage = _infer_stage(root)
    report.summary = {
        "loose_raw": _count_files(root, RAW_EXTS),
        "loose_hif": _count_files(root, HIF_EXTS),
        "raw": _count_tree(root / "raw", RAW_EXTS),
        "hif": _count_tree(root / "hif", HIF_EXTS),
        "xmp": _count_tree(root / "raw", {".xmp"}),
        "portrait_groups": len(_numbered_group_dirs(root / "portrait")),
        "portrait_raw": _count_group_media(root / "portrait", RAW_EXTS, "raw"),
        "portrait_hif": _count_group_media(root / "portrait", HIF_EXTS, "hif"),
        "panorama_groups": len(_numbered_group_dirs(root / "panorama")),
        "panorama_raw": _count_group_media(root / "panorama", RAW_EXTS, "raw"),
        "panorama_hif": _count_group_media(root / "panorama", HIF_EXTS, "hif"),
        "exports": sum(
            _count_files(export_dir, EXPORT_EXTS)
            for export_dir in export_scan_directories(root)
        ),
        "contact_sheets": sum(1 for _ in root.rglob("*contact_sheet*.jpg")),
    }

    if workflow == "initial-cull" or (
        workflow == "auto" and report.inferred_stage != "ready-for-finalize"
    ):
        check_initial_cull(report, root)
    if workflow in ("auto", "finalize"):
        check_finalize(report, root, copy_to=copy_to)
    if workflow == "learn-style":
        check_learn_style(report, root)

    if not report.findings:
        _add(report, "info", "no-issues", "No workflow issues found.")
    report.status = decide_status(report)
    report.recommendations = recommend_next_steps(report)
    return report


def decide_status(report: DoctorReport) -> DecisionStatus:
    if any(finding.severity == "error" for finding in report.findings):
        if any(finding.code in {"missing-exports", "empty-exports"} for finding in report.findings):
            return "needs-lightroom-export"
        return "blocked"
    if any(finding.code == "unorganized-media" for finding in report.findings):
        return "needs-organize"
    if any(finding.code in {"cull-structure", "missing-ratings"} for finding in report.findings):
        return "blocked"
    if report.workflow == "finalize" and report.summary.get("exports", 0) == 0:
        return "needs-lightroom-export"
    return "ready"


def recommend_next_steps(report: DoctorReport) -> list[str]:
    path = shlex.quote(report.path)
    codes = {finding.code for finding in report.findings}
    recommendations: list[str] = []

    if report.status == "needs-organize":
        recommendations.append(f"Run `mt organize {path} --dry-run` before moving files.")
    elif report.status == "needs-lightroom-export":
        recommendations.append(
            "Export final picks from Lightroom into raw/Export or portrait/<n>/raw/Export, then rerun `mt status --workflow finalize`."
        )
    elif report.status == "blocked":
        if "missing-copy-to" in codes:
            recommendations.append(
                f"Rerun with an explicit external destination: `mt status {path} --workflow finalize --copy-to <destination-dir>`."
            )
        if "copy-to-inside-source" in codes:
            recommendations.append("Choose a --copy-to directory outside the source photo directory.")
        if "cull-structure" in codes or "missing-ratings" in codes:
            recommendations.append(f"Run `mt verify-cull {path}` and complete missing cull artifacts before continuing.")
    elif report.inferred_stage == "ready-for-finalize":
        recommendations.append(
            f"Validate the archive target with `mt status {path} --workflow finalize --copy-to <destination-dir>`."
        )
        recommendations.append(
            f"Run `mt finalize {path} --copy-to <destination-dir> --dry-run --scene <scene>` before real finalization."
        )
    elif report.inferred_stage in {"initial-cull-reviewed", "organized"}:
        recommendations.append("Continue Lightroom refinement or complete any reported cull warnings.")

    if "missing-hif-for-export" in codes:
        recommendations.append("Review missing HIF warnings before running HIF-only archive.")
    return recommendations


def check_initial_cull(report: DoctorReport, root: Path) -> None:
    loose_media = report.summary["loose_raw"] + report.summary["loose_hif"]
    if loose_media:
        _add(
            report,
            "warning",
            "unorganized-media",
            "Loose RAW/HIF files are present at the directory root; run mt organize before culling.",
        )

    if (root / "raw").is_dir() or (root / "hif").is_dir():
        cull_report = verify_cull.verify_directory(root)
        for issue in cull_report.issues:
            _add(report, "warning", "cull-structure", issue)

        total_raw = sum(counts.raw for counts in cull_report.counts.values())
        total_xmp = sum(counts.xmp for counts in cull_report.counts.values())
        if total_raw and total_xmp < total_raw:
            _add(
                report,
                "warning",
                "missing-ratings",
                "Some RAW files do not have lowercase .xmp sidecars yet.",
            )


def check_finalize(
    report: DoctorReport,
    root: Path,
    *,
    copy_to: Path | None,
) -> None:
    export_dirs = export_scan_directories(root)
    if not export_dirs:
        if report.workflow == "finalize":
            _add(
                report,
                "error",
                "missing-exports",
                "Finalize requires Lightroom exports in raw/Export or portrait/<n>/raw/Export.",
            )
        return

    selected_stems = selected_export_stems(root)
    if not selected_stems:
        _add(report, "error", "empty-exports", "Lightroom export directories exist but contain no final export files.")
        return

    matches = matching_hif_files(root, selected_stems)
    missing = sorted(selected_stems - set(matches))
    if missing:
        _add(
            report,
            "warning",
            "missing-hif-for-export",
            "Some Lightroom export stems have no matching root/portrait HIF: "
            + ", ".join(missing),
        )

    if report.workflow == "finalize":
        if copy_to is None:
            _add(report, "error", "missing-copy-to", "Finalize requires an explicit --copy-to destination.")
        else:
            destination = Path(copy_to).expanduser().resolve()
            if destination_is_inside_source(root, destination):
                _add(
                    report,
                    "error",
                    "copy-to-inside-source",
                    "--copy-to must be outside the source photo directory.",
                )


def check_learn_style(report: DoctorReport, root: Path) -> None:
    xmp_count = _count_tree(root, {".xmp"})
    export_count = report.summary["exports"]
    if not xmp_count and not export_count:
        _add(
            report,
            "warning",
            "no-refinement-evidence",
            "No XMP sidecars or Lightroom exports were found as style-learning evidence.",
        )


def render_report(report: DoctorReport) -> str:
    lines = [
        f"Workflow doctor: {report.path}",
        f"workflow: {report.workflow}",
        f"inferred stage: {report.inferred_stage}",
        f"status: {report.status}",
        "summary: "
        + ", ".join(f"{key}={value}" for key, value in sorted(report.summary.items())),
    ]
    for finding in report.findings:
        lines.append(f"{finding.severity.upper()} {finding.code}: {finding.message}")
    if report.recommendations:
        lines.append("recommendations:")
        lines.extend(f"- {item}" for item in report.recommendations)
    return "\n".join(lines)
