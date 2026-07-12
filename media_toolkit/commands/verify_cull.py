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
HIF_EXTENSIONS = {".hif", ".heif", ".heic"}


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
        prog="mt verify-cull",
        description="Verify initial-cull structure, XMP ratings/markers, and generated sheets.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory to verify")
    parser.add_argument(
        "--rawpy",
        action="store_true",
        help="Also verify each RAW can be opened and analyzed with rawpy/LibRaw.",
    )
    parser.add_argument(
        "--legacy-structure-only",
        action="store_true",
        help="Compatibility mode: skip required XMP rating and marker checks.",
    )
    return parser.parse_args(argv)


def files_by_stem(directory: Path, extensions: set[str]) -> dict[str, Path]:
    if not directory.exists():
        return {}
    return {
        path.stem: path
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in extensions
    }


def lowercase_xmp_by_stem(directory: Path) -> dict[str, Path]:
    if not directory.exists():
        return {}
    return {
        path.stem: path
        for path in directory.iterdir()
        if path.is_file() and path.suffix == ".xmp"
    }


def count_folder(raw_dir: Path, hif_dir: Path) -> FolderCounts:
    return FolderCounts(
        raw=len(files_by_stem(raw_dir, rawpy_tools.RAW_EXTS)),
        hif=len(files_by_stem(hif_dir, HIF_EXTENSIONS)),
        xmp=len(lowercase_xmp_by_stem(raw_dir)),
    )


def check_pairing(
    report: VerificationReport,
    label: str,
    raw_dir: Path,
    hif_dir: Path,
    *,
    require_xmp: bool,
) -> None:
    raw_files = files_by_stem(raw_dir, rawpy_tools.RAW_EXTS)
    hif_files = files_by_stem(hif_dir, HIF_EXTENSIONS)
    xmp_files = lowercase_xmp_by_stem(raw_dir)
    raw_stems = set(raw_files)
    hif_stems = set(hif_files)
    xmp_stems = set(xmp_files)
    report.counts[label] = FolderCounts(len(raw_stems), len(hif_stems), len(xmp_stems))

    for stem in sorted(raw_stems - hif_stems):
        raw_file = raw_files[stem]
        if raw_file.suffix.lower() == ".dng" and stem.lower().endswith("-pano"):
            continue
        report.issues.append(f"{label}: missing HIF for {stem}")
    if require_xmp:
        for stem in sorted(raw_stems - xmp_stems):
            report.issues.append(f"{label}: missing XMP for {stem}")
        for stem in sorted(raw_stems & xmp_stems):
            check_xmp_metadata(
                report,
                label,
                raw_files[stem],
                xmp_files[stem],
            )


def check_xmp_metadata(
    report: VerificationReport,
    label: str,
    raw_file: Path,
    xmp_file: Path,
) -> None:
    try:
        properties = rawpy_tools.read_xmp_properties(xmp_file)
    except (OSError, UnicodeError, ValueError) as exc:
        report.issues.append(f"{label}: invalid XMP for {raw_file.stem}: {exc}")
        return

    rating_text = properties.get("xmp:Rating")
    try:
        rating = int(rating_text) if rating_text is not None else None
    except ValueError:
        rating = None
    if rating is None:
        report.issues.append(f"{label}: missing or invalid rating for {raw_file.stem}")
    elif not 0 <= rating <= 5:
        report.issues.append(f"{label}: rating must be 0..5 for {raw_file.stem}")

    expected = {
        "crs:HasSettings": "True",
        "crs:AlreadyApplied": "False",
        "photoshop:SidecarForExtension": raw_file.suffix.lstrip(".").upper(),
        "dc:format": rawpy_tools.xmp_format_for_raw(raw_file),
        "xmpMM:PreservedFileName": raw_file.name,
    }
    for key, expected_value in expected.items():
        actual = properties.get(key)
        if actual is None:
            report.issues.append(f"{label}: missing {key} for {raw_file.stem}")
        elif actual != expected_value:
            report.issues.append(
                f"{label}: invalid {key} for {raw_file.stem}: "
                f"expected {expected_value!r}, got {actual!r}"
            )


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
    require_xmp: bool = True,
    check_rawpy: bool = False,
) -> VerificationReport:
    report = VerificationReport()
    raw_directories = sorted(
        [path for path in root.rglob("raw") if path.is_dir()],
        key=lambda path: str(path.relative_to(root)).lower(),
    )
    if not raw_directories:
        raw_directories = [root / "raw"]
    for raw_dir in raw_directories:
        base = raw_dir.parent
        label = "root" if base == root else base.relative_to(root).as_posix()
        check_pairing(
            report,
            label,
            raw_dir,
            base / "hif",
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
    report = verify_directory(
        root,
        require_xmp=not args.legacy_structure_only,
        check_rawpy=args.rawpy,
    )
    print_report(report)
    return 0 if report.ok else 1
