# media-toolkit

Personal command-line tools and repository-owned Codex skills for photo/video
workflows. The repository contains code and reusable procedure only—never photo
libraries, Vault/Ledger data, or personal spending sources.

## Install

Use a virtual environment so Homebrew/system Python remains untouched:

```bash
git clone git@github.com:chr1sc2y/media-toolkit.git
cd media-toolkit
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
sh scripts/install-codex-skills.sh
sh scripts/install-codex-skills.sh --check
```

Contact sheets also require an external FFmpeg build with the `drawtext` filter
(libfreetype). Verify it with `ffmpeg -hide_banner -filters | grep drawtext`.
`mt self-check` reports this as a capability warning when unavailable. Install a
compatible FFmpeg build before running the complete initial-cull workflow.

The skill installer links all entries in `skills/manifest.json` into
`${CODEX_HOME:-$HOME/.codex}/skills`. It preflights the complete operation and
refuses to replace real directories or unrelated symlinks. Restart Codex after
the first registration.

After a pull, the skill links already point at the updated checkout. Re-run the
editable install only when package metadata or dependencies changed.

## Discover the CLI

```bash
mt
mt commands
mt commands finalize
mt commands --json
mt workflows
mt workflows initial-cull
mt workflows --json
mt self-check
mt self-check --json
```

The command registry is `media_toolkit/command_registry.py`; the workflow
registry is `media_toolkit/workflows.json`. They are the machine-readable
contract. Files under `scripts/` are compatibility wrappers.

## Repository-owned skills

| Skill | Trigger/use | Primary path |
| --- | --- | --- |
| `initial-cull` | 初筛、整理照片、选图、评星、可选 LR 粗修 | `organize → ratings-apply → lr-plan → lr-apply → verify-cull` |
| `extract-feature` | 精修结束后的成片归档、只拷贝 HIF | `preflight-run finalize → finalize`; cleanup is a separate plan/confirmation |
| `learn-color-style` | 学习调色、分析手工精修 XMP 风格 | `styles → learn-style` |
| `apple-photos-location-fill` | 审计并补 Apple Photos 缺失地点 | `fill-locations` plan, review, then `--apply-plan` |

Each complete skill is versioned under `skills/<name>/`, so another machine gets
the same workflow by cloning this private repository and running the installer.

## Initial cull

The CLI closes the ratings dependency explicitly: visual review produces a TSV,
then `ratings-apply` writes safe, Lightroom-readable sidecars.

```bash
mt status /path/to/shoot --json
mt doctor /path/to/shoot
mt organize /path/to/shoot --dry-run --verbose
mt organize /path/to/shoot

# Create and review /path/to/shoot/ratings.tsv with path and rating columns.
mt ratings-apply /path/to/shoot --manifest ratings.tsv --dry-run
mt ratings-apply /path/to/shoot --manifest ratings.tsv

mt raw-analyze /path/to/shoot --ratings ">=3" --output raw_stats.tsv
mt lr-plan /path/to/shoot --ratings ">=3" --output lr_plan.tsv
# Review rows and save only travel-rich-compatible paths as lr_plan_reviewed.tsv.
mt lr-apply /path/to/shoot --ratings ">=3" --plan lr_plan_reviewed.tsv --style travel-rich --dry-run
mt lr-apply /path/to/shoot --ratings ">=3" --plan lr_plan_reviewed.tsv --style travel-rich
mt verify-cull /path/to/shoot
```

`lr-apply` merges only owned XMP fields and preserves crop, perspective, masks,
labels, comments, and unknown metadata. The current plan is histogram-based; it
does not claim automatic ISO/lens/subject/WB/crop/sharpening/NR decisions.
Each generated plan row records its `plan_style`; `lr-apply --plan` rejects a
scene profile whose registered plan style does not match that reviewed plan.
For mixed shoots, make separate reviewed plans by compatible scene/profile and
leave portraits or panorama sources out of `travel-rich` unless a deliberately
selected compatible profile exists.

Portrait/panorama manifests are supported by:

```bash
mt manifest-template /path/to/shoot --kind portrait
mt portrait-organize /path/to/shoot --dry-run
mt portrait-organize /path/to/shoot

mt manifest-template /path/to/shoot --kind panorama
mt panorama-organize /path/to/shoot --dry-run
mt panorama-organize /path/to/shoot
```

Associated RAW, HIF/HEIF/HEIC, XMP, direct Export, and Pixcake files move
together. Detailed visual criteria remain in
`prompts/lightroom-raw-cull-and-rough-edit.md` and
`presets/lightroom-sony-st-travel-base.md`.

## Final archive

Always preflight with an explicit external destination:

```bash
mt preflight-run finalize /path/to/shoot \
  --copy-to /Volumes/CARD/DCIM/101MSDCF \
  --scene general-travel

mt finalize /path/to/shoot \
  --copy-to /Volumes/CARD/DCIM/101MSDCF \
  --photos-album Sony \
  --scene general-travel
```

Use `--hif-only` to skip Photos import. Full `--dry-run` performs neither copy
nor Photos import. `--photos-dry-run` prevents only Photos import and can still
copy HIF files.

Archive matching is complete-or-fail per discovered source base. HIF, HEIF, and
HEIC are accepted case-insensitively; missing stems and different-content name
collisions fail. Panorama source frames are excluded from HIF archiving while a
final panorama Export remains eligible for Photos import.

After a real finalize, rerun the same preflight. It should remain `GO` and show
the destination files as byte-identical skips. `--scene` labels the audit output;
it does not restrict recursive scene discovery.

Source cleanup is never implied by finalization:

```bash
mt hif-prune /path/to/shoot --mode plan --scene general-travel
# Review hif_prune_manifest.json and its TSV sibling.
mt hif-prune /path/to/shoot --mode aggressive \
  --apply-plan /path/to/shoot/hif_prune_manifest.json \
  --confirm-delete \
  --scene general-travel
```

The second command is permanent and requires separate user confirmation plus a
working HEIF decoder.

## Learn a Lightroom style

```bash
mt styles
mt learn-style /path/to/refined-shoot --scene grassland --json
mt learn-style /path/to/refined-shoot \
  --scene grassland \
  --baseline travel-rich \
  --json
```

Learning recursively uses final Export/XMP pairs, prefers Pixcake, ignores
rating-only sidecars, and reports frequencies, numeric min/median/max, and
baseline deviations for develop fields actually present in the sample XMP. It
does not infer differences for omitted fields and is read-only.

## Apple Photos missing locations

```bash
mt fill-locations --force-refresh
# Review outputs/photos_location_fill_plan.html and the JSON plan.
# Record the printed Plan SHA-256 for the exact approved JSON.
mt fill-locations --apply-plan work/photos-location-fill/photos_location_fill_plan.json
```

Planning compares previous and next located neighbors by timestamp. Applying a
reviewed plan never rescans or rebuilds choices; the apply-stage SHA-256 must
match the approved plan digest.

## Other commands

```bash
mt contact-sheet /path/to/photos --hif-only
mt rawpy-render /path/to/photos --ratings ">=3"
mt image-compress /path/to/photos --max-bytes 1048576
mt drone /path/to/videos
mt png-to-jpg /path/to/images
mt batch-report /path/to/photos
```

Portrait candidates rated 3–5 can use a reviewed per-image Select Subject layer:

```bash
mt subject-plan /path/to/shoot --ratings ">=3" --output subject_plan.tsv --preview-dir /tmp/mt-subject-review
mt subject-apply /path/to/shoot --plan subject_plan_reviewed.tsv --dry-run
mt subject-apply /path/to/shoot --plan subject_plan_reviewed.tsv
```

The Agent reviews every generated HIF/HEIF/HEIC preview and supplies different
values per image. Lightroom Classic computes the actual AI subject pixels after
metadata is read; the tool does not run its own segmentation model.

The portrait and panorama organizers generate one overview inside each numeric
group, such as `portrait/1/_contact_sheet.jpg` or
`panorama/2/_contact_sheet.jpg`; no aggregate sheet is kept in either parent.

## Development

```bash
python -m pip install build
python -m unittest discover -s tests
mt self-check --json
sh scripts/install-codex-skills.sh --check
python -m build --wheel
```

CI runs the unit suite on Python 3.9 and a current Python, then installs the wheel
in an isolated environment and smoke-tests `mt styles` and `mt self-check`.

## Structure

```text
media_toolkit/       package logic, registries, and command modules
scripts/             thin compatibility wrappers and skill-link shell entrypoint
skills/              canonical repository-owned Codex skills
prompts/ presets/    detailed visual/LR guidance
tests/               unit and safety-regression tests
docs/superpowers/    design and implementation records
src/                 tested legacy import compatibility shims
```
