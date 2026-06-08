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
| `mt contact-sheet` | Generate contact sheets and a manifest. |
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

For photo culling runs, separate portraits by default. Use visual judgment to
group portraits by person in first-appearance order: `portrait/1/`,
`portrait/2/`, `portrait/3/`, etc. Detect panorama stitch sequences by looking
for consecutive frames with overlapping scenery, similar exposure settings, and
intentional panning; move each sequence into `panorama/1/`, `panorama/2/`,
`panorama/3/`, etc. Inside each portrait or panorama directory, keep the same
media split such as `raw/` for RAW plus XMP sidecars and `hif/` for matching
previews. Cull and rough-edit portrait, panorama, and ordinary RAW files by
writing lowercase `.xmp` sidecars; include Lightroom-readable sidecar markers
such as
`crs:HasSettings=True`, `crs:AlreadyApplied=False`,
`photoshop:SidecarForExtension=ARW`, `dc:format=image/x-sony-arw`, and
`xmpMM:PreservedFileName`. Do not blindly apply one fixed preset: tune exposure,
contrast, tone curve, color calibration, noise reduction, and lens-specific
sharpening from ISO, shutter, aperture, lens, RAW histogram evidence, and visual
review.
Do not apply automatic Upright/Level by default; inspect previews and use small
manual `PerspectiveRotate` corrections only when needed.
Use `Camera PT` for Sony portraits when available; use gentler portrait settings
for Texture, Clarity, and Dehaze. Use HIF previews as the visual source for
initial recognition, composition/focus review, and contact sheets. Do not use
HIF brightness or color as the source of truth for RAW exposure or color
grading, because HIF files already include Sony camera rendering. Prefer
`rawpy`/LibRaw linear RAW statistics for exposure histograms on final
candidates; use HIF only as a visual aid. Do not use Lightroom
`raw/Export/*.jpg` exports for portrait detection, panorama detection, culling
review, or final contact sheets. If a portrait RAW is moved, move its corresponding
`raw/Export/*.jpg` along with the RAW as an associated export only. Keep
temporary JPEG conversion caches out of the final photo directory state. When
contact sheets are useful, use `mt contact-sheet --hif-only` and keep portrait
and non-portrait overviews as separate files: the photo directory's
`_contact_sheet.jpg` must include non-portrait HIF previews from `hif/` only,
excluding `portrait/` and `panorama/`; if a portrait directory exists, write
`portrait/_contact_sheet.jpg` from `portrait/*/hif/` only, with each numbered
portrait group shown as a separate section. If a panorama directory exists,
write `panorama/_contact_sheet.jpg` from `panorama/*/hif/` only, with each
numbered panorama group shown as a separate section. Final contact sheets
should label tiles by filename only, without `001`/`002` index prefixes, and the
last sheet page should not be padded with black or blank placeholder tiles.

Final refinement candidates are photos rated `>=3` stars. Write base XMP
settings for every RAW, but treat 3/4/5-star files as the default pool for
manual final editing, export, and featured selection.

Editing consistency is mandatory for each batch. Final-candidate images from
the same scene/weather should share the same core edit skeleton: camera profile,
white balance baseline, highlight/shadow strategy, tone curve, Camera
Calibration range, HSL/Mixer caps, vignette policy, sharpening policy, lens
correction, and Upright policy. Per-image deviations are allowed only when the
subject or light genuinely differs, and the final report should call out those
intentional deviations.

Consistency means a unified final look, not identical slider values. Detect
exposure drift caused by different camera settings, metering, or subject
brightness by comparing RAW histogram/tonal evidence, preferably from
`rawpy`/LibRaw for Sony `.ARW` files, plus visual review. Adjust
`Exposure2012`, `Highlights2012`, `Shadows2012`, `Whites2012`, and `Blacks2012`
per image as needed so the batch lands at a shared brightness and contrast
baseline. Do not write one fixed exposure value across a batch unless the
images genuinely match.

Before assigning final-candidate ratings, group repeated compositions, burst
sequences, and same-location frames with only minor panning or zoom changes.
Usually keep one 4/5-star primary image per group, with at most one 3-star
alternate when it has clear backup value. Downgrade the rest to 2-star Skip even
when they are technically usable.

Legacy portrait paths such as `人像/1/` and `人像/_contact_sheet.jpg` are
obsolete. Use `portrait/` for all new work, even when the user writes in
Chinese.

Panorama stitching notes:

- This repository can identify and organize panorama source frames, but it does
  not currently provide a built-in high-quality panorama stitcher.
- For final output, prefer Lightroom Classic Photo Merge > Panorama so RAW
  source frames can produce a panorama DNG with Lightroom's projection,
  boundary warp, and fill controls.
- Hugin/Enblend can be used as an external CLI alternative when installed; do
  not claim panorama stitching is available until the relevant binaries are
  present.
- When reviewing candidate sequences, preserve leading zeroes in filenames.
  Avoid shell brace or sequence expansions that turn `08522` into `8522`; use
  `printf '%05d'` or explicit filenames.
- `mt contact-sheet` may not follow temporary symlinks to HIF files in ad hoc
  review folders. If candidate-only review sheets are needed, convert the HIF
  previews into temporary JPEG files first, then delete the temporary cache.

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
