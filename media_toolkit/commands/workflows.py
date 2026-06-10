from __future__ import annotations

import argparse
import json

from media_toolkit.workflows import (
    get_workflow,
    load_workflow_registry,
    render_workflow_detail,
    render_workflow_summary,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt workflows",
        description="Show the agent-readable media workflow registry."
    )
    parser.add_argument("workflow", nargs="?", help="Workflow id to show.")
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.json:
        data = get_workflow(args.workflow) if args.workflow else load_workflow_registry()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.workflow:
        workflow = get_workflow(args.workflow)
        print(render_workflow_detail(workflow))
        return 0

    print(render_workflow_summary())
    return 0
