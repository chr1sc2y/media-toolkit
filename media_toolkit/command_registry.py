from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Command:
    canonical: str
    aliases: tuple[str, ...]
    script_name: str
    help: str
    module_name: str | None = None
    default_cwd: bool = False
    options_with_values: tuple[str, ...] = ()
    visible: bool = True
    side_effects: tuple[str, ...] = ()
    supports_dry_run: bool = False
    requires_destination: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["aliases"] = list(self.aliases)
        data["options_with_values"] = list(self.options_with_values)
        data["side_effects"] = list(self.side_effects)
        return data


COMMANDS = (
    Command(
        canonical="finalize",
        aliases=(),
        script_name="finalize.py",
        help="Copy matching original HIF previews to an explicit destination and optionally import exports into Photos.",
        module_name="media_toolkit.commands.finalize",
        default_cwd=True,
        options_with_values=("--copy-to", "--scene", "--photos-album"),
        side_effects=("copy", "photos-import"),
        supports_dry_run=True,
        requires_destination=True,
    ),
    Command(
        canonical="hif-prune",
        aliases=(),
        script_name="hif_prune.py",
        help="Plan redundant source-side HIF cleanup; delete only with explicit confirmation.",
        module_name="media_toolkit.commands.hif_prune",
        default_cwd=True,
        options_with_values=("--mode", "--scene", "--manifest", "--apply-plan"),
        side_effects=("delete", "write-manifest"),
        supports_dry_run=True,
    ),
    Command(
        canonical="organize",
        aliases=("o", "org"),
        script_name="organize.py",
        help="Move camera media into per-directory type folders.",
        module_name="media_toolkit.commands.organize",
        default_cwd=True,
        options_with_values=("--type",),
        side_effects=("move",),
        supports_dry_run=True,
    ),
    Command(
        canonical="fill-locations",
        aliases=("loc", "locations", "fill-location"),
        script_name="fill_missing_photo_locations.py",
        help="Plan or apply Apple Photos missing-location fixes.",
        module_name="media_toolkit.commands.fill_locations",
        options_with_values=(
            "--apply-plan",
            "--scan-start",
            "--scan-lookback-hours",
            "--start",
            "--end",
            "--work-dir",
            "--output-dir",
            "--suffix",
        ),
        side_effects=("photos-read", "write-plan", "optional-photos-update"),
        supports_dry_run=True,
    ),
    Command(
        canonical="contact-sheet",
        aliases=("sheet", "sheets"),
        script_name="generate_contact_sheets.py",
        help="Generate contact sheet thumbnails and a manifest.",
        module_name="media_toolkit.commands.contact_sheet",
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
        side_effects=("write-contact-sheet", "write-manifest"),
    ),
    Command(
        canonical="portrait-organize",
        aliases=("portraits",),
        script_name="portrait_organize.py",
        help="Move portrait RAW/HIF pairs from a manifest and rebuild sheets.",
        module_name="media_toolkit.commands.portrait_organize",
        default_cwd=True,
        options_with_values=("--manifest",),
        side_effects=("move", "write-contact-sheet"),
        supports_dry_run=True,
    ),
    Command(
        canonical="panorama-organize",
        aliases=("panoramas",),
        script_name="panorama_organize.py",
        help="Move panorama RAW/HIF pairs from a manifest and rebuild sheets.",
        module_name="media_toolkit.commands.panorama_organize",
        default_cwd=True,
        options_with_values=("--manifest",),
        side_effects=("move", "write-contact-sheet"),
        supports_dry_run=True,
    ),
    Command(
        canonical="manifest-template",
        aliases=("manifest",),
        script_name="manifest_template.py",
        help="Create portrait or panorama manifest templates from root pairs.",
        module_name="media_toolkit.commands.manifest_template",
        default_cwd=True,
        options_with_values=("--kind", "--output"),
        side_effects=("write",),
    ),
    Command(
        canonical="verify-cull",
        aliases=("verify",),
        script_name="verify_cull.py",
        help="Verify cull structure, XMP ratings/markers, pairs, sheets, and temp artifacts.",
        module_name="media_toolkit.commands.verify_cull",
        default_cwd=True,
    ),
    Command(
        canonical="doctor",
        aliases=("workflow-check", "check"),
        script_name="doctor.py",
        help="Inspect a photo directory before running an agent workflow.",
        module_name="media_toolkit.commands.doctor",
        default_cwd=True,
        options_with_values=("--workflow", "--copy-to"),
    ),
    Command(
        canonical="status",
        aliases=("st",),
        script_name="status.py",
        help="Summarize photo directory workflow status.",
        module_name="media_toolkit.commands.status",
        default_cwd=True,
        options_with_values=("--workflow", "--copy-to"),
    ),
    Command(
        canonical="preflight-run",
        aliases=("preflight",),
        script_name="preflight_run.py",
        help="Run a read-only workflow preflight sequence.",
        module_name="media_toolkit.commands.preflight_run",
        options_with_values=("--copy-to", "--scene", "--photos-album"),
    ),
    Command(
        canonical="batch-report",
        aliases=("report",),
        script_name="batch_report.py",
        help="Print a read-only human summary of a photo batch.",
        module_name="media_toolkit.commands.batch_report",
        default_cwd=True,
        options_with_values=("--copy-to",),
    ),
    Command(
        canonical="raw-analyze",
        aliases=(),
        script_name="raw_analyze.py",
        help="Write RAW histogram and clipping metrics for culling evidence.",
        module_name="media_toolkit.commands.raw_analyze",
        default_cwd=True,
        options_with_values=("--output", "--ratings"),
        side_effects=("write-analysis",),
    ),
    Command(
        canonical="ratings-apply",
        aliases=(),
        script_name="ratings_apply.py",
        help="Apply reviewed path/rating TSV assignments to RAW XMP sidecars.",
        module_name="media_toolkit.commands.ratings_apply",
        default_cwd=True,
        options_with_values=("--manifest",),
        side_effects=("write-xmp-rating",),
        supports_dry_run=True,
    ),
    Command(
        canonical="lr-plan",
        aliases=(),
        script_name="lr_plan.py",
        help="Suggest Lightroom exposure sliders from RAW histogram evidence.",
        module_name="media_toolkit.commands.lr_plan",
        default_cwd=True,
        options_with_values=("--output", "--ratings", "--style"),
        side_effects=("write-plan",),
    ),
    Command(
        canonical="lr-apply",
        aliases=(),
        script_name="lr_apply.py",
        help="Apply reviewed LR plan values or derive rough-edit XMP from RAW histograms.",
        module_name="media_toolkit.commands.lr_apply",
        default_cwd=True,
        options_with_values=("--ratings", "--style", "--plan"),
        side_effects=("write-xmp",),
        supports_dry_run=True,
    ),
    Command(
        canonical="styles",
        aliases=("style-profiles",),
        script_name="styles.py",
        help="Show agent-readable Lightroom scene style profiles.",
        module_name="media_toolkit.commands.styles",
    ),
    Command(
        canonical="learn-style",
        aliases=("learn",),
        script_name="learn_style.py",
        help="Read Lightroom final-pick XMP files and summarize scene style evidence.",
        module_name="media_toolkit.commands.learn_style",
        default_cwd=True,
        options_with_values=("--scene", "--baseline"),
    ),
    Command(
        canonical="rawpy-render",
        aliases=(),
        script_name="rawpy_render.py",
        help="Render RAW-derived JPEG inputs for selected candidates.",
        module_name="media_toolkit.commands.rawpy_render",
        default_cwd=True,
        options_with_values=("--output-dir", "--ratings", "--quality"),
        side_effects=("write-render-cache",),
    ),
    Command(
        canonical="image-compress",
        aliases=("imgzip", "compress-images"),
        script_name="compress_images_under_size.py",
        help="Compress oversized JPG/JPEG files under a byte cap.",
        module_name="media_toolkit.commands.image_compress",
        default_cwd=True,
        options_with_values=("--max-bytes",),
        side_effects=("write-compressed-image",),
        supports_dry_run=True,
    ),
    Command(
        canonical="drone",
        aliases=("drone-compress",),
        script_name="compress_drone_video.py",
        help="Compress drone videos with the existing preset script.",
        module_name="media_toolkit.commands.drone",
        default_cwd=True,
        side_effects=("write-compressed-video",),
    ),
    Command(
        canonical="png-to-jpg",
        aliases=("pngjpg", "png"),
        script_name="png_to_jpg.py",
        help="Convert PNG images to JPG with the existing preset script.",
        module_name="media_toolkit.commands.png_to_jpg",
        default_cwd=True,
        side_effects=("write-converted-image",),
    ),
    Command(
        canonical="commands",
        aliases=(),
        script_name="commands.py",
        help="Show the agent-readable command registry.",
        module_name="media_toolkit.commands.commands",
    ),
    Command(
        canonical="workflows",
        aliases=(),
        script_name="workflows.py",
        help="Show the agent-readable workflow registry.",
        module_name="media_toolkit.commands.workflows",
    ),
    Command(
        canonical="self-check",
        aliases=("doctor-repo",),
        script_name="self_check.py",
        help="Run read-only registry and entrypoint health checks.",
        module_name="media_toolkit.commands.self_check",
    ),
)


def validate_command_registry(commands: Iterable[Command] = COMMANDS) -> None:
    seen: dict[str, str] = {}
    for command in commands:
        if not command.canonical:
            raise ValueError("command is missing canonical name")
        if command.visible:
            for field, value in (
                ("script_name", command.script_name),
                ("help", command.help),
                ("module_name", command.module_name),
            ):
                if not value:
                    raise ValueError(f"command {command.canonical} is missing {field}")
        for option in command.options_with_values:
            if not option.startswith("--"):
                raise ValueError(
                    f"command {command.canonical} has non-long option {option}"
                )
        for name in (command.canonical, *command.aliases):
            previous = seen.get(name)
            if previous is not None:
                raise ValueError(
                    f"command name or alias {name} is used by both "
                    f"{previous} and {command.canonical}"
                )
            seen[name] = command.canonical


def _build_aliases(commands: Iterable[Command]) -> dict[str, Command]:
    validate_command_registry(commands)
    return {
        alias: command
        for command in commands
        for alias in (command.canonical, *command.aliases)
    }


ALIASES = _build_aliases(COMMANDS)


def resolve_command(name: str) -> Command:
    try:
        return ALIASES[name]
    except KeyError as exc:
        raise ValueError(f"unknown command: {name}") from exc


def list_commands(*, visible_only: bool = False) -> list[Command]:
    if visible_only:
        return [command for command in COMMANDS if command.visible]
    return list(COMMANDS)


def command_registry_dict(*, visible_only: bool = False) -> dict[str, Any]:
    return {
        "version": 1,
        "commands": [
            command.to_dict() for command in list_commands(visible_only=visible_only)
        ],
    }
