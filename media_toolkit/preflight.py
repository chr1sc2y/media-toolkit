from __future__ import annotations

from dataclasses import asdict, dataclass, field
from io import StringIO
from pathlib import Path
from contextlib import redirect_stderr, redirect_stdout

from media_toolkit.commands import finalize
from media_toolkit.finalize_workflow import (
    find_finalize_directories,
    find_photos_import_directories,
)
from media_toolkit.workflow_doctor import DoctorReport, inspect_directory


@dataclass
class PreflightReport:
    workflow: str
    decision: str
    status: str
    dry_run_exit_code: int | None = None
    dry_run_output: str = ""
    reasons: list[str] = field(default_factory=list)
    doctor: dict[str, object] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.decision == "GO"

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["ok"] = self.ok
        return data


def _blocking_reasons(doctor_report: DoctorReport) -> list[str]:
    reasons = [
        f"{finding.code}: {finding.message}"
        for finding in doctor_report.findings
        if finding.severity == "error"
    ]
    for finding in doctor_report.findings:
        if finding.code == "missing-hif-for-export":
            reasons.append(f"{finding.code}: {finding.message}")
    if doctor_report.status != "ready" and not reasons:
        reasons.append(f"status is {doctor_report.status}")
    return reasons


def preflight_finalize(
    source: Path,
    *,
    copy_to: Path,
    scene: str,
    hif_only: bool = False,
    photos_album: str = "Sony",
    recursive: bool = True,
) -> PreflightReport:
    source = Path(source).expanduser().resolve()
    if recursive:
        bases = find_finalize_directories(source)
        photos_bases = find_photos_import_directories(source)
        if not bases and (hif_only or not photos_bases):
            return PreflightReport(
                workflow="finalize",
                decision="NO-GO",
                status="blocked",
                reasons=["no finalize directories with raw/ found"],
                doctor={
                    "path": str(source),
                    "inferred_stage": "recursive-finalize",
                    "status": "blocked",
                    "summary": {"finalize_directories": 0},
                    "findings": [],
                },
            )
        doctor_reports = [
            inspect_directory(base, workflow="finalize", copy_to=copy_to)
            for base in bases
        ]
        reasons = []
        for report in doctor_reports:
            reasons.extend(_blocking_reasons(report))
        doctor_report = DoctorReport(
            path=str(source),
            workflow="finalize",
            inferred_stage="recursive-finalize",
            status="ready" if not reasons else "blocked",
        )
        doctor_report.summary["finalize_directories"] = len(bases)
        doctor_report.summary["photos_import_directories"] = len(photos_bases)
        doctor_report.findings = [
            finding
            for report in doctor_reports
            for finding in report.findings
            if finding.severity == "error"
        ]
    else:
        doctor_report = inspect_directory(source, workflow="finalize", copy_to=copy_to)
        reasons = _blocking_reasons(doctor_report)
    if reasons:
        return PreflightReport(
            workflow="finalize",
            decision="NO-GO",
            status=doctor_report.status,
            reasons=reasons,
            doctor=doctor_report.to_dict(),
        )

    argv = [
        str(source),
        "--copy-to",
        str(Path(copy_to).expanduser()),
        "--scene",
        scene,
        "--dry-run",
    ]
    if recursive:
        argv.append("--recursive")
    if hif_only:
        argv.append("--hif-only")
    else:
        argv.extend(["--photos-album", photos_album])

    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = finalize.main(argv)
    dry_run_output = stdout.getvalue()
    if stderr.getvalue():
        dry_run_output += stderr.getvalue()

    decision = "GO" if exit_code == 0 else "NO-GO"
    reasons = [] if exit_code == 0 else [f"finalize dry-run exited with {exit_code}"]
    return PreflightReport(
        workflow="finalize",
        decision=decision,
        status=doctor_report.status,
        dry_run_exit_code=exit_code,
        dry_run_output=dry_run_output,
        reasons=reasons,
        doctor=doctor_report.to_dict(),
    )


def render_preflight_report(report: PreflightReport) -> str:
    lines = [
        f"Preflight {report.workflow}: {report.decision}",
        f"status: {report.status}",
    ]
    if report.reasons:
        lines.append("reasons:")
        lines.extend(f"- {reason}" for reason in report.reasons)
    if report.doctor:
        lines.append("")
        lines.append(f"source: {report.doctor['path']}")
        lines.append(f"stage: {report.doctor['inferred_stage']}")
        summary = report.doctor.get("summary", {})
        if isinstance(summary, dict):
            lines.append(
                "summary: "
                + ", ".join(f"{key}={value}" for key, value in sorted(summary.items()))
            )
        findings = report.doctor.get("findings", [])
        if findings:
            lines.append("findings:")
            for finding in findings:
                if isinstance(finding, dict):
                    lines.append(
                        f"- {str(finding.get('severity', '')).upper()} "
                        f"{finding.get('code')}: {finding.get('message')}"
                    )
    if report.dry_run_output:
        lines.append("")
        lines.append("dry-run output:")
        lines.append(report.dry_run_output.rstrip())
    return "\n".join(lines)
