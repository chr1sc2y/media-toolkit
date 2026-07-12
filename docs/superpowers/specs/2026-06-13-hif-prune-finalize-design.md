# HIF Prune Finalize Design

## Goal

Extend the finalized archive workflow with a dedicated HIF cleanup step. The cleanup is a separate `mt hif-prune` command, but the agent-facing finalize workflow runs it automatically after `mt finalize`.

## Behavior

`mt finalize` keeps its existing boundary: it copies matching original HIF previews to an explicit external destination and imports Lightroom exports into Apple Photos unless disabled. It must not delete source or destination media.

`mt hif-prune` inspects source-side HIF files after finalization. Its default mode is `aggressive`, which permanently deletes only high-confidence cleanup candidates. It writes a JSON manifest and a TSV review manifest before deleting so every decision remains auditable.

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
mt hif-prune <photo-dir> --mode aggressive
mt hif-prune <photo-dir> --mode plan
```

`aggressive` is the default and deletes selected duplicate HIFs. `plan` and `--dry-run` only write manifests and report the plan.

## Workflow Integration

The workflow registry and agent instructions should say that finalized archive runs:

1. `mt preflight-run finalize <photo-dir> --copy-to <destination-dir> --scene <scene>`
2. `mt finalize <photo-dir> --copy-to <destination-dir> --scene <scene>`
3. `mt hif-prune <photo-dir> --mode aggressive --scene <scene>`

