from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_style_profile_registry() -> dict[str, Any]:
    text = resources.files("media_toolkit").joinpath("style_profiles.json").read_text(
        encoding="utf-8"
    )
    return json.loads(text)


def list_style_profiles() -> list[dict[str, Any]]:
    return list(load_style_profile_registry()["profiles"])


def get_style_profile(profile_id: str) -> dict[str, Any]:
    for profile in list_style_profiles():
        if profile["id"] == profile_id:
            return profile
    raise KeyError(f"unknown style profile: {profile_id}")


def render_style_summary() -> str:
    lines = ["Scene style profiles:"]
    for profile in list_style_profiles():
        lines.append(
            f"- {profile['id']}: {profile['cn_name']} / {profile['name']} "
            f"(plan_style={profile['plan_style']})"
        )
    return "\n".join(lines)


def render_style_detail(profile: dict[str, Any]) -> str:
    lines = [
        f"{profile['id']}: {profile['cn_name']} / {profile['name']}",
        f"plan style: {profile['plan_style']}",
        f"summary: {profile['summary']}",
    ]
    if profile.get("use_when"):
        lines.append("use when:")
        lines.extend(f"- {item}" for item in profile["use_when"])
    if profile.get("avoid_when"):
        lines.append("avoid when:")
        lines.extend(f"- {item}" for item in profile["avoid_when"])
    return "\n".join(lines)
