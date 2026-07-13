---
name: initial-cull
description: Organize and review a new photo shoot, group portraits or panorama frames, assign 0-5 star ratings from a reviewed manifest, create contact sheets, and optionally write a Lightroom rough-edit plan. Use for 整理照片, 初筛, 选图, 评星, 粗修, or preparing a new shoot directory. Do not use for final archive or Apple Photos import.
---

# 初筛

Turn one fresh shoot directory into a reviewed, Lightroom-ready cull. Keep all
large media in that directory; the repository stores only tools and skills.

## Safety boundary

- Never delete rejected RAW/HIF files unless the user separately asks.
- Never run `mt finalize`, copy final HIF files, or import into Apple Photos.
- Use HIF/HEIF previews for visual selection and RAW statistics for exposure
  evidence. Do not treat camera-rendered preview color as RAW color truth.
- Preserve existing XMP fields. Ratings and rough-edit commands update only the
  fields they own.

## Workflow

1. Inspect first:

```bash
mt status "<photo-dir>" --json
mt doctor "<photo-dir>"
mt self-check
mt organize "<photo-dir>" --dry-run --verbose
```

The complete workflow requires `ffmpeg` with the `drawtext` filter for contact
sheets. If self-check reports that capability as a warning, fix it before the
contact-sheet stage; do not claim the full cull is complete without the required
overviews.

Review every printed source/destination pair. Name collisions are hard errors;
resolve them explicitly because the organizer never invents suffixes or
overwrites an existing file. If the plan is correct, organize:

```bash
mt organize "<photo-dir>"
```

2. Use visual judgment to group only the two structures backed by reviewed
manifest movers: portraits by person and panorama frames by sequence. Leave
ordinary scenes in the root `raw/` and `hif/` buckets; do not hand-move related
RAW/HIF/XMP/Export files into invented scene folders. Separate ordinary scene
profiles later by keeping only compatible paths in a reviewed Lightroom TSV.
The detailed visual criteria live in
`../../prompts/lightroom-raw-cull-and-rough-edit.md`.

For each grouped type, generate a manifest, fill only the `group` column, review
the dry run, then apply:

```bash
mt manifest-template "<photo-dir>" --kind portrait
mt portrait-organize "<photo-dir>" --dry-run
mt portrait-organize "<photo-dir>"

mt manifest-template "<photo-dir>" --kind panorama
mt panorama-organize "<photo-dir>" --dry-run
mt panorama-organize "<photo-dir>"
```

The organizers move matching RAW, HIF/HEIF/HEIC, XMP, direct Export, and Pixcake
Export files together.

3. Review previews and create `<photo-dir>/ratings.tsv` with exactly:

```text
path	rating
raw/DSC0001.ARW	4
portrait/1/raw/DSC0002.ARW	3
```

Every remaining RAW must appear once. Ratings are integers from 0 through 5:
4-5 strong selects, 3 secondary final candidates, 0-2 skips. Use at most one
3-star alternate for a near-duplicate group unless it has clear backup value.

Validate and apply the reviewed manifest:

```bash
mt ratings-apply "<photo-dir>" --manifest ratings.tsv --dry-run
mt ratings-apply "<photo-dir>" --manifest ratings.tsv
```

4. Unless the user asked for ratings/organization only, create and review the
Lightroom plan for `>=3` candidates:

```bash
mt raw-analyze "<photo-dir>" --ratings ">=3" --output raw_stats.tsv
mt lr-plan "<photo-dir>" --ratings ">=3" --style travel --output lr_plan.tsv
mt lr-apply "<photo-dir>" --ratings ">=3" --style travel-rich --plan lr_plan_reviewed.tsv --dry-run
mt lr-apply "<photo-dir>" --ratings ">=3" --style travel-rich --plan lr_plan_reviewed.tsv
```

Use `--style flower` with `lr-plan` and `--style flower-rich` with `lr-apply`
for flower-field scenes. Use `mt styles` before choosing another profile. The
implemented plan is RAW-histogram-based; do not claim automatic ISO, lens,
subject, white-balance, crop, Upright, sharpening, or noise-reduction tuning.

Before either apply command, create `lr_plan_reviewed.tsv` from the generated
plan and review it row by row. In a mixed directory, remove portrait, panorama,
and incompatible-scene rows from this profile-specific plan; make separate
reviewed plans only for scene/profile pairs that are actually compatible. Never
apply `travel-rich` recursively to portraits merely because they are `>=3`.
Keep the generated `plan_style` column unchanged: `lr-apply` rejects a profile
whose registered plan style is incompatible with the reviewed plan.

5. Generate the allowed final HIF-only overviews:

```bash
mt contact-sheet "<photo-dir>" --hif-only --exclude-dir portrait --exclude-dir panorama --output /tmp/mt-root-sheet --final-overview "<photo-dir>/_contact_sheet.jpg"
mt contact-sheet "<photo-dir>/portrait/<group>" --hif-only --output "/tmp/mt-portrait-<group>-sheet" --final-overview "<photo-dir>/portrait/<group>/_contact_sheet.jpg"
mt contact-sheet "<photo-dir>/panorama/<group>" --hif-only --output "/tmp/mt-panorama-<group>-sheet" --final-overview "<photo-dir>/panorama/<group>/_contact_sheet.jpg"
```

Repeat the matching command for every numeric group. The portrait/panorama
organizers do this automatically after moving files. Remove temporary plan/stat
files only after the XMP result has passed verification.

6. Verify strictly:

```bash
mt verify-cull "<photo-dir>"
```

Do not use `--legacy-structure-only` for a new cull. It exists only for old
folders that predate rating/marker validation.

## Handoff

Report rating counts, grouped folders, contact-sheet paths, and unresolved visual
uncertainty. Remind the user to select the RAW files in Lightroom Classic and
run `Metadata > Read Metadata from Files`; writing sidecars does not update an
already imported catalog by itself.
