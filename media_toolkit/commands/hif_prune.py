from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from media_toolkit.hif_prune import (
    HifPruneMode,
    apply_reviewed_prune_plan,
    build_prune_plan,
    execute_prune_plan,
)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt hif-prune",
        description="Prune redundant source-side HIF previews after finalization.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Photo directory to inspect.")
    parser.add_argument(
        "--mode",
        choices=[mode.value for mode in HifPruneMode],
        default=HifPruneMode.PLAN.value,
        help="Cleanup mode. aggressive permanently deletes planned duplicate HIF files; plan only writes manifests.",
    )
    parser.add_argument(
        "--confirm-delete",
        action="store_true",
        help="Explicitly confirm permanent deletion when --mode aggressive is used.",
    )
    parser.add_argument(
        "--apply-plan",
        type=Path,
        help="Reviewed plan JSON to validate and apply in aggressive mode.",
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


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1

    mode = HifPruneMode(args.mode)
    if mode == HifPruneMode.AGGRESSIVE and not args.confirm_delete:
        print(
            "Error: --mode aggressive requires --confirm-delete.",
            file=sys.stderr,
        )
        return 2
    if mode == HifPruneMode.AGGRESSIVE and args.apply_plan is None:
        print(
            "Error: --mode aggressive requires --apply-plan <reviewed.json>.",
            file=sys.stderr,
        )
        return 2
    if mode == HifPruneMode.AGGRESSIVE and args.dry_run:
        print(
            "Error: --dry-run cannot be combined with --mode aggressive; "
            "use --mode plan for a non-destructive review.",
            file=sys.stderr,
        )
        return 2
    if mode == HifPruneMode.PLAN and args.apply_plan is not None:
        print(
            "Error: --apply-plan is only valid with --mode aggressive.",
            file=sys.stderr,
        )
        return 2

    manifest = args.manifest or root / "hif_prune_manifest.json"
    plan = None
    try:
        if mode == HifPruneMode.AGGRESSIVE:
            assert args.apply_plan is not None
            result = apply_reviewed_prune_plan(
                args.apply_plan,
                root=root,
                manifest_path=args.manifest,
                confirmed=args.confirm_delete,
            )
        else:
            plan = build_prune_plan(root)
            result = execute_prune_plan(
                plan,
                mode=mode,
                manifest_path=manifest,
                dry_run=args.dry_run,
            )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print("HIF PRUNE")
    print(f"Scene: {args.scene}")
    print(f"Mode: {mode.value}")
    print(f"Root: {root}")
    if plan is not None:
        print(f"Kept: {len(plan.keep)}")
        print(f"Warnings: {len(plan.warnings)}")
    print(f"Planned delete: {result.planned_delete_count}")
    print(f"Deleted: {result.deleted_count}")
    print(f"Manifest: {result.manifest_path}")
    return 0
