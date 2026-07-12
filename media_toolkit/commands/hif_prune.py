from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_toolkit.hif_prune import (
    HifPruneMode,
    build_prune_plan,
    execute_prune_plan,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt hif-prune",
        description="Prune redundant source-side HIF previews after finalization.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Photo directory to inspect.")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in HifPruneMode],
        default=HifPruneMode.AGGRESSIVE.value,
        help="Cleanup mode. aggressive permanently deletes planned duplicate HIF files; plan only writes manifests.",
    )
    parser.add_argument(
        "--scene",
        default="general-travel",
        help="Scene category label for reports.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        help="Path for the JSON manifest. A TSV sibling is written beside it.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Write the cleanup plan without deleting files.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

    mode = HifPruneMode(args.mode)
    manifest = args.manifest or root / "hif_prune_manifest.json"
    plan = build_prune_plan(root)
    result = execute_prune_plan(
        plan,
        mode=mode,
        manifest_path=manifest,
        dry_run=args.dry_run,
    )

    print("HIF PRUNE")
    print(f"Scene: {args.scene}")
    print(f"Mode: {mode.value}")
    print(f"Root: {root}")
    print(f"Kept: {len(plan.keep)}")
    print(f"Warnings: {len(plan.warnings)}")
    print(f"Planned delete: {result.planned_delete_count}")
    print(f"Deleted: {result.deleted_count}")
    print(f"Manifest: {result.manifest_path}")
    return 0
