from __future__ import annotations

import json
from importlib import resources
from typing import Any


def load_style_profile_registry() -> dict[str, Any]:
    text = resources.files("media_toolkit").joinpath("style_profiles.json").read_text(
        encoding="utf-8"
    )
    registry = json.loads(text)
    _validate_registry(registry)
    return registry


def _validate_registry(registry: dict[str, Any]) -> None:
    profile_ids: set[str] = set()
    for profile in registry.get("profiles", []):
        profile_id = profile.get("id")
        if not profile_id:
            raise ValueError("style profile is missing id")
        if profile_id in profile_ids:
            raise ValueError(f"duplicate style profile id: {profile_id}")
        profile_ids.add(profile_id)
        if not profile.get("plan_style"):
            raise ValueError(f"style profile {profile_id} is missing plan_style")
        xmp_fields = profile.get("xmp_fields")
        if not isinstance(xmp_fields, dict) or not xmp_fields:
            raise ValueError(f"style profile {profile_id} is missing xmp_fields")
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in xmp_fields.items()
        ):
            raise ValueError(f"style profile {profile_id} has non-string XMP fields")


def list_style_profiles() -> list[dict[str, Any]]:
    return list(load_style_profile_registry()["profiles"])


def get_style_profile(profile_id: str) -> dict[str, Any]:
    for profile in list_style_profiles():
        if profile["id"] == profile_id:
            return profile
    raise KeyError(f"unknown style profile: {profile_id}")


def style_profile_ids() -> tuple[str, ...]:
    return tuple(profile["id"] for profile in list_style_profiles())


def lr_style_profiles() -> dict[str, dict[str, str]]:
    return {
        profile["id"]: dict(profile["xmp_fields"]) for profile in list_style_profiles()
    }


def lr_plan_styles_by_xmp_style() -> dict[str, str]:
    return {
        profile["id"]: profile["plan_style"] for profile in list_style_profiles()
    }


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
        f"xmp fields: {len(profile['xmp_fields'])}",
        f"summary: {profile['summary']}",
    ]
    if profile.get("use_when"):
        lines.append("use when:")
        lines.extend(f"- {item}" for item in profile["use_when"])
    if profile.get("avoid_when"):
        lines.append("avoid when:")
        lines.extend(f"- {item}" for item in profile["avoid_when"])
    return "\n".join(lines)
