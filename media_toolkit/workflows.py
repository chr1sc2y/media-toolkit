from __future__ import annotations

import json
import re
from importlib import resources
from typing import Any

from media_toolkit.command_registry import resolve_command


REQUIRED_WORKFLOW_FIELDS = (
    "id",
    "name",
    "cn_name",
    "primary_command",
    "source_path_required",
    "destination_path_required",
    "default_behavior",
)

LIST_WORKFLOW_FIELDS = ("preflight", "must_not", "agent_notes")
MT_COMMAND_RE = re.compile(r"\bmt\s+([a-z][a-z0-9-]*)\b")


def load_workflow_registry() -> dict[str, Any]:
    text = resources.files("media_toolkit").joinpath("workflows.json").read_text(
        encoding="utf-8"
    )
    registry = json.loads(text)
    _validate_registry(registry)
    return registry


def _validate_registry(registry: dict[str, Any]) -> None:
    workflow_ids: set[str] = set()
    for workflow in registry.get("workflows", []):
        workflow_id = workflow.get("id")
        if not workflow_id:
            raise ValueError("workflow is missing id")
        if workflow_id in workflow_ids:
            raise ValueError(f"duplicate workflow id: {workflow_id}")
        workflow_ids.add(workflow_id)
        for field in REQUIRED_WORKFLOW_FIELDS:
            if field not in workflow:
                raise ValueError(f"workflow {workflow_id} is missing {field}")
        for field in ("source_path_required", "destination_path_required"):
            if not isinstance(workflow[field], bool):
                raise ValueError(f"workflow {workflow_id} has non-boolean {field}")
        for field in LIST_WORKFLOW_FIELDS:
            if field in workflow and not _is_string_list(workflow[field]):
                raise ValueError(f"workflow {workflow_id} has invalid {field}")
        _validate_referenced_commands(workflow_id, workflow)


def _is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _validate_referenced_commands(workflow_id: str, workflow: dict[str, Any]) -> None:
    for command_name in _iter_referenced_mt_commands(workflow):
        try:
            resolve_command(command_name)
        except ValueError as exc:
            raise ValueError(
                f"workflow {workflow_id} references unknown mt command: {command_name}"
            ) from exc


def _iter_referenced_mt_commands(workflow: dict[str, Any]) -> set[str]:
    commands: set[str] = set()
    for value in workflow.values():
        if isinstance(value, str):
            commands.update(MT_COMMAND_RE.findall(value))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    commands.update(MT_COMMAND_RE.findall(item))
    return commands


def list_workflows() -> list[dict[str, Any]]:
    registry = load_workflow_registry()
    return list(registry["workflows"])


def get_workflow(workflow_id: str) -> dict[str, Any]:
    for workflow in list_workflows():
        if workflow["id"] == workflow_id:
            return workflow
    raise KeyError(f"unknown workflow: {workflow_id}")


def workflow_ids() -> tuple[str, ...]:
    return tuple(workflow["id"] for workflow in list_workflows())


def workflow_choices(*, include_auto: bool = False) -> tuple[str, ...]:
    choices = tuple(
        workflow["id"]
        for workflow in list_workflows()
        if workflow["source_path_required"]
    )
    if include_auto:
        return ("auto", *choices)
    return choices


def render_workflow_summary() -> str:
    lines = ["Agent workflows:"]
    for workflow in list_workflows():
        lines.append(
            f"- {workflow['id']}: {workflow['cn_name']} / {workflow['name']}"
        )
        lines.append(f"  command: {workflow['primary_command']}")
        if workflow.get("destination_path_required"):
            lines.append("  requires: source path + explicit destination path")
        elif workflow.get("source_path_required"):
            lines.append("  requires: source path")
    return "\n".join(lines)


def render_workflow_detail(workflow: dict[str, Any]) -> str:
    lines = [
        f"{workflow['id']}: {workflow['cn_name']} / {workflow['name']}",
        f"command: {workflow['primary_command']}",
    ]
    if "hif_only_command" in workflow:
        lines.append(f"hif-only: {workflow['hif_only_command']}")
    if "apply_command" in workflow:
        lines.append(f"apply: {workflow['apply_command']}")
    if "inspection_command" in workflow:
        lines.append(f"inspect: {workflow['inspection_command']}")
    lines.append(f"default: {workflow['default_behavior']}")
    if workflow.get("preflight"):
        lines.append("preflight:")
        lines.extend(f"- {item}" for item in workflow["preflight"])
    if workflow.get("must_not"):
        lines.append("must not:")
        lines.extend(f"- {item}" for item in workflow["must_not"])
    if workflow.get("agent_notes"):
        lines.append("agent notes:")
        lines.extend(f"- {item}" for item in workflow["agent_notes"])
    return "\n".join(lines)
