from __future__ import annotations

import argparse
import json

from media_toolkit.command_registry import command_registry_dict, resolve_command


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt commands",
        description="Show the agent-readable command registry.",
    )
    parser.add_argument("command", nargs="?", help="Command id to show.")
    parser.add_argument("--json", action="store_true", help="Print JSON.")
    return parser.parse_args(argv)


def render_command(command_id: str) -> str:
    command = resolve_command(command_id)
    lines = [f"{command.canonical}: {command.help}"]
    if command.aliases:
        lines.append(f"aliases: {', '.join(command.aliases)}")
    if command.module_name:
        lines.append(f"module: {command.module_name}")
    else:
        lines.append(f"compatibility script: {command.script_name}")
    if command.side_effects:
        lines.append(f"side effects: {', '.join(command.side_effects)}")
    lines.append(f"default cwd: {str(command.default_cwd).lower()}")
    lines.append(f"supports dry-run: {str(command.supports_dry_run).lower()}")
    lines.append(f"requires destination: {str(command.requires_destination).lower()}")
    return "\n".join(lines)


def render_summary() -> str:
    lines = ["Agent commands:"]
    for command in command_registry_dict(visible_only=True)["commands"]:
        migrated = "module" if command["module_name"] else "script"
        effects = ", ".join(command["side_effects"]) if command["side_effects"] else "read/inspect"
        lines.append(f"- {command['canonical']}: {migrated}; effects={effects}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.json:
        data = (
            resolve_command(args.command).to_dict()
            if args.command
            else command_registry_dict(visible_only=True)
        )
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0
    if args.command:
        print(render_command(args.command))
        return 0
    print(render_summary())
    return 0
