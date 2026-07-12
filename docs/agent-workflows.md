# Agent Workflow Registry

## Core Agent Skills

Use these local Codex skills before falling back to ad hoc command selection:

| Skill | Trigger | Command path |
| --- | --- | --- |
| `apple-photos-location-fill` | Apple Photos missing geolocation audit/fill. | `mt fill-locations --force-refresh` or `mt fill-locations --scan-start "<timestamp>" --force-refresh`, review plan, then `mt fill-locations --apply-plan work/photos-location-fill/photos_location_fill_plan.json`. |
| `initial-cull` (`初筛`) | New photo directory organization, rating, contact sheets, and LR rough edits. | `mt organize`, `mt raw-analyze`, `mt lr-plan`, `mt lr-apply`, `mt contact-sheet`. |
| `extract-feature` (`成片归档`) | Post-Lightroom final pick archiving and optional Photos import. | `mt preflight-run finalize`, `mt finalize`, `mt hif-prune`. |
| `学习` (`学习调色`) | Preserve learned scene-specific Lightroom style from manual refinements. | `mt learn-style`, `mt styles`, repo profile/prompt updates. |

`apple-photos-location-fill` is not a photo-directory workflow. It operates on
Apple Photos and must keep planning separate from writes: generate
one compact HTML run-log table plus a machine-readable JSON plan first, then
apply only a reviewed JSON plan. Completed runs append timing, counts, examples,
warning rows, and apply status to `work/photos-location-fill/run_history.json`
and redraw `outputs/photos_location_fill_plan.html` with one row per run.

The source of truth for agent-facing workflow selection is
`media_toolkit/workflows.json`.

Use it before choosing commands for photo workflow requests:

- `initial-cull` / `初筛`: organize, group, rate, contact sheets, and Lightroom
  rough-edit XMP by default.
- `finalize` / `成片归档`: after manual Lightroom refinement, require both a
  source photo directory and an explicit destination outside that source; copy
  matching original HIF previews and optionally import Lightroom exports into
  Apple Photos, then run aggressive source-side HIF pruning for redundant
  HIF-only repeats.
- `learn-style` / `学习调色`: update repository knowledge from manual
  refinements; do not organize, archive, copy, or delete media.

Quick inspection:

```bash
mt commands
mt commands finalize
mt commands hif-prune
mt commands --json
mt self-check
mt self-check --json
mt workflows
mt workflows finalize
mt workflows --json
mt status <photo-dir>
mt batch-report <photo-dir>
mt doctor <photo-dir>
mt doctor <photo-dir> --workflow finalize --copy-to <destination-dir>
mt preflight-run finalize <photo-dir> --copy-to <destination-dir> --scene <scene>
mt hif-prune <photo-dir> --mode aggressive --scene <scene>
mt styles
mt styles <profile> --json
mt learn-style <photo-dir> --scene <scene> --json
```

`mt status --json` and `mt doctor --json` return a `status` field:

- `ready`
- `blocked`
- `needs-organize`
- `needs-lightroom-export`

The same JSON includes `recommendations`, which agents should treat as the
preferred next action list.

## Command Entry Points

New agent-facing command logic should live under `media_toolkit/commands/`.
The `mt` launcher calls command modules there directly. Files under `scripts/`
are thin compatibility wrappers for old entry points only.

Package command modules:

- `mt finalize`
- `mt hif-prune`
- `mt commands`
- `mt workflows`
- `mt self-check`
- `mt organize`
- `mt fill-locations`
- `mt contact-sheet`
- `mt status`
- `mt batch-report`
- `mt doctor`
- `mt preflight-run`
- `mt verify-cull`
- `mt manifest-template`
- `mt portrait-organize`
- `mt panorama-organize`
- `mt raw-analyze`
- `mt lr-plan`
- `mt lr-apply`
- `mt styles`
- `mt learn-style`
- `mt rawpy-render`
- `mt image-compress`
- `mt drone`
- `mt png-to-jpg`

When adding or changing behavior, prefer this order:

1. Put reusable logic under `media_toolkit/`.
2. Put command parsing and `main(argv)` under `media_toolkit/commands/`.
3. Keep any matching `scripts/*.py` file as a thin wrapper.
4. Update `media_toolkit/command_registry.py` if command metadata changes.
5. Update `media_toolkit/workflows.json` if the behavior changes a reusable
   agent workflow.
