# RAW Initial Cull And Reviewed Lightroom Plan

This prompt contains visual selection criteria only. Command order and safety
belong to `skills/initial-cull/SKILL.md` and `media_toolkit/workflows.json`.

## User prompt

```text
请对下面目录执行完整初筛，并使用仓库的 $initial-cull skill：

<PHOTO_DIRECTORY>

要求：先只读检查和 organize dry-run；按视觉判断分组；为每一张 RAW
建立并审核 ratings.tsv；ratings-apply dry-run 通过后才写入；如进入 LR
分支，先审核 lr_plan.tsv，再用 lr-apply --plan 写入；最后严格运行
verify-cull。不要删除 RAW/HIF，不要归档，不要导入 Photos。
```

## Visual grouping

- Use HIF/HEIF/HEIC previews for composition, focus, expression, and grouping.
  Do not use Lightroom Export JPG files as culling previews.
- Group portraits by person in first-appearance order under `portrait/1/`,
  `portrait/2/`, and so on. A person must be a meaningful subject, not a tiny
  accidental background figure.
- Group panorama source sequences by intentional panning, overlapping content,
  consecutive filenames, and similar exposure under `panorama/1/`, etc.
- Leave ordinary travel scenes in the root `raw/` and `hif/` buckets. The
  repository has no general scene mover, so do not hand-move associated
  RAW/HIF/XMP/Export files into ad-hoc scene folders. Split profile-specific
  work later with reviewed Lightroom plan rows.
- Use reviewed portrait/panorama manifests. The organizer moves associated RAW,
  HIF/HEIF/HEIC, XMP, direct Export, and Pixcake files together.

## Rating rubric

Every RAW path appears exactly once in `ratings.tsv`.

- 5: exceptional and rare; an outstanding final image.
- 4: clearly strong and already at a high final-candidate bar.
- 3: broad review pool for plausible, uncertain, or post-edit-dependent candidates.
- 2: ordinary record, weak composition, or near duplicate.
- 0-1: obvious technical or moment failure.

Judge landscapes by light, atmosphere, foreground/midground/background depth,
leading lines, subject clarity, and uniqueness. Judge portraits/animals by eyes,
expression, pose, face visibility, focus, separation, and background cleanliness.

Group near-duplicates before rating. Keep the 4/5 bar strict, but allow multiple
3-star alternatives when expression, pose, sharpness, framing, or timing has
meaningful differences. Demote only repeats with no comparison value. For flower fields, value location context,
rows/lines, sky, distant mountains, and travel atmosphere instead of selecting
only close-up flowers or insects.

## Reviewed rating contract

The manifest format is:

```text
path	rating
raw/DSC0001.ARW	4
portrait/1/raw/DSC0002.ARW	3
```

`mt ratings-apply` rejects omitted RAW files by default. `--allow-partial` is
only for a later targeted correction, never for a new cull. It writes rating and
required Lightroom sidecar markers without replacing unrelated XMP metadata.

## Lightroom branch

The implemented automatic evidence is deliberately narrow:

- `mt raw-analyze` reads RAW/LibRaw histogram evidence.
- `mt lr-plan` suggests per-image Exposure, Highlights, Shadows, Whites, Blacks,
  and Contrast values and records the generating `plan_style` in each row.
- `mt lr-apply --plan` combines only those reviewed values with an explicitly
  chosen compatible repository scene profile, rejects plan/profile style
  mismatches, and merges owned XMP fields non-destructively.
- Panorama source rows always receive zero post-crop vignette.

The CLI does not infer subject, ISO-specific NR, lens-specific sharpening,
Camera PT portrait treatment, white balance, crop, Upright, or manual rotation.
Do not claim those features or write them ad hoc as if they were reviewed.

For a mixed shoot, review `lr_plan.tsv` by path. Remove portrait, panorama, or
scene rows that are not appropriate for the selected profile, then apply that
reviewed subset. Never apply `travel-rich` recursively to portraits merely
because they are `>=3` stars. Use a separate compatible profile only when one
exists and has been deliberately selected; otherwise leave those candidates for
manual Lightroom refinement.

Preserve camera white balance unless the user separately reviews a correction.
Use `mt styles` and `media_toolkit/style_profiles.json` for actual machine
profiles. `presets/lightroom-sony-st-travel-base.md` is a manual artistic
reference, not automated behavior.

After writing sidecars, the user must select the RAW files in Lightroom Classic
and run `Metadata > Read Metadata from Files`.

For all 3-5-star portraits, generate individual HIF/HEIF/HEIC review JPEGs with
`mt subject-plan`. The Agent must open every preview and write separate local
Exposure, Contrast, Highlights, Shadows, Whites, and Blacks values or an
explicit all-zero `skip`. `mt subject-apply` owns only the correction named
`Media Toolkit Subject Lift`; Lightroom computes its Select Subject pixels.
Run `Update All` in Lightroom for pending AI masks and leave face retouching to
the user's later manual pass.

## Contact sheets and cleanup

- Root `_contact_sheet.jpg`: ordinary `hif/`, excluding portrait and panorama.
- `portrait/<group>/_contact_sheet.jpg`: one overview for each portrait group.
- `panorama/<group>/_contact_sheet.jpg`: one overview for each source sequence.
- Labels are filenames, without numeric manifest prefixes unless requested.
- Remove temporary conversion/sheet directories after final overviews succeed.
- Keep `lr_plan.tsv` and `raw_stats.tsv` until XMP verification passes; then they
  may be removed. Keep the reviewed ratings manifest or its reported SHA-256 as
  audit evidence according to the user's preference.

## Handoff

Report rating counts, `>=3` paths, groups, contact-sheet paths, LR profile and
plan subset actually applied, skipped incompatible rows, uncertainties, and the
Lightroom metadata-read step. Final archive is a separate `$extract-feature`
workflow and never implies source deletion.
