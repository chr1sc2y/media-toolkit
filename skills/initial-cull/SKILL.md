---
name: initial-cull
description: Use when the user asks in English or Chinese to organize, initial-cull, select photos, rate, rough-edit, prepare a new photo shoot directory, 整理照片, 初筛, 选图, 评星, 套预设, 粗修, or 处理新拍摄目录.
---

# 初筛

## Goal

Turn a fresh shoot directory into a Lightroom-ready initial cull:

- ordinary non-portraits remain in the original directory, split into `raw/` and `hif/`
- visually distinct scenes may be split into a small number of broad source-side scene folders during initial organization
- portraits move under `portrait/<person-number>/`, also split into `raw/` and `hif/`
- panorama stitch sequences move under `panorama/<sequence-number>/`, also split into `raw/` and `hif/`
- every RAW receives a lowercase `.xmp` sidecar with rating and Lightroom-readable sidecar markers
- unless the user explicitly asks for initial-cull only/no rough edit, `>=3` star RAW files also receive LR rough-edit XMP fields from `mt lr-plan` and `mt lr-apply`
- final contact sheets are separated: ordinary non-portraits in the root, portraits under `portrait/`, and panorama source frames under `panorama/`
- no temporary review directories remain at the end

Use the repository containing this skill as the canonical tool repo when local scripts or documentation are needed. Prefer the installed `mt` command; repository resources are relative to this skill at `../..`.

## Workflow

1. Inspect the target directory and confirm it exists.
2. Run `mt organize "<target-dir>"` to split media by type. Use `--dry-run` first only when the directory looks unusual or the user asks for caution.
3. Use visual/model judgment to decide whether the initial cull should split the source into broad scene folders before ratings. Keep the top-level category count to 4-5 total, and count `portrait` and `panorama` within that limit. Prefer broad English slug names such as `lake-valley`, `snow-top`, `village-street`, `forest-road`, plus reserved `portrait` and `panorama`; do not create many narrow one-off folders. Move associated RAW, HIF, XMP, and matching `raw/Export` files together without rewriting image metadata or XMP settings.
4. Identify portraits with visual/model judgment. Portrait means a person is a meaningful subject, not just a tiny accidental background figure.
5. Move every portrait pair into `portrait/<person-number>/raw/` and `portrait/<person-number>/hif/`.
6. If portraits contain more than one distinct person, group them by person using visual similarity and first-appearance order:
   - `portrait/1/` is the first person encountered
   - `portrait/2/` is the next distinct person
   - continue as needed
7. Identify panorama stitch sequences by consecutive frames with overlapping scenery, similar exposure settings, and intentional panning. Move each sequence into `panorama/<sequence-number>/raw/` and `panorama/<sequence-number>/hif/` in first-appearance order.
8. Keep ordinary non-portrait, non-panorama RAW/HIF files in the root `raw/` and `hif/`, or in the chosen broad scene folder's `raw/` and `hif/` when scene classification is useful.
9. Write or update lowercase `.xmp` sidecars next to all RAW files, including scene-folder, portrait, and panorama RAW files. Do not leave uppercase `.XMP`.
10. Generate final contact sheets:
   - root `_contact_sheet.jpg` contains ordinary non-portraits only
   - `portrait/_contact_sheet.jpg` contains portraits only, sectioned by `Portrait 1`, `Portrait 2`, etc. when multiple person folders exist
   - `panorama/_contact_sheet.jpg` contains panorama source frames only, sectioned by `Panorama 1`, `Panorama 2`, etc. when multiple panorama folders exist
11. Delete temporary review artifacts: `review_jpg/`, `contact_sheets/`, `.codex_previews/`, and other one-off JPEG conversion caches.
12. Verify counts and report the final structure.
13. Unless the user explicitly requested initial-cull only/no rough edit, continue into the default LR branch for all `>=3` star RAW files: run `mt raw-analyze --ratings ">=3"` when RAW evidence is needed, run `mt lr-plan --ratings ">=3"`, then run `mt lr-apply --ratings ">=3"` with the appropriate scene style (`travel-rich` by default, `flower-rich` for lavender/flower-field travel scenes). After XMP sidecars are written and verified, delete temporary `lr_plan.tsv` and `raw_stats.tsv`; do not keep them in the final photo directory state.
14. Tell the user that Lightroom Classic must read the sidecars: select the imported RAW files, then run `Metadata > Read Metadata from Files`. Do not claim the preset has been applied inside Lightroom until Lightroom has read the sidecars.
15. After the user reads metadata in Lightroom, perform a second review when requested or when changes are experimental: check applied appearance, orientation, crop/upright behavior, exposure consistency, color, and obvious failures. Be especially careful with rotated vertical frames and automatic `PerspectiveUpright=Level`.

## Culling Rules

Rate by image quality and editing potential:

- `>=4`: Select; strong keep, clean focus/composition/light
- `3`: Select; usable but secondary, included in final refinement candidates
- `<=2`: Skip; blurred, bad expression, blocked subject, weak duplicate, or poor technical quality

For portraits, prioritize eyes, expression, pose, face visibility, subject separation, and background cleanliness.

For landscapes and travel scenes, prioritize light, atmosphere, composition, depth, subject clarity, and uniqueness.

For repeated compositions, burst sequences, or same-location frames with only
minor panning/zoom differences, group visually before rating. Usually keep one
4/5-star primary image per group, with at most one 3-star alternate when it has
clear backup value. Downgrade the rest to 2-star Skip even if they are
technically usable. A 3-star file is a final-refinement candidate, not a holding
area for near-duplicates.

Do not delete rejected RAW/HIF files during initial cull unless the user explicitly asks.

## XMP Rough Edit

RAW files are not modified directly. Write Lightroom/Camera Raw-readable `.xmp` sidecars beside each RAW.

These XMP files are the handoff format. They do not automatically change an already-imported Lightroom catalog unless Lightroom reads them. In the final response, explicitly remind the user to run `Metadata > Read Metadata from Files` in Lightroom Classic after import, or after XMP files are created for already-imported photos.

The rough edit is not a blind preset application. Use ISO, shutter speed, aperture, lens model, exposure compensation, RAW histogram evidence, and visual review to make the batch exposure feel consistent. HIF files are useful for culling, composition, focus, and contact sheets, but they are already rendered by the Sony camera and must not be the source of truth for RAW exposure or color grading. Prefer `rawpy`/LibRaw linear RAW statistics for Sony `.ARW` exposure histograms. Consistency means a unified final look, not identical slider values. Detect exposure drift caused by different camera settings, metering, or subject brightness, then adjust `Exposure2012`, `Highlights2012`, `Shadows2012`, `Whites2012`, and `Blacks2012` per image as needed. Do not write one fixed exposure value across a batch unless the images genuinely match.

Every sidecar must use a lowercase `.xmp` extension and include Lightroom-readable markers:

- `crs:HasSettings=True`
- `crs:AlreadyApplied=False`
- `photoshop:SidecarForExtension=ARW`
- `dc:format=image/x-sony-arw`
- `xmpMM:PreservedFileName=<RAW filename>`

Use the media-toolkit Lightroom prompt and preset notes as the source of truth:

- `../../prompts/lightroom-raw-cull-and-rough-edit.md`
- `../../presets/lightroom-sony-st-travel-base.md`

Default rough edit intent:

- natural Sony travel look
- Camera ST or the closest available Standard/ST profile for non-portraits
- Camera PT for Sony portraits when available; fall back to a natural portrait/standard profile if needed
- enforce batch edit consistency for final-candidate images from the same scene/weather: shared camera profile, WB baseline, highlight/shadow strategy, tone curve, Camera Calibration range, HSL/Mixer caps, vignette policy, sharpening policy, lens correction, and Upright policy. Deviate per image only when the subject or light genuinely differs, and report the reason.
- keep exposure consistency RAW-histogram-based and visually reviewed: same-scene candidates should land at a shared brightness/contrast baseline, but their exposure/highlight/shadow/white/black sliders may differ if the source files differ.
- moderate exposure and highlight/shadow recovery
- preserve camera white balance by default: do not write `WhiteBalance`, `Temperature`, or `Tint` in agent-written rough-edit XMP unless the user explicitly asks for WB correction or manually confirms a batch-specific correction after review
- sensible contrast, tone curve, calibration, noise reduction, and lens/profile metadata
- lower global saturation: keep Saturation at 0 or near 0 and use only small Vibrance changes
- prefer subtle Camera Calibration hue/saturation changes over direct Saturation/Vibrance boosts
- do not apply automatic Upright/Level by default; review previews and use small manual `PerspectiveRotate` corrections only when the horizon is visibly wrong
- add a light contrast curve only when it improves depth without crushing shadows or clipping highlights
- add a small sharpening baseline for Tamron 50-400mm F4.5-6.3 A067 images; leave other lenses unsharpened by default
- use ordinary Lightroom/ACR noise reduction sliders for high ISO; this does not run AI Denoise or create DNG files
- gentler Texture, Clarity, and Dehaze for portraits so skin and hair do not become harsh
- if the user asks for a Hasselblad-leaning direction, aim for restrained saturation, smooth highlight roll-off, slightly richer midtones, and clean blue/green separation through calibration
- if borrowing from the user's `Sony ST.xmp`, borrow the structure only at low strength: stronger highlight protection, Texture around 5-7, low global Saturation/Vibrance, subtle Camera Calibration color energy, and its gentle point curve (`ToneCurvePV2012=0,0 / 66,59 / 125,125 / 182,188 / 255,255`). Do not inherit `PerspectiveUpright=Auto`, `Shadows2012=42`, `Dehaze=8`, or RGB calibration saturation around +11/+12/+12. Keep typical caps near `Highlights2012=-55..-70`, `Shadows2012=10..24`, `Dehaze=1..4`, `RedSaturation=2..4`, `GreenSaturation=1..3`, and `BlueSaturation=0..2`.
- keep HSL/Mixer adjustments small during batch rough edits. Use them to restrain grass, water, and sky, not to create the main style. Larger HSL moves are acceptable only during final single-image edits on `>=3` star photos after reviewing the image.
- keep `PostCropVignetteAmount=0` by default. Use `-3..-6` only for centered landscapes or loose edges, and never add vignette to panorama source frames before stitching.

## Contact Sheets

Use `mt contact-sheet` for sheet generation when possible. It supports HIF by making internal temporary JPEG conversions.

Rules for final output:

- final overview filename is `_contact_sheet.jpg`
- root `_contact_sheet.jpg` must exclude portraits and panorama source frames
- `portrait/_contact_sheet.jpg` must include portraits only
- `panorama/_contact_sheet.jpg` must include panorama source frames only
- final tile labels show filenames only
- do not show `001`, `002`, or other numeric prefixes unless the user explicitly asks for manifest index labels
- if index labels are needed, use `mt contact-sheet --show-index`
- a `manifest.tsv` can be kept with generated sheets when useful, but do not leave `contact_sheets/` as the final user-facing overview

If `mt contact-sheet` emits several sheet images, combine them into one reasonably low-resolution `_contact_sheet.jpg` for quick review.

## Panorama Notes

This skill organizes panorama source frames but does not assume a panorama
stitcher is available. For final panorama output, prefer Lightroom Classic
Photo Merge > Panorama so RAW files can produce a panorama DNG. If Hugin,
Enblend, or another stitcher is installed, it may be used after verifying the
CLI binaries exist.

When building candidate panorama review sheets:

- Preserve leading zeroes in filenames. Avoid shell sequence expansions that
  turn `08522` into `8522`; use `printf '%05d'` or explicit filenames.
- Temporary symlinks to HIF files may not be detected by `mt contact-sheet`.
  Convert candidate HIF previews into temporary JPEG files first, then delete
  the temporary cache.
- Legacy portrait paths such as `人像/1/` and `人像/_contact_sheet.jpg` are
  obsolete. Use `portrait/` for all new work.

## Final Verification

Before finishing, verify:

- root `raw/` and `hif/` contain only ordinary non-portrait, non-panorama files
- portrait folders, if present, are grouped by person and each has its own `raw/` and `hif/`
- panorama folders, if present, are grouped by stitch sequence and each has its own `raw/` and `hif/`
- RAW and XMP counts match for every RAW folder
- sidecars are lowercase `.xmp`; no uppercase `.XMP` remains
- sidecars contain the Lightroom-readable marker fields listed above
- after Lightroom reads metadata, visually review representative applied results; flag or fix bad orientation, broken upright/crop, over-bright exposure, muddy shadows, over-saturated color, or harsh texture
- HIF and RAW counts match when the camera produced pairs
- root `_contact_sheet.jpg` exists and excludes portraits and panorama source frames
- `portrait/_contact_sheet.jpg` exists when portraits exist
- `panorama/_contact_sheet.jpg` exists when panorama groups exist
- temporary review directories are gone
- temporary `lr_plan.tsv` and `raw_stats.tsv` files are gone

Final response should summarize counts, contact sheet paths, removed temporary artifacts, anything uncertain about portrait or panorama grouping, and the Lightroom Classic step: `Metadata > Read Metadata from Files`.
