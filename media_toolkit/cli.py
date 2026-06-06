from __future__ import annotations

import argparse
import runpy
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


@dataclass(frozen=True)
class Command:
    canonical: str
    aliases: tuple[str, ...]
    script_name: str
    help: str
    default_cwd: bool = False
    options_with_values: tuple[str, ...] = ()


COMMANDS = (
    Command(
        canonical="featured",
        aliases=("f", "feature"),
        script_name="extract_featured_raw.py",
        help="Copy files matching raw/ stems into featured/.",
        default_cwd=True,
    ),
    Command(
        canonical="organize",
        aliases=("o", "org"),
        script_name="organize.py",
        help="Move camera media into per-directory type folders.",
        default_cwd=True,
        options_with_values=("--type",),
    ),
    Command(
        canonical="fill-locations",
        aliases=("loc", "locations", "fill-location"),
        script_name="fill_missing_photo_locations.py",
        help="Plan or apply Apple Photos missing-location fixes.",
    ),
    Command(
        canonical="contact-sheet",
        aliases=("sheet", "sheets"),
        script_name="generate_contact_sheets.py",
        help="Generate contact sheet thumbnails and a manifest.",
        default_cwd=True,
        options_with_values=(
            "--output",
            "--exclude-dir",
            "--cols",
            "--rows",
            "--thumb-width",
            "--thumb-height",
            "--label-height",
            "--quality",
        ),
    ),
    Command(
        canonical="image-compress",
        aliases=("imgzip", "compress-images"),
        script_name="compress_images_under_size.py",
        help="Compress oversized JPG/JPEG files under a byte cap.",
        default_cwd=True,
        options_with_values=("--max-bytes",),
    ),
    Command(
        canonical="drone",
        aliases=("drone-compress",),
        script_name="compress_drone_video.py",
        help="Compress drone videos with the existing preset script.",
        default_cwd=True,
    ),
    Command(
        canonical="png-to-jpg",
        aliases=("pngjpg", "png"),
        script_name="png_to_jpg.py",
        help="Convert PNG images to JPG with the existing preset script.",
        default_cwd=True,
    ),
)


ALIASES = {
    alias: command
    for command in COMMANDS
    for alias in (command.canonical, *command.aliases)
}


def resolve_command(name: str) -> Command:
    try:
        return ALIASES[name]
    except KeyError as exc:
        raise ValueError(f"unknown command: {name}") from exc


def has_positional_argument(args: list[str], options_with_values: tuple[str, ...]) -> bool:
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg == "--":
            return True
        if arg.startswith("-"):
            option = arg.split("=", 1)[0]
            if option in options_with_values and "=" not in arg:
                skip_next = True
            continue
        return True
    return False


def build_script_argv(command: Command, args: list[str]) -> list[str]:
    script_args = list(args)
    if command.default_cwd and not has_positional_argument(script_args, command.options_with_values):
        script_args.insert(0, str(Path.cwd()))
    return [command.script_name, *script_args]


def command_table() -> str:
    lines = []
    for command in COMMANDS:
        alias_text = ", ".join(command.aliases)
        lines.append(f"  {command.canonical:<16} ({alias_text})  {command.help}")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt",
        description="Media Toolkit command launcher.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Commands:\n{command_table()}\n\nExamples:\n  mt f\n  mt o --dry-run\n  mt loc --describe\n  mt sheet --export-only",
    )
    parser.add_argument("command", nargs="?", help="Command or alias to run.")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the command.")
    return parser.parse_args(argv)


def run_script(command: Command, args: list[str]) -> int:
    script_path = SCRIPTS_DIR / command.script_name
    if not script_path.exists():
        print(f"mt: script not found: {script_path}", file=sys.stderr)
        return 1

    old_argv = sys.argv[:]
    old_path = sys.path[:]
    try:
        sys.argv = build_script_argv(command, args)
        if str(REPO_ROOT) not in sys.path:
            sys.path.insert(0, str(REPO_ROOT))
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as exc:
        if exc.code is None:
            return 0
        if isinstance(exc.code, int):
            return exc.code
        print(exc.code, file=sys.stderr)
        return 1
    finally:
        sys.argv = old_argv
        sys.path = old_path
    return 0


def main(argv: list[str] | None = None) -> int:
    namespace = parse_args(sys.argv[1:] if argv is None else argv)
    if not namespace.command:
        print("Media Toolkit (mt)\n")
        print("Commands:")
        print(command_table())
        print("\nUse 'mt <command> --help' for command-specific help.")
        return 0

    try:
        command = resolve_command(namespace.command)
    except ValueError as exc:
        print(f"mt: {exc}", file=sys.stderr)
        print("Run 'mt' to list available commands.", file=sys.stderr)
        return 2

    return run_script(command, namespace.args)


if __name__ == "__main__":
    raise SystemExit(main())
