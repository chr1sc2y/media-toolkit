from __future__ import annotations

import argparse
from pathlib import Path

from media_toolkit import group_organize


ManifestEntry = group_organize.ManifestEntry
MoveOperation = group_organize.MoveOperation


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt panorama-organize",
        description="Move panorama RAW/HIF pairs into panorama/<group>/ folders.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory containing raw/ and hif/")
    parser.add_argument(
        "--manifest",
        help="TSV or CSV with columns stem and group. Defaults to panorama/panorama_manifest.tsv.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print planned moves without changing files.",
    )
    parser.add_argument(
        "--no-contact-sheets",
        action="store_true",
        help="Skip rebuilding root and panorama contact sheets after moving.",
    )
    return parser.parse_args(argv)


def read_manifest(path: Path) -> list[ManifestEntry]:
    return group_organize.read_manifest(path)


def build_move_plan(root: Path, entries: list[ManifestEntry]) -> list[MoveOperation]:
    return group_organize.build_move_plan(root, entries, "panorama")


def apply_move_plan(operations: list[MoveOperation]) -> None:
    group_organize.apply_move_plan(operations)


def run_command(command: list[str]) -> None:
    group_organize.run_command(command)


def rebuild_contact_sheets(root: Path) -> None:
    group_organize.rebuild_contact_sheets(
        root,
        "panorama",
        "Panorama",
        runner=run_command,
    )


def summarize(entries: list[ManifestEntry]) -> str:
    return group_organize.summarize(entries, "panorama")


def organize_panoramas(args: argparse.Namespace) -> int:
    return group_organize.organize_groups(
        args,
        group_kind="panorama",
        section_prefix="Panorama",
        rebuild_func=lambda root, group_kind, section_prefix: rebuild_contact_sheets(root),
    )


def main(argv: list[str] | None = None) -> int:
    return organize_panoramas(parse_args(argv))
