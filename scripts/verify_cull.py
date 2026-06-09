#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit import rawpy_tools


TEMP_ARTIFACT_NAMES = {
    ".codex_contact_tmp",
    ".codex_previews",
    "contact_sheets",
    "review_jpg",
}
ALLOWED_CONTACT_SHEETS = {
    Path("_contact_sheet.jpg"),
    Path("portrait/_contact_sheet.jpg"),
    Path("panorama/_contact_sheet.jpg"),
}


class FolderCounts:
    def __init__(self, raw: int = 0, hif: int = 0, xmp: int = 0):
        self.raw = raw
        self.hif = hif
        self.xmp = xmp


class VerificationReport:
    def __init__(self):
        self.counts: dict[str, FolderCounts] = {}
        self.issues: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.issues


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify initial-cull directory structure and generated sheets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory to verify")
    parser.add_argument(
        "--rawpy",
        action="store_true",
        help="Also verify each RAW can be opened and analyzed with rawpy/LibRaw.",
    )
    return parser.parse_args(argv)


def stems_for(directory: Path, pattern: str) -> set[str]:
    if not directory.exists():
        return set()
    return {path.stem for path in directory.glob(pattern) if path.is_file()}


def count_folder(raw_dir: Path, hif_dir: Path) -> FolderCounts:
    return FolderCounts(
        raw=len(stems_for(raw_dir, "*.ARW")),
        hif=len(stems_for(hif_dir, "*.HIF")),
        xmp=len(stems_for(raw_dir, "*.xmp")),
    )


def check_pairing(
    report: VerificationReport,
    label: str,
    raw_dir: Path,
    hif_dir: Path,
    *,
    require_xmp: bool,
) -> None:
    raw_stems = stems_for(raw_dir, "*.ARW")
    hif_stems = stems_for(hif_dir, "*.HIF")
    xmp_stems = stems_for(raw_dir, "*.xmp")
    report.counts[label] = FolderCounts(len(raw_stems), len(hif_stems), len(xmp_stems))

    for stem in sorted(raw_stems - hif_stems):
        report.issues.append(f"{label}: missing HIF for {stem}")
    if require_xmp:
        for stem in sorted(raw_stems - xmp_stems):
            report.issues.append(f"{label}: missing XMP for {stem}")


def numbered_children(directory: Path) -> list[Path]:
    if not directory.exists():
        return []
    return sorted(
        [path for path in directory.iterdir() if path.is_dir() and path.name.isdigit()],
        key=lambda path: int(path.name),
    )


def check_contact_sheets(report: VerificationReport, root: Path) -> None:
    if (root / "hif").exists() and not (root / "_contact_sheet.jpg").exists():
        report.issues.append("missing root _contact_sheet.jpg")

    portrait_dir = root / "portrait"
    if numbered_children(portrait_dir) and not (portrait_dir / "_contact_sheet.jpg").exists():
        report.issues.append("missing portrait/_contact_sheet.jpg")

    panorama_dir = root / "panorama"
    if numbered_children(panorama_dir) and not (panorama_dir / "_contact_sheet.jpg").exists():
        report.issues.append("missing panorama/_contact_sheet.jpg")

    for path in sorted(root.rglob("*contact_sheet*.jpg")):
        rel = path.relative_to(root)
        if rel not in ALLOWED_CONTACT_SHEETS:
            report.issues.append(f"redundant contact sheet remains: {rel}")


def check_temp_artifacts(report: VerificationReport, root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_dir() and path.name in TEMP_ARTIFACT_NAMES:
            report.issues.append(f"temporary artifact remains: {path.relative_to(root)}")


def check_rawpy_readability(report: VerificationReport, root: Path) -> None:
    for raw_file in rawpy_tools.collect_raw_files(root):
        try:
            rawpy_tools.analyze_raw(raw_file)
        except Exception as exc:
            report.issues.append(f"rawpy failed for {raw_file.relative_to(root)}: {exc}")


def verify_directory(
    root: Path,
    require_xmp: bool = False,
    check_rawpy: bool = False,
) -> VerificationReport:
    report = VerificationReport()
    check_pairing(report, "root", root / "raw", root / "hif", require_xmp=require_xmp)

    for child in numbered_children(root / "portrait"):
        check_pairing(
            report,
            f"portrait/{child.name}",
            child / "raw",
            child / "hif",
            require_xmp=require_xmp,
        )

    for child in numbered_children(root / "panorama"):
        check_pairing(
            report,
            f"panorama/{child.name}",
            child / "raw",
            child / "hif",
            require_xmp=require_xmp,
        )

    check_contact_sheets(report, root)
    check_temp_artifacts(report, root)
    if check_rawpy:
        check_rawpy_readability(report, root)
    return report


def print_report(report: VerificationReport) -> None:
    for label, counts in sorted(report.counts.items()):
        print(f"{label}: raw={counts.raw} hif={counts.hif} xmp={counts.xmp}")
    if report.issues:
        print("Issues:")
        for issue in report.issues:
            print(f"- {issue}")
    else:
        print("No issues found.")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1
    report = verify_directory(root, check_rawpy=args.rawpy)
    print_report(report)
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
