# Media Toolkit Agent Guide

`media-toolkit` is a personal, repository-owned CLI for photo/video workflows.
Media libraries and personal records stay outside this repository.

## Source of truth

Use the narrowest source that owns the decision:

1. `media_toolkit/command_registry.py` — command names, modules, side effects,
   destination requirements, and dry-run support.
2. `media_toolkit/workflows.json` — machine-readable workflow order and hard
   safety boundaries.
3. `skills/*/SKILL.md` — agent triggers, exact operator procedure, and handoff.
4. `prompts/` and `presets/` — detailed visual criteria and Lightroom direction.
5. README prose — orientation only; it must not override the registries.

Do not copy long workflow rules into several files. Change the owning registry
or skill, update its focused tests, then adjust short references elsewhere.

## Repository-owned skills

| Skill | Use for | Hard boundary |
| --- | --- | --- |
| `initial-cull` | Organize a new shoot, group, rate, create sheets, and optionally apply a reviewed LR plan. | No final archive, Photos import, or deletion. |
| `extract-feature` | Preflight and archive manually refined final picks. | Explicit external destination; no implicit source cleanup. |
| `learn-color-style` | Read final Export/XMP evidence and compare a scene style. | Read-only; no media processing or universal style inference. |
| `apple-photos-location-fill` | Plan missing Photos locations and apply an approved JSON plan. | Planning and writeback are separate user-confirmed stages. |

Canonical skill files live under `skills/`. Register them with:

```bash
sh scripts/install-codex-skills.sh
sh scripts/install-codex-skills.sh --check
```

The installer preflights all four destinations and never replaces a real
directory or unrelated symlink.

## Core safety invariants

- Keep Vault, Ledger, trip-spending, and other personal source data out of this
  repository even though the GitHub repository is private.
- Keep photo/video binaries in the user's source directories, not in Git.
- Never infer an archive destination. `mt finalize` requires an explicit path
  outside the complete user-supplied source root.
- Never overwrite a different same-named archive file. Missing HIF matches and
  content conflicts are failures.
- Panorama source-frame HIF files are not archive candidates; final panorama
  exports may still be imported into Photos.
- XMP updates are field-scoped and atomic per sidecar. Preserve crop,
  perspective, masks, labels, comments, and unknown metadata.
- New culls use `mt ratings-apply` and strict `mt verify-cull`; do not use
  `--legacy-structure-only` for fresh work.
- `mt hif-prune` defaults to a plan. Permanent deletion requires the separate,
  explicit combination `--mode aggressive`, `--apply-plan <reviewed.json>`, and
  `--confirm-delete`, plus a working HEIF decoder. It must apply the reviewed
  file, not rebuild the plan.
- `mt fill-locations --apply-plan` may write only the already-reviewed JSON plan;
  it must not rescan or rebuild location choices.

## Primary interface

Prefer clear `mt` names over aliases and compatibility scripts:

```bash
mt commands
mt commands finalize
mt workflows
mt workflows initial-cull
mt self-check --json

mt status <photo-dir> --json
mt doctor <photo-dir>
mt organize <photo-dir> --dry-run --verbose
mt ratings-apply <photo-dir> --manifest ratings.tsv --dry-run
mt lr-plan <photo-dir> --ratings ">=3" --output lr_plan.tsv
mt lr-apply <photo-dir> --ratings ">=3" --plan lr_plan_reviewed.tsv --dry-run
mt verify-cull <photo-dir>

mt preflight-run finalize <photo-dir> --copy-to <destination-dir> --scene <scene>
mt finalize <photo-dir> --copy-to <destination-dir> --scene <scene>
mt hif-prune <photo-dir> --mode plan --scene <scene>

mt styles
mt learn-style <photo-dir> --scene <scene> --baseline travel-rich --json

mt fill-locations --force-refresh
mt fill-locations --apply-plan work/photos-location-fill/photos_location_fill_plan.json
```

Directory commands may default to the current directory for interactive use,
but agent instructions must always pass the target path explicitly.

## Implementation rules

- Put behavior in `media_toolkit/` and command parsing in
  `media_toolkit/commands/`.
- Keep Python files in `scripts/` as thin compatibility wrappers only.
- Keep Python 3.9 compatibility; use `from __future__ import annotations` before
  PEP 604 annotations.
- Use `pathlib`, argument lists for subprocesses, and explicit encodings.
- Preserve timestamps/metadata for archives with `shutil.copy2`.
- Treat destructive commands and metadata writes as test-first changes.
- Package runtime JSON through `importlib.resources`; never assume a source
  checkout at runtime.
- The top-level `src/` package is a tested compatibility shim. New behavior does
  not belong there.

## Verification

Run focused tests while changing behavior, then before commit:

```bash
python -m unittest discover -s tests
mt self-check --json
sh scripts/install-codex-skills.sh --check
git diff --check
```

Also build and smoke-test an isolated wheel when packaging or resources change.
CI repeats the full suite on the supported Python floor and a current Python.
