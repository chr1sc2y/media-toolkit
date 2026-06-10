from __future__ import annotations

import argparse
import runpy
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


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
    visible: bool = True


COMMANDS = (
    Command(
        canonical="finalize",
        aliases=(),
        script_name="finalize.py",
        help="Copy matching original HIF previews to an SD card folder and import exports into Photos.",
        default_cwd=True,
        options_with_values=("--copy-to", "--scene", "--photos-album"),
    ),
    Command(
        canonical="featured",
        aliases=("f", "feature"),
        script_name="extract_featured_raw.py",
        help="Compatibility shortcut for old featured HIF extraction.",
        default_cwd=True,
        options_with_values=("--copy-to",),
        visible=False,
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
            "--final-overview",
            "--section-prefix",
        ),
    ),
    Command(
        canonical="portrait-organize",
        aliases=("portraits",),
        script_name="portrait_organize.py",
        help="Move portrait RAW/HIF pairs from a manifest and rebuild sheets.",
        default_cwd=True,
        options_with_values=("--manifest",),
    ),
    Command(
        canonical="panorama-organize",
        aliases=("panoramas",),
        script_name="panorama_organize.py",
        help="Move panorama RAW/HIF pairs from a manifest and rebuild sheets.",
        default_cwd=True,
        options_with_values=("--manifest",),
    ),
    Command(
        canonical="manifest-template",
        aliases=("manifest",),
        script_name="manifest_template.py",
        help="Create portrait or panorama manifest templates from root pairs.",
        default_cwd=True,
        options_with_values=("--kind", "--output"),
    ),
    Command(
        canonical="verify-cull",
        aliases=("verify",),
        script_name="verify_cull.py",
        help="Verify cull structure, pair counts, sheets, and temp artifacts.",
        default_cwd=True,
    ),
    Command(
        canonical="raw-analyze",
        aliases=(),
        script_name="raw_analyze.py",
        help="Write RAW histogram and clipping metrics for culling evidence.",
        default_cwd=True,
        options_with_values=("--output", "--ratings"),
    ),
    Command(
        canonical="lr-plan",
        aliases=(),
        script_name="lr_plan.py",
        help="Suggest Lightroom exposure sliders from RAW histogram evidence.",
        default_cwd=True,
        options_with_values=("--output", "--ratings", "--style"),
    ),
    Command(
        canonical="lr-apply",
        aliases=(),
        script_name="lr_apply.py",
        help="Write Lightroom rough-edit XMP fields from RAW evidence and style profiles.",
        default_cwd=True,
        options_with_values=("--ratings", "--style"),
    ),
    Command(
        canonical="rawpy-render",
        aliases=(),
        script_name="rawpy_render.py",
        help="Render RAW-derived JPEG inputs for selected candidates.",
        default_cwd=True,
        options_with_values=("--output-dir", "--ratings", "--quality"),
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


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def normalize_directory_input(raw_input: str) -> Path:
    return Path(raw_input.strip()).expanduser().resolve()


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
    output: TextIO = sys.stdout,
    interactive: bool | None = None,
) -> list[str] | None:
    script_args = list(args)
    help_requested = any(arg in ("-h", "--help") for arg in script_args)
    if command.default_cwd and not help_requested and not has_positional_argument(
        script_args, command.options_with_values
    ):
        if interactive if interactive is not None else is_interactive():
            directory = resolve_default_directory(
                input_func=input_func,
                cwd_func=cwd_func,
                output=output,
            )
            if directory is None:
                return None
            script_args.insert(0, str(directory))
        else:
            print(
                "mt: directory required when stdin is not interactive "
                "(pass a path argument).",
                file=sys.stderr,
            )
            return None
    return [command.script_name, *script_args]


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
            "  mt finalize --copy-to /Volumes/SDCARD/DCIM/100MSDCF --photos-album Sony --scene flower-field\n"
            "  mt organize --dry-run\n"
            "  mt fill-locations --describe\n"
            "  mt contact-sheet --export-only\n"
            "  mt lr-apply --style flower-rich"
        ),
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

    return run_script(command, namespace.args)


if __name__ == "__main__":
    raise SystemExit(main())
