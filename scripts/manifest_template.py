#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit.manifest_organize import read_manifest


class PairResult:
    def __init__(self, paired: list[str], raw_only: list[str], hif_only: list[str]):
        self.paired = paired
        self.raw_only = raw_only
        self.hif_only = hif_only


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a portrait/panorama manifest template from root RAW/HIF pairs.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory containing root raw/ and hif/")
    parser.add_argument(
        "--kind",
        required=True,
        choices=("portrait", "panorama"),
        help="Manifest type to generate.",
    )
    parser.add_argument(
        "--output",
        help="Output manifest path. Defaults to <kind>/<kind>_manifest.tsv.",
    )
    parser.add_argument(
        "--preserve-existing",
        action="store_true",
        help="Keep existing group values for stems already in the manifest.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing manifest instead of refusing.",
    )
    return parser.parse_args(argv)


def stems_for(directory: Path, pattern: str) -> set[str]:
    if not directory.exists():
        return set()
    return {path.stem for path in directory.glob(pattern) if path.is_file()}


def collect_paired_stems(root: Path) -> PairResult:
    raw_stems = stems_for(root / "raw", "*.ARW")
    hif_stems = stems_for(root / "hif", "*.HIF")
    paired = sorted(raw_stems & hif_stems)
    raw_only = sorted(raw_stems - hif_stems)
    hif_only = sorted(hif_stems - raw_stems)
    return PairResult(paired, raw_only, hif_only)


def default_manifest_path(root: Path, kind: str) -> Path:
    return root / kind / f"{kind}_manifest.tsv"


def existing_groups(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {entry.stem: entry.group for entry in read_manifest(path)}


def write_template(
    output: Path,
    stems: list[str],
    preserve_existing: bool = False,
) -> None:
    groups = existing_groups(output) if preserve_existing else {}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        handle.write("stem\tgroup\n")
        for stem in stems:
            handle.write(f"{stem}\t{groups.get(stem, '')}\n")


def generate_template(args: argparse.Namespace) -> int:
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

    output = (
        Path(args.output).expanduser().resolve()
        if args.output
        else default_manifest_path(root, args.kind)
    )
    if output.exists() and not args.force and not args.preserve_existing:
        print(
            f"Error: manifest already exists: {output}. "
            "Use --preserve-existing or --force.",
            file=sys.stderr,
        )
        return 1

    result = collect_paired_stems(root)
    if not result.paired:
        print("No paired root RAW/HIF files found.")
        return 0

    write_template(output, result.paired, preserve_existing=args.preserve_existing)
    print(f"Wrote {len(result.paired)} row(s): {output}")
    if result.raw_only:
        print(f"RAW without HIF: {', '.join(result.raw_only)}")
    if result.hif_only:
        print(f"HIF without RAW: {', '.join(result.hif_only)}")
    return 0


if __name__ == "__main__":
    sys.exit(generate_template(parse_args()))
