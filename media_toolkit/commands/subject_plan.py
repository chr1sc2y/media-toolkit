from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from media_toolkit import rawpy_tools, subject_lift
from media_toolkit.commands import contact_sheet


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mt subject-plan",
        description="Build per-image HIF review artifacts for portrait subject lifts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("directory", help="Shoot directory to scan")
    parser.add_argument("--ratings", default=">=3", help="Eligible XMP rating expression")
    parser.add_argument("--output", default="subject_plan.tsv", help="TSV plan template")
    parser.add_argument(
        "--preview-dir",
        default=None,
        help="Directory for individual HIF-derived JPEG previews",
    )
    return parser.parse_args(argv)


def resolve_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root / path


def default_preview_dir(root: Path) -> Path:
    return Path(tempfile.gettempdir()) / f"media-toolkit-subject-review-{root.name}"


def convert_preview(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = contact_sheet.require_ffmpeg()
    try:
        contact_sheet.render_ffmpeg_input_image(ffmpeg, source, destination)
    except RuntimeError:
        contact_sheet.run_sips(source, destination)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    root = Path(args.directory).expanduser().resolve()
    if not root.is_dir():
        print(f"Error: directory not found: {root}", file=sys.stderr)
        return 1
    try:
        candidates = subject_lift.discover_candidates(root, args.ratings)
        output = resolve_path(root, args.output)
        preview_dir = (
            resolve_path(root, args.preview_dir)
            if args.preview_dir
            else default_preview_dir(root)
        )
        stats_by_path: dict[Path, object] = {}
        preview_names: dict[Path, str] = {}
        for candidate in candidates:
            group = candidate.raw_path.parent.parent.name
            preview_name = f"portrait-{group}-{candidate.raw_path.stem}.jpg"
            convert_preview(candidate.preview_path, preview_dir / preview_name)
            stats_by_path[candidate.raw_path.resolve()] = rawpy_tools.analyze_raw(
                candidate.raw_path
            )
            preview_names[candidate.raw_path.resolve()] = preview_name
        subject_lift.write_plan_template(
            output,
            root,
            candidates,
            stats_by_path,
            preview_names,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(f"Prepared {len(candidates)} portrait review candidate(s).")
    print(f"Plan template: {output}")
    print(f"Review previews: {preview_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
