from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "skills" / "manifest.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Register repository-owned Codex skills using symlinks."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify every link without creating or changing files.",
    )
    return parser.parse_args(argv)


def load_manifest() -> list[tuple[str, Path]]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if payload.get("version") != 1:
        raise ValueError("unsupported skills manifest version")
    entries = payload.get("skills")
    if not isinstance(entries, list) or not entries:
        raise ValueError("skills manifest is empty")

    skills_root = (REPO_ROOT / "skills").resolve()
    result: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid skills manifest entry")
        name = entry.get("name")
        relative_path = entry.get("path")
        if not isinstance(name, str) or not name or name in seen:
            raise ValueError(f"invalid or duplicate skill name: {name!r}")
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(f"skill {name} has no path")
        source = (REPO_ROOT / relative_path).resolve()
        try:
            source.relative_to(skills_root)
        except ValueError as exc:
            raise ValueError(f"skill {name} is outside repository skills/") from exc
        if source.name != name:
            raise ValueError(f"skill {name} path must end with its name")
        if not (source / "SKILL.md").is_file():
            raise ValueError(f"missing repository skill: {source / 'SKILL.md'}")
        seen.add(name)
        result.append((name, source))
    return result


def destination_root() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser() / "skills"
    return Path.home() / ".codex" / "skills"


def link_state(destination: Path, source: Path) -> str:
    if destination.is_symlink():
        if destination.resolve(strict=False) == source.resolve():
            return "current"
        return "wrong-link"
    if destination.exists():
        return "real-path"
    return "missing"


def preflight(
    entries: list[tuple[str, Path]], skills_root: Path
) -> tuple[list[str], list[tuple[str, Path, Path]]]:
    errors: list[str] = []
    missing: list[tuple[str, Path, Path]] = []
    for name, source in entries:
        destination = skills_root / name
        state = link_state(destination, source)
        if state == "real-path":
            errors.append(
                f"Refusing to replace {destination} because it is not a symlink."
            )
        elif state == "wrong-link":
            errors.append(
                f"Refusing to replace {destination} because it points somewhere else."
            )
        elif state == "missing":
            missing.append((name, source, destination))
    return errors, missing


def install_missing(entries: list[tuple[str, Path, Path]], skills_root: Path) -> None:
    skills_root.mkdir(parents=True, exist_ok=True)
    staged: list[tuple[Path, Path, Path]] = []
    installed: list[Path] = []
    try:
        for index, (_name, source, destination) in enumerate(entries):
            temporary = skills_root / f".{destination.name}.tmp-{os.getpid()}-{index}"
            temporary.symlink_to(source, target_is_directory=True)
            staged.append((temporary, destination, source))
        for temporary, destination, source in staged:
            os.replace(temporary, destination)
            installed.append(destination)
            print(f"Linked {destination} -> {source}")
    except Exception:
        for destination in installed:
            if destination.is_symlink():
                destination.unlink()
        for temporary, _destination, _source in staged:
            if temporary.is_symlink():
                temporary.unlink()
        raise


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        entries = load_manifest()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Skill manifest error: {exc}", file=sys.stderr)
        return 1

    skills_root = destination_root()
    errors, missing = preflight(entries, skills_root)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1

    if args.check:
        if missing:
            for name, _source, destination in missing:
                print(f"Skill link is missing: {name} ({destination})", file=sys.stderr)
            return 1
        print(f"All {len(entries)} Codex skill links are current.")
        return 0

    try:
        install_missing(missing, skills_root)
    except OSError as exc:
        print(f"Skill installation failed: {exc}", file=sys.stderr)
        return 1
    if not missing:
        print(f"All {len(entries)} Codex skill links are current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
