# HIF Prune Finalize Design

> **Superseded (2026-07-12):** This is a historical design record. The current
> safety contract is
> `docs/superpowers/specs/2026-07-12-media-toolkit-hardening-design.md`.
> Automatic or default deletion described below was rejected. Current cleanup
> is plan → human review → explicit application of that exact reviewed plan.

## Goal

Extend the finalized archive workflow with a dedicated, separately requested
HIF cleanup step. Finalization itself never runs cleanup automatically.

## Behavior

`mt finalize` keeps its existing boundary: it copies matching original HIF previews to an explicit external destination and imports Lightroom exports into Apple Photos unless disabled. It must not delete source or destination media.

`mt hif-prune` inspects source-side HIF files after finalization. Its default
mode is `plan`, which writes a JSON manifest and a TSV review companion without
deleting. Permanent cleanup applies only the exact reviewed JSON plan and
requires an explicit confirmation flag.

## Hard Keep Rules

`mt hif-prune` never deletes:

- HIF files whose stem appears in Lightroom exports under `raw/Export`, `raw/Export/Pixcake`, `portrait/<n>/raw/Export`, or `portrait/<n>/raw/Export/Pixcake`.
- HIF files that still have a same-stem RAW file in the sibling `raw/` directory.
- HIF files under `panorama/<n>/hif/`.
- Files outside the source photo directory.
- Files in the explicit archive destination.

## Delete Candidate Rules

The command may delete HIF-only files when they are high-confidence clutter:

- visually near-identical repeats in a filename/time-neighbor group, keeping one representative;
- obvious unreadable or unsupported files only as manifest warnings, not deletion targets.

Portrait HIFs are treated conservatively by using a stricter visual-similarity threshold.

## CLI Shape

```bash
mt hif-prune <photo-dir>
mt hif-prune <photo-dir> --dry-run
mt hif-prune <photo-dir> --mode plan
mt hif-prune <photo-dir> --mode aggressive \
  --apply-plan <reviewed.json> --confirm-delete
```

`plan` is the default. `aggressive` is rejected unless it receives a reviewed
plan through `--apply-plan` together with `--confirm-delete`.

## Workflow Integration

The workflow registry and agent instructions should say that finalized archive runs:

1. `mt preflight-run finalize <photo-dir> --copy-to <destination-dir> --scene <scene>`
2. `mt finalize <photo-dir> --copy-to <destination-dir> --scene <scene>`
3. If cleanup was separately requested, run
   `mt hif-prune <photo-dir> --mode plan --scene <scene>`, review the JSON, then
   apply that file with `--mode aggressive --apply-plan <reviewed.json>
   --confirm-delete --scene <scene>`.
