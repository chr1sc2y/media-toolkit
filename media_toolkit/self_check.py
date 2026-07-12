from __future__ import annotations

import ast
import importlib
from importlib import resources
import json
from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import subprocess
from typing import Callable

from media_toolkit.command_registry import (
    command_registry_dict,
    list_commands,
    validate_command_registry,
)
from media_toolkit.style_profiles import (
    list_style_profiles,
    lr_plan_styles_by_xmp_style,
    lr_style_profiles,
)
from media_toolkit.workflows import load_workflow_registry, list_workflows


@dataclass(frozen=True)
class SelfCheckResult:
    name: str
    ok: bool
    message: str
    required: bool = True

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_self_checks(repo_root: Path | None = None) -> list[SelfCheckResult]:
    root = repo_root or Path(__file__).resolve().parents[1]
    checks: list[tuple[str, bool, Callable[[], str]]] = [
        ("command-registry", True, _check_command_registry),
        ("command-modules", True, _check_command_modules),
        ("script-wrappers", True, lambda: _check_script_wrappers(root / "scripts")),
        ("workflow-registry", True, _check_workflow_registry),
        ("style-registry", True, _check_style_registry),
        ("package-resources", True, _check_package_resources),
        ("raw-support", False, _check_raw_support),
        ("ffmpeg", False, _check_ffmpeg),
        ("heif-decoder", False, _check_heif_decoder),
        (
            "repository-skills",
            True,
            lambda: _check_repository_skills(root / "skills"),
        ),
    ]
    results: list[SelfCheckResult] = []
    for name, required, check in checks:
        try:
            message = check()
        except Exception as exc:
            results.append(
                SelfCheckResult(
                    name=name,
                    ok=False,
                    message=str(exc),
                    required=required,
                )
            )
        else:
            results.append(
                SelfCheckResult(
                    name=name,
                    ok=True,
                    message=message,
                    required=required,
                )
            )
    return results


def self_check_ok(results: list[SelfCheckResult]) -> bool:
    return all(result.ok for result in results if result.required)


def self_check_payload(results: list[SelfCheckResult]) -> dict[str, object]:
    return {
        "ok": self_check_ok(results),
        "checks": [result.to_dict() for result in results],
    }


def render_self_check(results: list[SelfCheckResult]) -> str:
    lines = ["Media Toolkit self-check:"]
    for result in results:
        if result.ok:
            status = "OK"
        elif result.required:
            status = "FAIL"
        else:
            status = "WARN"
        lines.append(f"- {status} {result.name}: {result.message}")
    lines.append(f"overall: {'OK' if self_check_ok(results) else 'FAIL'}")
    return "\n".join(lines)


def _check_command_registry() -> str:
    commands = list_commands(visible_only=True)
    validate_command_registry(commands)
    registry = command_registry_dict(visible_only=True)
    return f"{len(registry['commands'])} visible command(s)"


def _check_command_modules() -> str:
    failures: list[str] = []
    for command in list_commands(visible_only=True):
        if command.module_name is None:
            failures.append(f"{command.canonical}: missing module_name")
            continue
        try:
            importlib.import_module(command.module_name)
        except Exception as exc:
            failures.append(f"{command.canonical}: {exc}")
    if failures:
        raise ValueError("; ".join(failures))
    return "all visible command modules import"


def _check_script_wrappers(scripts_dir: Path) -> str:
    if not scripts_dir.is_dir():
        return "not present in installed distribution"
    missing: list[str] = []
    offenders: list[str] = []
    for command in list_commands(visible_only=True):
        script = scripts_dir / command.script_name
        if not script.exists():
            missing.append(command.script_name)
            continue
        tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
        definitions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        if definitions:
            offenders.append(f"{script.name}: {', '.join(definitions)}")
    problems = []
    if missing:
        problems.append(f"missing scripts: {', '.join(missing)}")
    if offenders:
        problems.append(f"non-thin scripts: {'; '.join(offenders)}")
    if problems:
        raise ValueError("; ".join(problems))
    return "all visible command scripts exist and are thin"


def _check_workflow_registry() -> str:
    registry = load_workflow_registry()
    workflows = list_workflows()
    return f"version={registry['version']}, workflows={len(workflows)}"


def _check_style_registry() -> str:
    profiles = list_style_profiles()
    xmp_profiles = lr_style_profiles()
    plan_styles = lr_plan_styles_by_xmp_style()
    profile_ids = {profile["id"] for profile in profiles}
    if profile_ids != set(xmp_profiles):
        raise ValueError("style profile ids differ from XMP profile ids")
    if profile_ids != set(plan_styles):
        raise ValueError("style profile ids differ from LR plan style ids")
    return f"profiles={len(profiles)}, xmp_profiles={len(xmp_profiles)}"


def _check_package_resources() -> str:
    package = resources.files("media_toolkit")
    required = {
        "workflows.json": "workflows",
        "style_profiles.json": "profiles",
    }
    details: list[str] = []
    for filename, collection in required.items():
        payload = json.loads(package.joinpath(filename).read_text(encoding="utf-8"))
        values = payload.get(collection)
        if not isinstance(values, list) or not values:
            raise ValueError(f"{filename} has no {collection}")
        details.append(f"{filename}={len(values)}")
    return ", ".join(details)


def _check_raw_support() -> str:
    module = importlib.import_module("rawpy")
    version = getattr(module, "__version__", "unknown")
    return f"rawpy {version}"


def _check_ffmpeg() -> str:
    executable = shutil.which("ffmpeg")
    if executable is None:
        raise RuntimeError("ffmpeg not found; video compression is unavailable")
    result = subprocess.run(
        [executable, "-hide_banner", "-filters"],
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise RuntimeError("ffmpeg exists but its filter list could not be read")
    if not any(
        line.split()[1:2] == ["drawtext"] for line in result.stdout.splitlines()
    ):
        raise RuntimeError(
            "ffmpeg has no drawtext filter; contact-sheet generation requires "
            "an ffmpeg build with libfreetype"
        )
    return f"{executable}; drawtext available"


def _check_heif_decoder() -> str:
    pillow_heif = importlib.import_module("pillow_heif")
    pillow_heif.register_heif_opener()
    image_module = importlib.import_module("PIL.Image")
    extensions = image_module.registered_extensions()
    supported = sorted(
        extension
        for extension in (".hif", ".heif", ".heic")
        if extension in extensions
    )
    if not supported:
        raise RuntimeError("pillow-heif loaded but registered no HEIF extensions")
    version = getattr(pillow_heif, "__version__", "unknown")
    return f"pillow-heif {version}; extensions={','.join(supported)}"


def _check_repository_skills(skills_dir: Path) -> str:
    if not skills_dir.is_dir():
        return "not present in installed distribution"
    manifest_path = skills_dir / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = payload.get("skills")
    if payload.get("version") != 1 or not isinstance(entries, list) or not entries:
        raise ValueError("invalid skills/manifest.json")
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("invalid skill manifest entry")
        name = entry.get("name")
        relative = entry.get("path")
        if not isinstance(name, str) or name in seen:
            raise ValueError(f"invalid or duplicate skill name: {name!r}")
        if relative != f"skills/{name}":
            raise ValueError(f"skill {name} has non-canonical path: {relative!r}")
        skill_file = skills_dir / name / "SKILL.md"
        if not skill_file.is_file():
            raise ValueError(f"missing {skill_file}")
        lines = skill_file.read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "---" or f"name: {name}" not in lines[:10]:
            raise ValueError(f"skill frontmatter name does not match folder: {name}")
        seen.add(name)
    return f"manifest version=1, skills={len(seen)}"
