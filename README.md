# media-toolkit

Personal media command-line toolkit for photo and video workflows.

## Quick Start

Install once from the repository root:

```bash
python3 -m pip install -e .
```

After that, run `mt` from any directory:

```bash
mt
mt featured /path/to/photos
mt featured
mt organize /path/to/import --dry-run
mt organize
mt fill-locations --describe
mt contact-sheet /path/to/photos --export-only
mt raw-analyze /path/to/photos --ratings ">=3"
mt rawpy-render /path/to/photos --ratings ">=3"
mt image-compress /path/to/photos --max-bytes 1048576
```

When a directory-based command is run without a path, `mt` uses the current
directory.

## Agent Workflows

Reusable agent prompts live under `prompts/`. Keep photo folders in their
original travel/import locations; do not copy large photo directories into this
repository.

For photo initial culling and downstream edit branches:

```bash
prompts/lightroom-raw-cull-and-rough-edit.md
```

Ask the agent to use that prompt with a photo directory:

```text
使用 prompts/lightroom-raw-cull-and-rough-edit.md
对 /path/to/photo-directory 执行 RAW 初筛、评级和后续 LR/AI 分支流程。
```

Workflow preset notes live under `presets/`, including the Sony ST travel base
starting point for Lightroom / Camera Raw XMP sidecars.

During agent-led culling, portraits are separated by default. If one person is
present, use `portrait/1/raw/` and `portrait/1/hif/`. If multiple people are
present, use visual judgment to group them by person in first-appearance order:
`portrait/1/`, `portrait/2/`, `portrait/3/`, etc. Each person directory keeps
its own `raw/` and `hif/` split. Initial cull rates every RAW file but does not
write XMP label fields or Lightroom rough-edit parameters.

Panorama stitch sequences are separated by default. Detect them from
consecutive frames with overlapping scenery, similar exposure settings, and
intentional panning. Use `panorama/1/raw/` and `panorama/1/hif/` for the first
sequence, `panorama/2/` for the second, and continue by first-appearance order.
Keep all source frames for a panorama sequence together so Lightroom or other
stitch tools can merge them later. Sidecars are always lowercase `.xmp` and
include Lightroom-readable
markers such as `crs:HasSettings=True`, `crs:AlreadyApplied=False`,
`photoshop:SidecarForExtension=ARW`, `dc:format=image/x-sony-arw`, and
`xmpMM:PreservedFileName`. The LR branch writes rough edits later, customized
from ISO, shutter, aperture, lens, RAW histogram evidence, and visual review;
do not blindly apply one fixed preset. Automatic Upright/Level is off by
default; use small manual `PerspectiveRotate` corrections only when a reviewed
preview needs it. Sony portraits prefer `Camera PT` when available, while
non-portraits prefer `Camera ST` or a natural Standard/ST fallback. Temporary
JPEG caches such as `review_jpg/` should be deleted before the run is reported
complete. Use HIF
previews as the visual source for culling decisions, composition/focus review,
and contact sheets, but not as the source of truth for RAW exposure or color
grading because they already include Sony camera rendering. Prefer
`rawpy`/LibRaw linear RAW statistics for final-candidate exposure histograms,
using HIF only as a visual aid. Do not use Lightroom `raw/Export/*.jpg` exports
for portrait detection, panorama detection, culling review, or final contact
sheets; when a portrait RAW moves, move the matching export JPG as an associated
file only. HIF-only files are normal backup files after rejected RAWs have been
deleted during refinement; do not treat HIF files without RAW as a culling
problem. The required pairing check is one-way: every remaining RAW should have
a matching HIF preview when the camera produced one. If a review artifact
is useful, use `mt contact-sheet --hif-only` and prefer a single low-resolution
`_contact_sheet.jpg` in the photo directory for non-portraits only, sourced
from `hif/` and excluding `portrait/` and `panorama/`. If portraits exist, also
write `portrait/_contact_sheet.jpg` from `portrait/*/hif/` only, with each
numbered portrait group shown as a separate section. If panorama groups exist,
write `panorama/_contact_sheet.jpg` from `panorama/*/hif/` only. Final contact
sheets should not pad the last page with black or blank placeholder tiles.

Final refinement candidates are photos rated `>=3` stars. Initial cull writes
ratings for every RAW file; both downstream branches operate on every `>=3`
star candidate. The LR branch writes Lightroom/Camera Raw rough-edit XMP
parameters for `>=3` star RAW files. The AI branch generates edited output for
`>=3` star candidates and stores those images under `codex/` beside the source
group: root `codex/` for ordinary photos, `portrait/<n>/codex/` for portraits,
and `panorama/<n>/codex/` for panorama groups.

Editing consistency is mandatory for each batch. Final-candidate images from
the same scene/weather should share the same core edit skeleton: camera profile,
white balance baseline, highlight/shadow strategy, tone curve, Camera
Calibration range, HSL/Mixer caps, vignette policy, sharpening policy, lens
correction, and Upright policy. Per-image deviations are allowed only when the
subject or light genuinely differs, and should be reported explicitly.

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
obsolete. Use `portrait/` for all new work.

Panorama stitching is prepared by organizing source frames, but `media-toolkit`
does not currently include a high-quality stitcher. For final panorama output,
use Lightroom Classic Photo Merge > Panorama, or an external toolchain such as
Hugin/Enblend when installed. When building review sheets for candidate
sequences, keep filename leading zeroes intact with `printf '%05d'` or explicit
filenames. Temporary symlinks to HIF files may not be detected by
`mt contact-sheet`; convert candidate HIF previews to temporary JPEG files
instead, then delete that cache.

## Command Reference

`mt` is the stable human-facing command. Use clear long command names in docs,
scripts, and agent instructions.

| Command | Meaning | Default path behavior |
| --- | --- | --- |
| `mt featured` | Copy original HIF previews whose names match RAW items into `featured/`. | Uses current directory when no path is passed. |
| `mt organize` | Move camera media into type folders such as `raw/` and `hif/`. | Uses current directory when no path is passed. |
| `mt fill-locations` | Plan or apply missing Apple Photos geolocation fixes. | Works on Apple Photos, not the current directory. |
| `mt contact-sheet` | Generate contact sheet images and `manifest.tsv`. | Uses current directory when no path is passed. |
| `mt raw-analyze` | Write RAW histogram and clipping metrics for culling evidence. | Uses current directory when no path is passed. |
| `mt lr-plan` | Suggest Lightroom exposure sliders from RAW histogram evidence. | Uses current directory when no path is passed. |
| `mt rawpy-render` | Render RAW-derived JPEG inputs for selected candidates. | Uses current directory when no path is passed. |
| `mt image-compress` | Compress oversized JPG/JPEG files under a byte cap. | Uses current directory when no path is passed. |
| `mt drone` | Compress drone `.mp4` video with the DJI-oriented preset. | Uses current directory when no path is passed. |
| `mt png-to-jpg` | Convert `.png` images to `.jpg`. | Uses current directory when no path is passed. |

Compatibility aliases still work for interactive use, but they are intentionally
not the documented interface: `mt f`, `mt o`, `mt loc`, `mt sheet`, `mt imgzip`,
and `mt png`.

### RAW Analysis And Rendering

```bash
mt raw-analyze /path/to/photos
mt raw-analyze /path/to/photos --ratings ">=3"
mt lr-plan /path/to/photos --ratings ">=3"
mt lr-plan /path/to/photos --ratings ">=3" --style flower
mt rawpy-render /path/to/photos --ratings ">=3"
```

`mt raw-analyze` reads RAW files through rawpy/LibRaw and writes `raw_stats.tsv`
with linear RAW histogram evidence: black/white levels, percentile brightness,
clipping ratios, shadow ratios, per-channel clipping, and white-balance metadata.
Use it as exposure evidence for culling and LR rough edits; it does not replace
HIF visual review, contact sheets, or human rating judgment.

`mt lr-plan` turns RAW histogram evidence into an auditable Lightroom plan for
`Exposure2012`, `Highlights2012`, `Shadows2012`, `Whites2012`, `Blacks2012`,
and `Contrast2012`. It aligns exposure against the candidate batch median, then
adds per-image high-light protection, shadow recovery, white point restraint,
and black point recovery from RAW clipping and shadow-risk signals. Use
`--style flower` for lavender or flower-field travel scenes where the desired
LR direction is softer contrast, stronger high-light protection, and airier
foreground shadows. The command writes `lr_plan.tsv`; it does not edit XMP by
itself.

`mt rawpy-render` creates RAW-derived JPEG inputs for downstream AI work. By
default it renders `>=3` star RAW files from their lowercase `.xmp` ratings and
writes quality 96, 4:4:4 JPEGs to `codex/rawpy_inputs/` beside the source RAW
group, including `portrait/<n>/codex/rawpy_inputs/` and
`panorama/<n>/codex/rawpy_inputs/`. These are temporary AI input caches, not
final edits.

### Drone Video Compression

```bash
mt drone /path/to/videos
mt drone
```

Compress drone videos to 1080p @ 15Mbps while keeping original frame rate.

- Optimized for DJI drone footage
- High quality for mobile viewing
- Compressed files saved to `compressed/` subdirectory
- Original files remain untouched
- ~112MB per minute

### Image Format Conversion

```bash
mt png-to-jpg /path/to/images
mt png-to-jpg
```

Converts PNG to JPG format.

### Image Size Cap Compression

```bash
mt image-compress /path/to/photos
mt image-compress /path/to/photos --max-bytes 1048576
mt image-compress --dry-run
```

Compresses oversized JPG/JPEG files in place until each processed image is under
the requested byte cap. The script tries JPEG quality changes first, then gentle
Lanczos downscaling only when needed.

### Contact Sheet Generation

```bash
mt contact-sheet /path/to/photos --export-only --exclude-dir PixCake
mt contact-sheet --export-only --exclude-dir PixCake
mt contact-sheet /path/to/photos --hif-only --exclude-dir portrait --exclude-dir panorama
```

Generates contact sheet thumbnails and a `manifest.tsv` mapping sheet
positions back to source files.

- Recursively scans common image formats
- `--export-only` limits the scan to files under `Export`/`export` directories
- `--hif-only` limits the scan to `.HIF`/`.hif` files below directories named
  `hif`; this is the required mode for agent-led culling contact sheets
- `--exclude-dir` can be repeated to ignore tool output directories
- Supports `.hif` previews by decoding them through FFmpeg when possible, with
  a temporary internal JPEG fallback during rendering
- Tile labels show filenames only by default; pass `--show-index` to prefix
  labels with manifest indexes such as `001`
- The final sheet page contains only real image tiles and is not padded with
  black or blank placeholders
- For agent-led culling, place the final combined overview image at
  `_contact_sheet.jpg` for non-portraits only, generated with `--hif-only`
  from root `hif/` while excluding `portrait/` and `panorama/`; portrait
  overviews belong at `portrait/_contact_sheet.jpg` and are generated from
  `portrait/*/hif/`; panorama overviews belong at
  `panorama/_contact_sheet.jpg` and are generated from `panorama/*/hif/`
- Remove redundant review sheets such as `_select_contact_sheet.jpg`,
  `_review_contact_sheet.jpg`, or other ad hoc `*contact_sheet*.jpg` outputs
  before reporting completion; the final allowed paths are only
  `_contact_sheet.jpg`, `portrait/_contact_sheet.jpg`, and
  `panorama/_contact_sheet.jpg`

### Featured Extraction

```bash
mt featured /path/to/photos
mt featured
```

Runs after refinement when `raw/` contains the selected RAW files whose original
HIF previews should be collected.

- RAW filenames in `raw/` define the selected stems
- matching original HIF previews are copied from `hif/`, `portrait/<n>/hif/`,
  and `panorama/<n>/hif/`
- Lightroom exports under `raw/Export/` are not copied by this command
- missing HIF files are reported clearly

### Media File Organization

```bash
mt organize /path/to/sony/import
mt organize /path/to/sony/import --dry-run
mt organize /path/to/import --type xmp:xmp
mt organize
```

Recursively scans every directory under the input path and moves camera media
files into per-directory type subdirectories. By default it prints a final
summary grouped by file type instead of one line per moved file.

- HEIF extensions: `.hif`, `.heif`, `.heic`
- RAW extensions include Sony `.arw`, Fuji `.raf`, iPhone/Adobe `.dng`, and
  other common camera RAW formats
- Existing `hif/` and `raw/` directories are skipped to avoid nested output
- Filename conflicts are preserved by appending `_1`, `_2`, etc.
- `--type folder:ext,ext` adds or replaces a type mapping, for example
  `--type xmp:xmp`
- `--verbose` prints every individual move when you want the full log

### Apple Photos Missing Location Fill

```bash
mt fill-locations --describe
mt fill-locations --force-refresh
mt fill-locations --start 2026-06-01 --end 2026-06-07 --force-refresh
mt fill-locations --start 2026-06-01 --end 2026-06-07 --apply
```

Finds Apple Photos items without a location and plans a location fill from
nearby timeline neighbors. By default it only writes a CSV/HTML plan; pass
`--apply` to write the planned locations back through the Photos app.

- Uses the previous located item when it is within 10 minutes.
- Falls back to the next located item when the previous item is too far away.
- `--threshold-minutes` changes the 10 minute window.
- `--require-next-within-threshold` also requires the next fallback to be within
  the threshold.
- `--start` and `--end` limit which missing items are planned/applied.
- `--force-refresh` refreshes the Photos timeline cache; without it, the script
  reuses `work/photos-location-fill/`.
- `--describe` prints the script's feature summary and exits.
- Every run records start time, finish time, duration, cache mode, and apply
  result in `outputs/photos_location_fill_summary*.txt` and prints the timing to
  stdout.

AppleScript access to Photos is slow. Time ranges reduce the number of missing
items planned or applied, but a forced refresh still walks the Photos timeline to
build the cache. Reusing the cache is much cheaper for repeated runs.

## Project Structure

- `media_toolkit/` - `mt` command launcher and package metadata
- `src/` - Legacy FFmpeg helper modules
- `scripts/` - Existing script entry points, kept for compatibility
- `tests/` - Unit tests
