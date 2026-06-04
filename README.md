# ffmpeg-py

Video and image processing toolkit based on FFmpeg.

## Quick Start

### Drone Video Compression

```bash
cd scripts
python3 drone_video.py
```

Compress drone videos to 1080p @ 15Mbps while keeping original frame rate.

- Optimized for DJI drone footage
- High quality for mobile viewing
- Compressed files saved to `compressed/` subdirectory
- Original files remain untouched
- ~112MB per minute

### Image Format Conversion

```bash
cd scripts
python3 convert_png_to_jpg.py
```

Converts PNG to JPG format.

### Contact Sheet Generation

```bash
python3 scripts/generate_contact_sheets.py /path/to/photos --export-only --exclude-dir PixCake
```

Generates numbered contact sheet thumbnails and a `manifest.tsv` mapping sheet
positions back to source files.

- Recursively scans common image formats
- `--export-only` limits the scan to files under `Export`/`export` directories
- `--exclude-dir` can be repeated to ignore tool output directories
- Output defaults to `contact_sheets/`

### Media File Organization

```bash
python3 scripts/organize.py /path/to/sony/import
python3 scripts/organize.py /path/to/sony/import --dry-run
python3 scripts/organize.py /path/to/import --type xmp:xmp
python3 scripts/organize.py
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

## Project Structure

- `src/` - Core implementation modules
- `scripts/` - Preset scripts
