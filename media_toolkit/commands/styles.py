from __future__ import annotations

import argparse
import json

from media_toolkit.style_profiles import (
    get_style_profile,
    list_style_profiles,
    load_style_profile_registry,
    render_style_detail,
    render_style_summary,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt styles",
        description="Show agent-readable Lightroom scene style profiles.",
    )
    parser.add_argument("profile", nargs="?", help="Style profile id to show.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.json:
        data = get_style_profile(args.profile) if args.profile else load_style_profile_registry()
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if args.profile:
        print(render_style_detail(get_style_profile(args.profile)))
        return 0
    print(render_style_summary())
    return 0
