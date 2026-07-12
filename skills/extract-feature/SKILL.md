---
name: extract-feature
description: Use when the user asks in English or Chinese after detailed edits are finished to finalize selected photos, 成片归档, 提取成片, 整理精修成片, 只拷贝 HIF, or 执行 mt finalize.
---

# 成片归档

## Goal

After the user finishes detailed edits/refinement and exports final picks from Lightroom, archive the final picks:

1. Copy the original HIF previews that correspond to the Lightroom export stems directly into the destination directory provided by the user.
2. Import the Lightroom export JPG/JPEG files into Apple Photos unless the user asks to only copy HIF files.

Do not create a local `featured/` folder as an intermediate output.
Do not use the source photo directory itself, a child of that source directory, `~/Downloads/featured`, or a remembered prior path as the copy destination.

Use the repository containing this skill as the canonical tool repo when local scripts or documentation are needed. Prefer the installed `mt` command; repository resources are relative to this skill at `../..`.

## When To Use

Use this skill when the user says things like:

- "只拷贝 HIF"
- "成片归档"
- "把精修后的成片整理出来"
- "后面的 organize 步骤"
- "执行 mt finalize"

Do not run this during initial cull unless the user explicitly says editing is finished.

## Workflow

1. Inspect the source photo directory and confirm it contains Lightroom exports under `raw/Export/`, `portrait/<n>/raw/Export/`, or scene subdirectories such as `lake-valley/raw/Export`, `snow-top/raw/Export`, and their nested `portrait/<n>/raw/Export` directories.
2. Before any copy command, identify two distinct paths: the source photo directory and the copy destination. If the user gives only one path, treat it as the source photo directory and ask for `--copy-to`. Do not infer a local `featured/` directory, the source root, a child directory, or a prior remembered archive path. Prefer an explicit SD card camera folder such as `/Volumes/<CARD>/DCIM/101MSDCF`. Ask for or infer a scene label when possible, such as `flower-field`, `grassland`, `overcast-travel`, `portrait`, `panorama`, `snow-mountain`, or `night-city`.
3. If an `Export` directory contains an `Export/Pixcake/` subdirectory, treat files in `Pixcake/` as higher-priority final exports. For any same-stem file that exists both directly under `Export/` and under `Export/Pixcake/`, use the Pixcake version for Photos import/reporting and do not import the same-stem direct Export file.
4. Use recursive finalization by default. Internally, preflight and finalize with recursive scanning so existing scene, portrait, and panorama subdirectories that contain their own `raw/`, `hif/`, `portrait/`, or `panorama/` structure are included. Do not expose command syntax to the user unless they ask for it.
5. If the user asks "只拷贝 HIF", "only HIF", "不要导入 Photos", or equivalent, run HIF-only mode and do not import Lightroom export JPG/JPEG files into Apple Photos. Otherwise, import Lightroom export JPG/JPEG files into Apple Photos as part of the same finalization workflow. Use the `Sony` album unless the user provides another album name. For a new batch, use `--photos-dry-run` only if the user has also allowed HIF copying to the destination.

Use the normal finalize path with Apple Photos import.

For HIF-only:

Use the HIF-only finalize path.

6. If the event contains multiple subdirectories that each need extraction, recursive scanning is still the default; include all eligible subdirectories and summarize what was included.

7. If the user asks to inspect or plan without really archiving, do not run `mt finalize`, because `--photos-dry-run` only prevents Apple Photos import and still copies HIF files. Instead, inspect export/HIF filenames with read-only commands and report the planned HIF copy count, missing HIF matches, and planned Apple Photos import count.

8. To validate Apple Photos import while actually allowing HIF copying to the destination, run:

Use a Photos dry-run only for this validation case.

Only run this command if the user has allowed HIF copying to the destination; `--photos-dry-run` only prevents Apple Photos import, not HIF copying.

9. If `mt finalize` is unavailable, use the repository fallback script relative to this skill at `../../scripts/`:

Use the repository fallback script with the same recursive/default behavior.

10. Verify the copy destination contains HIF files whose stems match Lightroom export filenames.
11. Report results using the structured final report format below, with separate HEIF/HIF and Apple Photos sections.

## Behavior Notes

The extraction workflow is stem-based:

- Lightroom export filenames in `raw/Export/`, `portrait/<n>/raw/Export/`, and recursive scene subdirectories define the desired HIF stems
- matching original HIF previews are copied to the user-provided destination from the corresponding `hif/` or `portrait/<n>/hif/` directories
- HIF copy must preserve source metadata and must not rewrite EXIF, timestamps, filenames, or image content
- destination contents are never deleted; existing files are left untouched
- source-side category folders are created during initial cull, not during finalize; finalize should use the existing structure and should not reorganize files by scene
- when `Export/Pixcake/` exists, same-stem Pixcake exports override direct `Export/` files for Photos import/reporting while the HIF copy remains stem-based
- panorama source-frame previews under `panorama/<n>/hif/` are not copied into the destination
- do not copy Lightroom exports to the HIF destination; use them as the final-pick list and import them into Apple Photos unless HIF-only mode was requested
- `--photos-album Sony` imports Lightroom export files into Apple Photos, including panorama Export files; this is separate from HIF copying
- `raw/` itself and existing legacy `featured/` directories should not be searched as candidate source folders
- Lightroom-generated panorama DNG files such as `*-Pano.dng` normally do not have matching HIF previews; do not report them as missing-HIF issues

Do not rate, cull, or rewrite XMP files in this skill. If final user `.xmp` files reveal new style rules, update the repository profiles/docs or memory directly; do not write per-photo-directory style learning reports. Rating and initial sidecar creation belong to `$initial-cull`.

## Final Verification

Before finishing, verify:

- the destination exists and is outside the source photo directory
- copied files match Lightroom export stems
- copied files are original HIF previews
- copied HIF files went to the explicit user-provided destination, not the source root and not a local `featured/` folder
- no unexpected RAW sidecars, Lightroom exports, or temporary review files were copied into the destination
- Lightroom export JPG/JPEG files were imported into Apple Photos, or HIF-only/dry-run/import failure was reported separately
- missing matches are called out clearly, because they usually mean a Lightroom export no longer has a matching original HIF preview

## Final Report Format

After every finalize run, format the user-facing result with two clear sections. Keep it outcome-focused and do not expose command/code details unless the user asks.

Use this structure:

```text
HEIF/HIF 文件归档
- 目标目录: <destination>
- 覆盖范围: <included source folders, recursively summarized>
- 应归档: <count> 张
- 新增复制: <count> 张
- 已存在跳过: <count> 张
- 缺失: <count> 张
- 规则: 原始 HIF/HEIF 按 Export stem 匹配复制；不复制 Lightroom/Pixcake JPG 到 HIF 目标；不覆盖已存在文件。

Apple Photos 归档
- 相册: <album or not imported>
- 应导入: <count> 张
- 本次导入: <count> 张
- 已知重复跳过: <count> 张
- Pixcake 优先: <used/not present/not applicable, with count if useful>
- 状态: <success / dry-run / HIF-only / partial failure>
```

When HIF-only mode is used, still include the Apple Photos section and mark it as `HIF-only，未导入`. When Photos import fails but HIF copying succeeds, report it as a partial failure, not a failed HIF archive.
