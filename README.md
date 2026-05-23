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

## Project Structure

- `src/` - Core implementation modules
- `scripts/` - Preset scripts
