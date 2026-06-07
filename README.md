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
mt image-compress /path/to/photos --max-bytes 1048576
```

When a directory-based command is run without a path, `mt` uses the current
directory.

## Agent Workflows

Reusable agent prompts live under `prompts/`. Keep photo folders in their
original travel/import locations; do not copy large photo directories into this
repository.

For Lightroom RAW culling and rough edits:

```bash
prompts/lightroom-raw-cull-and-rough-edit.md
```

Ask the agent to use that prompt with a photo directory:

```text
使用 prompts/lightroom-raw-cull-and-rough-edit.md
对 /path/to/photo-directory 执行 RAW 初筛和 Lightroom 粗修流程。
```

Workflow preset notes live under `presets/`, including the Sony ST travel base
starting point for Lightroom / Camera Raw XMP sidecars.

During agent-led culling, portraits are separated by default. If one person is
present, use `人像/1/raw/` and `人像/1/hif/`. If multiple people are present, use
visual judgment to group them by person in first-appearance order:
`人像/1/`, `人像/2/`, `人像/3/`, etc. Each person directory keeps its own `raw/`
and `hif/` split, then gets culled and rough-edited with gentler portrait
settings. Temporary JPEG caches such as `review_jpg/` should be deleted before
the run is reported complete. If a review artifact is useful, prefer a single
low-resolution `_contact_sheet.jpg` in the photo directory for non-portraits
only. If portraits exist, also write `人像/_contact_sheet.jpg` for portraits
only, with each numbered portrait group shown as a separate section.

## Command Reference

`mt` is the stable human-facing command. Use clear long command names in docs,
scripts, and agent instructions.

| Command | Meaning | Default path behavior |
| --- | --- | --- |
| `mt featured` | Copy files whose names match items in `raw/` into `featured/`. | Uses current directory when no path is passed. |
| `mt organize` | Move camera media into type folders such as `raw/` and `hif/`. | Uses current directory when no path is passed. |
| `mt fill-locations` | Plan or apply missing Apple Photos geolocation fixes. | Works on Apple Photos, not the current directory. |
| `mt contact-sheet` | Generate contact sheet images and `manifest.tsv`. | Uses current directory when no path is passed. |
| `mt image-compress` | Compress oversized JPG/JPEG files under a byte cap. | Uses current directory when no path is passed. |
| `mt drone` | Compress drone `.mp4` video with the DJI-oriented preset. | Uses current directory when no path is passed. |
| `mt png-to-jpg` | Convert `.png` images to `.jpg`. | Uses current directory when no path is passed. |

Compatibility aliases still work for interactive use, but they are intentionally
not the documented interface: `mt f`, `mt o`, `mt loc`, `mt sheet`, `mt imgzip`,
and `mt png`.

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
```

Generates contact sheet thumbnails and a `manifest.tsv` mapping sheet
positions back to source files.

- Recursively scans common image formats
- `--export-only` limits the scan to files under `Export`/`export` directories
- `--exclude-dir` can be repeated to ignore tool output directories
- Supports `.hif` previews by converting them through a temporary internal JPEG
  cache during rendering
- Tile labels show filenames only by default; pass `--show-index` to prefix
  labels with manifest indexes such as `001`
- For agent-led culling, place the final combined overview image at
  `_contact_sheet.jpg` for non-portraits only; portrait overviews belong at
  `人像/_contact_sheet.jpg`

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
