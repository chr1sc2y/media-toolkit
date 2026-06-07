# Media Toolkit Agent Guide

This repository is becoming `media-toolkit`. The Git repository may still live
at `media-workflow` until the remote/local folder is renamed.

## Primary Interface

Use `mt` with clear long command names as the primary interface for humans and
agents. The old files in `scripts/` remain compatibility entry points, but new
instructions should prefer `mt`.

| Clear command | Purpose |
| --- | --- |
| `mt featured` | Copy matching files from image folders into `featured/` based on stems found in `raw/`. |
| `mt organize` | Move camera media into per-directory type folders such as `raw/` and `hif/`. |
| `mt fill-locations` | Plan or apply missing Apple Photos location fixes. |
| `mt contact-sheet` | Generate numbered contact sheets and a manifest. |
| `mt image-compress` | Compress oversized JPG/JPEG files under a maximum byte size. |
| `mt drone` | Compress drone videos with the existing preset. |
| `mt png-to-jpg` | Convert PNG images to JPG. |

Directory-based commands default to the current directory when no path is
provided. `mt fill-locations` operates on Apple Photos and does not use the
current directory as a media input.

Short aliases such as `mt f`, `mt o`, and `mt loc` exist only as compatibility
shortcuts. Do not use them in documentation or generated instructions unless the
user explicitly asks for aliases.

## Reusable Agent Workflows

Reusable prompts live under `prompts/`; workflow preset notes live under
`presets/`. Keep photos in their original travel/import directories instead of
copying them into this repository.

For Lightroom RAW culling and rough edits, use:

```text
prompts/lightroom-raw-cull-and-rough-edit.md
```

The user should only need to provide the target photo directory. Apply the
prompt to that external directory, write Lightroom/Camera Raw sidecars next to
the RAW files, and leave large media files outside this repository.

For photo culling runs, separate portraits by default. Move portrait RAW files
and their matching HIF/JPG previews under `人像/`, keeping the same `raw/` and
`hif/` split inside that directory. Cull and rough-edit both portrait and
non-portrait RAW files by writing sidecar XMP; use gentler portrait settings for
Texture, Clarity, and Dehaze. Keep temporary JPEG conversion caches out of the
final photo directory state. When contact sheets are useful, leave a single
low-resolution overview image named `_contact_sheet.jpg` in the photo directory,
with portrait and non-portrait sections separated.

## Development Rules

- Keep `media_toolkit/cli.py` as the command launcher.
- Keep `scripts/` as compatibility entry points unless a migration explicitly
  removes one.
- Add or update tests under `tests/` when command behavior changes.
- Run `python3 -m unittest discover -s tests` before claiming completion.
- Do not commit generated local runtime outputs such as `outputs/`, `work/`, or
  `*.egg-info/`.

## Install

From the repository root:

```bash
python3 -m pip install -e .
```

If `mt` installs into the Python user bin but the shell cannot find it, either
add that bin directory to `PATH` or link it into an existing PATH directory.
