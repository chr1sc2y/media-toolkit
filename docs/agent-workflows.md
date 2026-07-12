# Agent Workflow Map

This page is an index, not a second source of workflow rules. Read
`media_toolkit/workflows.json` for machine behavior and the matching repository
skill for operator procedure.

| Intent | Skill | Read-only gate | Mutating command |
| --- | --- | --- | --- |
| 初筛 / rate a new shoot | `initial-cull` | `mt organize <photo-dir> --dry-run --verbose`; `mt ratings-apply <photo-dir> --manifest ratings.tsv --dry-run` | `mt organize`; `mt ratings-apply`; optional scene-compatible `mt lr-apply --plan lr_plan_reviewed.tsv` |
| 成片归档 | `extract-feature` | `mt preflight-run finalize <photo-dir> --copy-to <destination-dir> --scene <scene>` | `mt finalize <photo-dir> --copy-to <destination-dir>` |
| Optional HIF cleanup | `extract-feature` | `mt hif-prune <photo-dir> --mode plan` | Separate confirmation: `--mode aggressive --apply-plan <reviewed.json> --confirm-delete` |
| 学习调色 | `learn-color-style` | `mt learn-style <photo-dir> --scene <scene> --json` | None unless the user separately asks to update repository profiles |
| Photos 补地点 | `apple-photos-location-fill` | `mt fill-locations --force-refresh` | After plan approval: `mt fill-locations --apply-plan <reviewed.json>` |

## Boundaries at handoff

- Initial cull ends with strict `mt verify-cull`, rating counts, contact-sheet
  paths, and the Lightroom `Metadata > Read Metadata from Files` reminder.
- Final archive reports copied, byte-identical skipped, missing/conflicting, and
  Photos submission status. Photos does not expose reliable duplicate-skip or
  final imported counts through the current AppleScript path.
- HIF deletion is never a default post-finalize step.
- Style learning reports valid sample paths, repeated values, numeric summaries,
  observed-field baseline deviations, and uncertainty; it does not infer
  omitted fields or create photo-folder reports.
- Location fill reports plan warnings and neighbor time deltas before any write.

## Source hierarchy

```text
command_registry.py  command metadata and side effects
workflows.json       workflow order and hard safety rules
skills/*/SKILL.md    trigger language and exact operator procedure
prompts/ + presets/  detailed visual and Lightroom guidance
```

When behavior changes, update the owning layer and its tests first. Keep this
index short so it cannot drift into a competing specification.
