from __future__ import annotations

import ast
import importlib
from dataclasses import asdict, dataclass
from pathlib import Path
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

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_self_checks(repo_root: Path | None = None) -> list[SelfCheckResult]:
    root = repo_root or Path(__file__).resolve().parents[1]
    checks: list[tuple[str, Callable[[], str]]] = [
        ("command-registry", _check_command_registry),
        ("command-modules", _check_command_modules),
        ("script-wrappers", lambda: _check_script_wrappers(root / "scripts")),
        ("workflow-registry", _check_workflow_registry),
        ("style-registry", _check_style_registry),
    ]
    results: list[SelfCheckResult] = []
    for name, check in checks:
        try:
            message = check()
        except Exception as exc:
            results.append(SelfCheckResult(name=name, ok=False, message=str(exc)))
        else:
            results.append(SelfCheckResult(name=name, ok=True, message=message))
    return results


def self_check_ok(results: list[SelfCheckResult]) -> bool:
    return all(result.ok for result in results)


def self_check_payload(results: list[SelfCheckResult]) -> dict[str, object]:
    return {
        "ok": self_check_ok(results),
        "checks": [result.to_dict() for result in results],
    }


def render_self_check(results: list[SelfCheckResult]) -> str:
    lines = ["Media Toolkit self-check:"]
    for result in results:
        status = "OK" if result.ok else "FAIL"
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
