from __future__ import annotations

import argparse
from pathlib import Path

from media_toolkit import group_organize


ManifestEntry = group_organize.ManifestEntry
MoveOperation = group_organize.MoveOperation


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt portrait-organize",
        description="Move portrait RAW/HIF pairs into portrait/<group>/ folders.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory containing raw/ and hif/")
    parser.add_argument(
        "--manifest",
        help="TSV or CSV with columns stem and group. Defaults to portrait/portrait_manifest.tsv.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and print planned moves without changing files.",
    )
    parser.add_argument(
        "--no-contact-sheets",
        action="store_true",
        help="Skip rebuilding root and portrait contact sheets after moving.",
    )
    return parser.parse_args(argv)


def read_manifest(path: Path) -> list[ManifestEntry]:
    return group_organize.read_manifest(path)


def build_move_plan(root: Path, entries: list[ManifestEntry]) -> list[MoveOperation]:
    return group_organize.build_move_plan(root, entries, "portrait")


def apply_move_plan(operations: list[MoveOperation]) -> None:
    group_organize.apply_move_plan(operations)


def run_command(command: list[str]) -> None:
    group_organize.run_command(command)


def rebuild_contact_sheets(root: Path) -> None:
    group_organize.rebuild_contact_sheets(
        root,
        "portrait",
        "Portrait",
        runner=run_command,
    )


def summarize(entries: list[ManifestEntry]) -> str:
    return group_organize.summarize(entries, "portrait")


def organize_portraits(args: argparse.Namespace) -> int:
    return group_organize.organize_groups(
        args,
        group_kind="portrait",
        section_prefix="Portrait",
        rebuild_func=lambda root, group_kind, section_prefix: rebuild_contact_sheets(root),
    )


def main(argv: list[str] | None = None) -> int:
    return organize_portraits(parse_args(argv))
