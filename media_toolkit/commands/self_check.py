from __future__ import annotations

import argparse
import json

from media_toolkit.self_check import (
    render_self_check,
    run_self_checks,
    self_check_ok,
    self_check_payload,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt self-check",
        description="Run read-only registry and entrypoint health checks.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results = run_self_checks()
    if args.json:
        print(json.dumps(self_check_payload(results), ensure_ascii=False, indent=2))
    else:
        print(render_self_check(results))
    return 0 if self_check_ok(results) else 1
