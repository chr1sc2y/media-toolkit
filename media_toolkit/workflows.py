from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_workflow_registry() -> dict[str, Any]:
    text = resources.files("media_toolkit").joinpath("workflows.json").read_text(
        encoding="utf-8"
    )
    return json.loads(text)


def list_workflows() -> list[dict[str, Any]]:
    registry = load_workflow_registry()
    return list(registry["workflows"])


def get_workflow(workflow_id: str) -> dict[str, Any]:
    for workflow in list_workflows():
        if workflow["id"] == workflow_id:
            return workflow
    raise KeyError(f"unknown workflow: {workflow_id}")


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
