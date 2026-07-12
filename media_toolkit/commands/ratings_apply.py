from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from media_toolkit import rawpy_tools


@dataclass(frozen=True)
class RatingAssignment:
    raw_file: Path
    rating: int


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt ratings-apply",
        description="Apply a reviewed path/rating TSV manifest to RAW XMP sidecars.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory containing the manifest paths")
    parser.add_argument(
        "--manifest",
        default="ratings.tsv",
        help="Reviewed TSV with path and rating columns; relative paths resolve under the shoot directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print assignments without writing XMP sidecars.",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Allow a targeted correction manifest to omit other RAW files. Never use for a new cull.",
    )
    return parser.parse_args(argv)


def resolve_manifest(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def read_manifest(root: Path, manifest: Path) -> list[RatingAssignment]:
    if not manifest.is_file():
        raise ValueError(f"ratings manifest does not exist: {manifest}")

    assignments: list[RatingAssignment] = []
    seen: set[Path] = set()
    with manifest.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = [field for field in ("path", "rating") if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"ratings manifest is missing column(s): {', '.join(missing)}")
        for line_number, row in enumerate(reader, start=2):
            raw_file = rawpy_tools.resolve_raw_path(
                root,
                row.get("path") or "",
                context=f"manifest row {line_number}",
            )
            if raw_file in seen:
                raise ValueError(
                    f"manifest row {line_number}: duplicate RAW path: {row.get('path')!r}"
                )
            seen.add(raw_file)
            rating_text = (row.get("rating") or "").strip()
            try:
                rating = int(rating_text)
            except ValueError as exc:
                raise ValueError(
                    f"manifest row {line_number}: rating must be an integer from 0 to 5"
                ) from exc
            if str(rating) != rating_text or not 0 <= rating <= 5:
                raise ValueError(
                    f"manifest row {line_number}: rating must be an integer from 0 to 5"
                )
            assignments.append(RatingAssignment(raw_file=raw_file, rating=rating))
    if not assignments:
        raise ValueError("ratings manifest contains no assignments")
    return assignments


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

    manifest = resolve_manifest(root, args.manifest)
    try:
        assignments = read_manifest(root, manifest)
    except (OSError, UnicodeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if not args.allow_partial:
        all_raw_files = {path.resolve() for path in rawpy_tools.collect_raw_files(root)}
        assigned_files = {assignment.raw_file.resolve() for assignment in assignments}
        omitted = sorted(
            all_raw_files - assigned_files,
            key=lambda path: str(path).casefold(),
        )
        if omitted:
            preview = ", ".join(
                path.relative_to(root).as_posix() for path in omitted[:5]
            )
            suffix = "" if len(omitted) <= 5 else f" ... (+{len(omitted) - 5})"
            print(
                f"Error: ratings manifest omits {len(omitted)} RAW file(s): "
                f"{preview}{suffix}. Use --allow-partial only for a targeted correction.",
                file=sys.stderr,
            )
            return 2

    for assignment in assignments:
        xmp_file = assignment.raw_file.with_suffix(".xmp")
        if not xmp_file.exists():
            continue
        try:
            rawpy_tools.read_xmp_properties(xmp_file)
        except (OSError, UnicodeError, ValueError) as exc:
            relative = xmp_file.relative_to(root)
            print(f"Error: invalid existing XMP {relative}: {exc}", file=sys.stderr)
            return 2

    action = "Would rate" if args.dry_run else "Rated"
    for assignment in assignments:
        relative = assignment.raw_file.relative_to(root)
        if not args.dry_run:
            try:
                rawpy_tools.write_rating_xmp_sidecar(
                    assignment.raw_file,
                    assignment.rating,
                )
            except (OSError, UnicodeError, ValueError) as exc:
                print(f"Error updating {relative}: {exc}", file=sys.stderr)
                return 1
        print(f"{action} {relative}: {assignment.rating}")
    print(f"{action} {len(assignments)} RAW file(s) from {manifest}.")
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    print(f"Manifest SHA-256: {digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
