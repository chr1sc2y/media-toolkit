from __future__ import annotations

import argparse
import importlib
import runpy
import sys
from collections.abc import Callable
from pathlib import Path
from typing import TextIO

from media_toolkit.command_registry import COMMANDS, Command, resolve_command
from media_toolkit.path_input import normalize_directory_input


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"

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


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def prompt_for_directory(
    *,
    input_func: Callable[[str], str] = input,
    output: TextIO = sys.stdout,
) -> Path | None:
    while True:
        raw_input = input_func("Enter directory: ").strip()
        if not raw_input:
            print("Directory is required.", file=output)
            continue
        try:
            directory = normalize_directory_input(raw_input)
        except OSError:
            print(f"Invalid path: {raw_input}", file=output)
            continue
        if not directory.exists():
            print(f"Directory does not exist: {directory}", file=output)
            continue
        if not directory.is_dir():
            print(f"Not a directory: {directory}", file=output)
            continue
        return directory


def resolve_default_directory(
    *,
    input_func: Callable[[str], str] = input,
    cwd_func: Callable[[], Path] = Path.cwd,
    output: TextIO = sys.stdout,
) -> Path | None:
    cwd = cwd_func().resolve()
    response = input_func(
        f"Run on current directory ({cwd})? Type y to confirm: "
    )
    if response.strip() == "y":
        return cwd
    return prompt_for_directory(input_func=input_func, output=output)


def build_script_argv(
    command: Command,
    args: list[str],
    *,
    input_func: Callable[[str], str] = input,
    cwd_func: Callable[[], Path] = Path.cwd,
    output: TextIO | None = None,
    interactive: bool | None = None,
) -> list[str] | None:
    message_output = output if output is not None else sys.stderr
    script_args = list(args)
    help_requested = any(arg in ("-h", "--help") for arg in script_args)
    if command.default_cwd and not help_requested and not has_positional_argument(
        script_args, command.options_with_values
    ):
        if interactive if interactive is not None else is_interactive():
            directory = resolve_default_directory(
                input_func=input_func,
                cwd_func=cwd_func,
                output=message_output,
            )
            if directory is None:
                return None
            script_args.insert(0, str(directory))
        else:
            print(
                "mt: directory required when stdin is not interactive "
                "(pass a path argument).",
                file=message_output,
            )
            return None
    return [command.script_name, *script_args]


def build_command_args(
    command: Command,
    args: list[str],
    *,
    input_func: Callable[[str], str] = input,
    cwd_func: Callable[[], Path] = Path.cwd,
    output: TextIO | None = None,
    interactive: bool | None = None,
) -> list[str] | None:
    script_argv = build_script_argv(
        command,
        args,
        input_func=input_func,
        cwd_func=cwd_func,
        output=output,
        interactive=interactive,
    )
    if script_argv is None:
        return None
    return script_argv[1:]


def command_table() -> str:
    lines = []
    for command in COMMANDS:
        if not command.visible:
            continue
        lines.append(f"  mt {command.canonical:<16} {command.help}")
    return "\n".join(lines)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt",
        description="Media Toolkit command launcher.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"Commands:\n{command_table()}\n\n"
            "Examples:\n"
            "  mt finalize /path/to/photos --copy-to /Volumes/SDCARD/DCIM/100MSDCF --photos-album Sony --scene flower-field\n"
            "  mt hif-prune /path/to/photos --mode plan --scene flower-field\n"
            "  mt organize /path/to/photos --dry-run --verbose\n"
            "  mt fill-locations --describe\n"
            "  mt contact-sheet /path/to/photos --export-only\n"
            "  mt status /path/to/photos\n"
            "  mt batch-report /path/to/photos\n"
            "  mt doctor /path/to/photos --workflow finalize --copy-to /Volumes/SDCARD/DCIM/100MSDCF\n"
            "  mt preflight-run finalize /path/to/photos --copy-to /Volumes/SDCARD/DCIM/100MSDCF --scene grassland\n"
            "  mt lr-apply /path/to/photos --plan lr_plan_reviewed.tsv --style flower-rich --dry-run\n"
            "  mt styles flower-rich\n"
            "  mt learn-style /path/to/photos --scene flower-field\n"
            "  mt workflows finalize"
        ),
    )
    parser.add_argument("command", nargs="?", help="Command or alias to run.")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments passed to the command.")
    return parser.parse_args(argv)


def _normalize_exit_code(value) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    print(value, file=sys.stderr)
    return 1


def run_module(command: Command, args: list[str]) -> int:
    if command.module_name is None:
        return run_script(command, args)

    command_args = build_command_args(command, args)
    if command_args is None:
        return 1

    try:
        module = importlib.import_module(command.module_name)
        return _normalize_exit_code(module.main(command_args))
    except SystemExit as exc:
        return _normalize_exit_code(exc.code)


def run_script(command: Command, args: list[str]) -> int:
    script_path = SCRIPTS_DIR / command.script_name
    if not script_path.exists():
        print(f"mt: script not found: {script_path}", file=sys.stderr)
        return 1

    old_argv = sys.argv[:]
    old_path = sys.path[:]
    try:
        script_argv = build_script_argv(command, args)
        if script_argv is None:
            return 1
        sys.argv = script_argv
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

    return run_module(command, namespace.args)


if __name__ == "__main__":
    raise SystemExit(main())
