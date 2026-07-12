---
name: 学习
description: Use when the user asks in English or Chinese to learn, 学习, 学习调色, 学习调色风格, 学习我的调色, learn Lightroom style, analyze color grading, or update scene style from manual Lightroom refinements.
---

# 学习调色

## Goal

Learn the user's Lightroom/Camera Raw color grading style from manually refined photos, then preserve the lesson in long-term memory and, when appropriate, repo-level style docs/profiles.

This is a learning/maintenance activity, not a third user-facing photo processing workflow. The two user-facing photo workflows remain:

- `initial-cull` (`初筛`): organize, rate, write sidecars, rough-edit, contact sheets
- `extract-feature` (`成片归档`): copy original HIF previews for Lightroom-exported final picks to the explicit user-provided destination and optionally import exports into Apple Photos

Do not combine this learning activity with initial cull or finalization unless the user explicitly asks for multiple workflows.

Use the repository containing this skill as the canonical tool repo when reading prompts, presets, or scripts. Prefer the installed `mt` command; repository resources are relative to this skill at `../..`.

## When To Use

Use this skill when the user says things like:

- "学习"
- "学习调色"
- "学习调色风格"
- "学习我的 Lightroom 调色"
- "从这次精修里学习风格"
- "把这个场景风格沉淀下来"
- "analyze my color grading"
- "learn this scene style"

If the user says "初筛", use `initial-cull` instead. If the user says "归档/成片归档/复制到目标目录/复制到 SD 卡", use `extract-feature` instead.

## Inputs

Required:

- a photo directory
- a scene label, inferred or asked for when needed, such as `flower-field`, `grassland`, `sairim-lake-east`, `overcast-travel`, `portrait`, `snow-mountain`, or `night-city`

Preferred source of final picks:

- `raw/Export/`
- `portrait/<n>/raw/Export/`

Those Lightroom exports define which XMP files represent final refined examples. Do not use every RAW as a learning sample unless the user explicitly says all RAW/XMP files are refined examples.

## Workflow

1. Inspect the photo directory.
2. Build the final-pick stem list from Lightroom exports:
   - root exports: `raw/Export/*`
   - portrait exports: `portrait/<n>/raw/Export/*`
   - ignore `panorama/<n>/raw/Export/` unless the user explicitly asks to learn from a stitched panorama workflow
3. For each export stem, read the corresponding XMP:
   - root: `raw/<stem>.xmp`
   - portrait: `portrait/<n>/raw/<stem>.xmp`
4. Extract style-relevant Lightroom/ACR fields:
   - profile and white balance: `CameraProfile`, `WhiteBalance`, `Temperature`, `Tint`
   - tone: `Exposure2012`, `Contrast2012`, `Highlights2012`, `Shadows2012`, `Whites2012`, `Blacks2012`
   - presence: `Texture`, `Clarity2012`, `Dehaze`
   - curve: `ToneCurvePV2012`, parametric tone curve fields
   - color: `Vibrance`, `Saturation`, HSL/Mixer fields, Camera Calibration hue/saturation fields
   - detail and finishing: noise reduction, sharpening, vignette, lens/profile, Upright/rotate policy
5. Summarize medians/ranges and repeated decisions, and call out meaningful per-image deviations.
6. Compare against existing repo directions when useful:
   - `presets/lightroom-sony-st-travel-base.md`
   - scene profiles in `media_toolkit/rawpy_tools.py` or related profile code
   - `prompts/lightroom-raw-cull-and-rough-edit.md`
7. Preserve the lesson:
   - save a concise long-term memory via `supermemory-save`
   - update repo-level preset/profile/prompt files only if the user asked to fold it into future behavior or the lesson is clearly stable
8. Verify that no photo-directory `style_learning/` report was created.
9. Report what was learned, sample count, source stems, where the lesson was saved, and any uncertainty.

## Hard Boundaries

- Do not run `mt organize`.
- Do not write ratings.
- Do not write or overwrite rough-edit XMP unless the user separately asks for style application.
- Do not run `mt finalize`.
- Do not copy anything to any archive destination or SD card.
- Never delete, clear, clean, deduplicate, or reorganize destination or SD card contents.
- Do not create `style_learning/` inside the photo directory.
- Do not treat one scene's style as universal. Keep separate learned directions for flower fields, grasslands, overcast travel landscapes, portraits, panoramas, snow/mountain scenes, night/city, lakes, and other recurring classes.

## Output Shape

Keep the final report concise:

- scene label
- sample count and source export paths
- key learned style direction
- differences from the current baseline
- where the learning was preserved
- what was not changed

If there are no Lightroom exports or matching XMP files, stop and explain what is missing. Do not fall back silently to all RAW files.
