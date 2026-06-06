# Media Toolkit Agent Guide

This repository is becoming `media-toolkit`. The Git repository may still live
at `media-workflow` until the remote/local folder is renamed.

## Primary Interface

Use `mt` as the primary interface for humans and agents. The old files in
`scripts/` remain compatibility entry points, but new instructions should prefer
`mt`.

| Frequent alias | Clear command | Purpose |
| --- | --- | --- |
| `mt f` | `mt featured` | Copy matching files from image folders into `featured/` based on stems found in `raw/`. |
| `mt o` | `mt organize` | Move camera media into per-directory type folders such as `raw/` and `hif/`. |
| `mt loc` | `mt fill-locations` | Plan or apply missing Apple Photos location fixes. |
| `mt sheet` | `mt contact-sheet` | Generate numbered contact sheets and a manifest. |
| `mt imgzip` | `mt image-compress` | Compress oversized JPG/JPEG files under a maximum byte size. |
| `mt drone` | `mt drone` | Compress drone videos with the existing preset. |
| `mt png` | `mt png-to-jpg` | Convert PNG images to JPG. |

Directory-based commands default to the current directory when no path is
provided. `mt loc` operates on Apple Photos and does not use the current
directory as a media input.

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
