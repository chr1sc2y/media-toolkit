---
name: extract-feature
description: Finalize selected photos after manual Lightroom refinement by matching Export stems to original HIF/HEIF/HEIC files, copying them to an explicit external destination, and optionally importing final JPG exports into Apple Photos. Use for 成片归档, 提取成片, 整理精修成片, 只拷贝 HIF, or mt finalize.
---

# 成片归档

Use Lightroom Export filenames as the authoritative final-pick list. Copy only
matching original HIF/HEIF/HEIC previews to a destination explicitly supplied by
the user. Import final Export images into Apple Photos unless the user requests
HIF-only mode.

## Hard boundaries

- Require two distinct paths: `<photo-dir>` and `<destination-dir>`.
- The destination must be outside the source tree. Never infer `featured/`,
  Downloads, a remembered SD-card path, or any child of the source.
- Never overwrite a different same-named destination file. Byte-identical files
  may be skipped safely; different content is a hard failure.
- Never archive panorama source-frame HIF files. Final stitched panorama exports
  may still be imported into Photos.
- Any missing Export-to-HIF match makes HIF archiving incomplete and must be
  reported as failure. Lightroom `*-Pano.dng` outputs are not HIF expectations.
- Do not rate, cull, reorganize, or rewrite XMP in this workflow.

## 1. Read-only preflight

Normal archive plus Photos plan:

```bash
mt preflight-run finalize "<photo-dir>" --copy-to "<destination-dir>" --scene "<scene>" --photos-album Sony
```

HIF-only plan:

```bash
mt preflight-run finalize "<photo-dir>" --copy-to "<destination-dir>" --scene "<scene>" --hif-only
```

The preflight includes a full `mt finalize --dry-run`; it neither copies files
nor imports into Photos. Continue only on `GO` and after reviewing included
recursive scene roots, missing matches, conflicts, and Pixcake precedence.
`--scene` is an audit label, not a directory filter; recursive discovery still
processes every eligible scene root under `<photo-dir>`.

## 2. Apply

Normal archive and Photos import:

```bash
mt finalize "<photo-dir>" --copy-to "<destination-dir>" --scene "<scene>" --photos-album Sony
```

HIF-only:

```bash
mt finalize "<photo-dir>" --copy-to "<destination-dir>" --scene "<scene>" --hif-only
```

`Export/Pixcake` wins over a same-stem file directly under `Export` for Photos
import. `--photos-dry-run` prevents only Photos import and still allows HIF
copies; use it only when the user has already authorized those copies.

## 3. Verify and report

Rerun the same preflight command after finalization. It must still return `GO`,
and archived files should now appear as byte-identical skips rather than new
copies. This dry run does not submit another Photos import. For Apple Photos,
the command can report the number submitted and whether AppleScript succeeded;
it cannot reliably report Photos' internal duplicate-skip or final imported
counts. Do not invent those numbers.

Report:

```text
HEIF/HIF 文件归档
- 目标目录: <destination>
- 应归档 / 新复制 / 相同跳过 / 缺失或冲突: <counts>
- 状态: <success / failure>

Apple Photos 归档
- 相册: <album or HIF-only>
- 提交导入: <count>
- AppleScript: <success / dry-run / failure / not run>
- 重复跳过与最终导入数: Photos 未提供可靠结果
```

## Optional source cleanup

Finalization does not authorize deletion. If the user separately asks to inspect
redundant source-side HIF files, create a plan only:

```bash
mt hif-prune "<photo-dir>" --mode plan --scene "<scene>"
```

Review `hif_prune_manifest.json` and its TSV sibling. Only after the user
explicitly confirms that exact plan may permanent deletion run:

```bash
mt hif-prune "<photo-dir>" --mode aggressive --apply-plan "<photo-dir>/hif_prune_manifest.json" --confirm-delete --scene "<scene>"
```

Run `mt self-check` first. An installed HEIF decoder is required for meaningful
duplicate inspection and for deletion; if it is unavailable, do not interpret a
zero-delete/unreadable plan as proof that cleanup is complete. Unreadable files,
Export-selected stems, RAW-backed HIF files, and panorama source frames remain
protected.
