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
mt f /path/to/photos
mt f
mt o /path/to/import --dry-run
mt o
mt loc --describe
mt sheet /path/to/photos --export-only
mt imgzip /path/to/photos --max-bytes 1048576
```

When a directory-based command is run without a path, `mt` uses the current
directory. Long command names are also available: `featured`, `organize`,
`fill-locations`, `contact-sheet`, and `image-compress`.

## Command Reference

`mt` is the stable human-facing command. Short aliases are for frequent manual
use; long names are for readability in docs, scripts, and agent instructions.

| Short | Long command | Meaning | Default path behavior |
| --- | --- | --- | --- |
| `mt f` | `mt featured` | Copy files whose names match items in `raw/` into `featured/`. | Uses current directory when no path is passed. |
| `mt o` | `mt organize` | Move camera media into type folders such as `raw/` and `hif/`. | Uses current directory when no path is passed. |
| `mt loc` | `mt fill-locations` | Plan or apply missing Apple Photos geolocation fixes. | Works on Apple Photos, not the current directory. |
| `mt sheet` | `mt contact-sheet` | Generate contact sheet images and `manifest.tsv`. | Uses current directory when no path is passed. |
| `mt imgzip` | `mt image-compress` | Compress oversized JPG/JPEG files under a byte cap. | Uses current directory when no path is passed. |
| `mt drone` | `mt drone` | Compress drone `.mp4` video with the DJI-oriented preset. | Uses current directory when no path is passed. |
| `mt png` | `mt png-to-jpg` | Convert `.png` images to `.jpg`. | Uses current directory when no path is passed. |

Agent note: prefer the long command name in generated instructions unless the
user explicitly asks for the shortest command. Prefer `--dry-run` when a command
supports it and the task is exploratory.

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
mt png /path/to/images
mt png
```

Converts PNG to JPG format.

### Image Size Cap Compression

```bash
mt imgzip /path/to/photos
mt imgzip /path/to/photos --max-bytes 1048576
mt imgzip --dry-run
```

Compresses oversized JPG/JPEG files in place until each processed image is under
the requested byte cap. The script tries JPEG quality changes first, then gentle
Lanczos downscaling only when needed.

### Contact Sheet Generation

```bash
mt sheet /path/to/photos --export-only --exclude-dir PixCake
mt sheet --export-only --exclude-dir PixCake
```

Generates numbered contact sheet thumbnails and a `manifest.tsv` mapping sheet
positions back to source files.

- Recursively scans common image formats
- `--export-only` limits the scan to files under `Export`/`export` directories
- `--exclude-dir` can be repeated to ignore tool output directories
- Output defaults to `contact_sheets/`

### Media File Organization

```bash
mt o /path/to/sony/import
mt o /path/to/sony/import --dry-run
mt o /path/to/import --type xmp:xmp
mt o
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
mt loc --describe
mt loc --force-refresh
mt loc --start 2026-06-01 --end 2026-06-07 --force-refresh
mt loc --start 2026-06-01 --end 2026-06-07 --apply
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
