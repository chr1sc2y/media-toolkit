---
name: learn-color-style
description: Analyze manually refined Lightroom Export/XMP evidence and summarize a scene-specific color-grading style. Use for 学习调色, 学习我的 Lightroom 调色, analyze color grading, learn Lightroom style, or updating a stable scene profile. Do not trigger for generic learning questions, initial culling, or final archive.
---

# 学习调色

This is a read-only analysis workflow. It learns from final Lightroom Export
stems and their matching XMP sidecars; it does not process or archive photos.

## Boundaries

- Do not organize media, write ratings/XMP, finalize, copy, import, or delete.
- Do not create a report directory inside the photo folder.
- Do not silently fall back to every RAW/XMP when final exports are missing.
- Keep lessons scene-specific; one shoot is not a universal preset.

## Inspect evidence

List existing baselines:

```bash
mt styles
```

Analyze recursively with a scene label:

```bash
mt learn-style "<photo-dir>" --scene "<scene>" --json
```

When an existing profile is a meaningful comparison baseline:

```bash
mt learn-style "<photo-dir>" --scene "<scene>" --baseline travel-rich --json
```

The command recursively discovers ordinary and portrait Export roots, excludes
panorama source-frame workflows, prefers `Export/Pixcake` over same-stem direct
exports, and counts each logical final image once. Rating-only sidecars are
reported but not counted as style samples.

Review:

- sample count, source Export paths, and missing/ignored XMP
- value frequencies plus numeric minimum/median/maximum
- profile, tone, curve, HSL/Mixer, calibration, detail, noise reduction, lens,
  vignette, Upright, and rotate fields actually present
- differences from the selected repository baseline for fields actually
  present in each sample XMP; omitted fields are not inferred

## Preserve a lesson

Update `media_toolkit/style_profiles.json`, the Lightroom preset note, or the
rough-edit prompt only when the user explicitly asks to fold the result into
future behavior. As a default evidence floor, require the same direction across
at least three valid refined samples with no strong counterexample; report when
the set is smaller or mixed instead of editing a profile automatically. After a
requested update, run:

```bash
mt styles
python -m unittest tests.test_style_profiles tests.test_style_learning
```

Save external long-term memory only when the user asks; the analysis command
itself writes no learning report.

Report the scene, valid sample count, repeated direction, meaningful deviations,
files changed (if any), uncertainty, and what was deliberately left unchanged.
