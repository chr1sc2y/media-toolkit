# Media Toolkit Agent Guide

This repository is becoming `media-toolkit`. The Git repository may still live
at `media-workflow` until the remote/local folder is renamed.

## Primary Interface

Use `mt` with clear long command names as the primary interface for humans and
agents. The old files in `scripts/` remain compatibility entry points, but new
instructions should prefer `mt`.

| Clear command | Purpose |
| --- | --- |
| `mt finalize` | Copy matching original HIF previews to a user-provided SD card directory and import Lightroom export JPGs into Apple Photos after manual refinement. |
| `mt organize` | Move camera media into per-directory type folders such as `raw/` and `hif/`. |
| `mt fill-locations` | Plan or apply missing Apple Photos location fixes. |
| `mt contact-sheet` | Generate contact sheets and a manifest. |
| `mt raw-analyze` | Write RAW histogram and clipping metrics for culling evidence. |
| `mt lr-plan` | Suggest Lightroom exposure sliders from RAW histogram evidence. |
| `mt lr-apply` | Write Lightroom rough-edit XMP fields from RAW evidence and scene style profiles. |
| `mt rawpy-render` | Render RAW-derived JPEG inputs for selected candidates. |
| `mt image-compress` | Compress oversized JPG/JPEG files under a maximum byte size. |
| `mt drone` | Compress drone videos with the existing preset. |
| `mt png-to-jpg` | Convert PNG images to JPG. |

Directory-based commands default to the current directory when no path is
provided. `mt fill-locations` operates on Apple Photos and does not use the
current directory as a media input.

Compatibility commands and short aliases such as `mt featured`, `mt f`, `mt o`, and `mt loc` exist only as compatibility
shortcuts. Do not use them in documentation or generated instructions unless the
user explicitly asks for aliases.

## Reusable Agent Workflows

Reusable prompts live under `prompts/`; workflow preset notes live under
`presets/`. Keep photos in their original travel/import directories instead of
copying them into this repository.

For photo initial culling and downstream edit branches, use:

```text
prompts/lightroom-raw-cull-and-rough-edit.md
```

The user should only need to provide the target photo directory. Apply the
prompt to that external directory, write rating sidecars next to the RAW files,
and leave large media files outside this repository.

For photo culling runs, separate portraits by default. Use visual judgment to
group portraits by person in first-appearance order: `portrait/1/`,
`portrait/2/`, `portrait/3/`, etc. Detect panorama stitch sequences by looking
for consecutive frames with overlapping scenery, similar exposure settings, and
intentional panning; move each sequence into `panorama/1/`, `panorama/2/`,
`panorama/3/`, etc. Inside each portrait or panorama directory, keep the same
media split such as `raw/` for RAW plus XMP sidecars and `hif/` for matching
previews. Initial cull must rate every RAW file, including portrait, panorama,
and ordinary files, by writing lowercase `.xmp` sidecars. Do not write XMP
label fields; star ratings are the durable selection signal. Include
Lightroom-readable sidecar markers such as
`crs:HasSettings=True`, `crs:AlreadyApplied=False`,
`photoshop:SidecarForExtension=ARW`, `dc:format=image/x-sony-arw`, and
`xmpMM:PreservedFileName`.

Initial cull completes organization, grouping, ratings, and review contact
sheets before any downstream edit work. If the user does not explicitly choose
AI, both branches, or "initial-cull only", continue by default into the LR
branch and write Lightroom/Camera Raw rough edit XMP parameters for `>=3` star
RAW files. Stop after initial-cull deliverables only when the user explicitly
asks to organize/rate/select without LR rough edits. Do not blindly apply one
fixed preset in the LR branch: tune exposure, contrast, tone curve, color
calibration, noise reduction, and lens-specific sharpening from ISO, shutter,
aperture, lens, RAW histogram evidence, and visual review.
Do not apply automatic Upright/Level by default; inspect previews and use small
manual `PerspectiveRotate` corrections only when needed.
Use `Camera PT` for Sony portraits when available; use gentler portrait settings
for Texture, Clarity, and Dehaze. Use HIF previews as the visual source for
initial recognition, composition/focus review, and contact sheets. Do not use
HIF brightness or color as the source of truth for RAW exposure or color
grading, because HIF files already include Sony camera rendering. Prefer
`rawpy`/LibRaw linear RAW statistics for exposure histograms on final
candidates; `mt raw-analyze --ratings ">=3"` may be used to write
`raw_stats.tsv` evidence for candidate exposure, clipping, and shadow-risk
review. For the LR branch, run `mt lr-plan --ratings ">=3"` after ratings are
written; it converts RAW histogram evidence into auditable Lightroom slider
suggestions for `Exposure2012`, `Highlights2012`, `Shadows2012`, `Whites2012`,
`Blacks2012`, and `Contrast2012`. Use `mt lr-apply --ratings ">=3"` to write
agent rough-edit sidecars from those RAW evidence rules plus a scene style
profile. Use `--style flower-rich` for lavender/flower-field travel scenes
that should follow the user's `1.xmp` direction, and `--style travel-rich` for
the richer general travel landscape baseline. Do not keep `lr_plan.tsv` or
`raw_stats.tsv` in the final photo directory state; remove those temporary
evidence files after XMP sidecars have been written and verified. Use HIF only as a visual aid. Do not use Lightroom
`raw/Export/*.jpg` exports for portrait detection, panorama detection, culling
review, or final contact sheets. If a portrait RAW is moved, move its corresponding
`raw/Export/*.jpg` along with the RAW as an associated export only. Keep
temporary JPEG conversion caches out of the final photo directory state. When
checking RAW/HIF pairing, HIF-only files are normal backup files after rejected
RAWs have been deleted during refinement; do not report HIF files without RAW
as a problem. The invariant is one-way: every remaining RAW must have a matching
HIF preview when the camera produced one. When
contact sheets are useful, use `mt contact-sheet --hif-only` and keep portrait
and non-portrait overviews as separate files: the photo directory's
`_contact_sheet.jpg` must include non-portrait HIF previews from `hif/` only,
excluding `portrait/` and `panorama/`; if a portrait directory exists, write
`portrait/_contact_sheet.jpg` from `portrait/*/hif/` only, with each numbered
portrait group shown as a separate section. If a panorama directory exists,
write `panorama/_contact_sheet.jpg` from `panorama/*/hif/` only, with each
numbered panorama group shown as a separate section. Final contact sheets
should label tiles by filename only, without `001`/`002` index prefixes, and the
last sheet page should not be padded with black or blank placeholder tiles.
Remove redundant review sheets such as `_select_contact_sheet.jpg`,
`_review_contact_sheet.jpg`, or ad hoc `*contact_sheet*.jpg` outputs before
reporting completion; the final allowed contact sheet paths are only
`_contact_sheet.jpg`, `portrait/_contact_sheet.jpg`, and
`panorama/_contact_sheet.jpg`.

Final refinement candidates are photos rated `>=3` stars. Both downstream
branches operate on all `>=3` star files:

- LR branch: write Lightroom/Camera Raw rough-edit XMP parameters for each
  `>=3` star RAW, using `mt lr-plan` output as the exposure/highlight/shadow
  evidence layer and `mt lr-apply` to write the chosen scene style profile.
  Then the user can read metadata in Lightroom Classic and continue manual
  refinement/export.
- AI branch: generate AI-edited output for each `>=3` star candidate without
  overwriting RAW, HIF, or XMP files. Store ordinary outputs in `codex/` beside
  the root `raw/` and `hif/`; store portrait outputs in
  `portrait/<n>/codex/`; store panorama outputs in `panorama/<n>/codex/`.

After Lightroom manual refinement, use `mt finalize` for the final
"成片归档" workflow. This step uses Lightroom exports as the authoritative final
selection list: filenames in root `raw/Export/` and
`portrait/<n>/raw/Export/` define the stems to archive. It copies the matching
original HIF previews directly to the user-provided SD card directory from
`--copy-to`; if no SD card destination is provided, ask the user for one instead
of inferring a local `featured/` folder. It copies only matching HIF files from
`hif/` or `portrait/<n>/hif/`; it does not copy panorama source-frame HIF files
from `panorama/<n>/hif/`, does not copy the Lightroom export files to the SD
card, and does not generate a contact sheet by default. Use `--scene` to name
the scenery class for reporting and future repo-level style tuning, for example
`mt finalize <photo-dir> --copy-to /Volumes/SD/DCIM/101MSDCF --photos-album Sony --scene flower-field`.
Copy HIF with metadata-preserving semantics; do not rewrite EXIF, timestamps,
or image content. Never delete SD card contents; leave existing files untouched.
By default, `mt finalize` imports Lightroom export images into the Apple Photos
`Sony` album; `--photos-album` can override the album name. Imports include
files from `raw/Export/`, `portrait/<n>/raw/Export/`, and
`panorama/<n>/raw/Export/` as part of finalization. Use `--photos-dry-run` first
when validating a batch.
`--photos-dry-run` only prevents Apple Photos import; it does not make HIF
copying dry-run. Photos import may require macOS automation permission and may
not fully prevent duplicates, so report any import failure as a separate partial
failure from HIF copying.
Do not write per-photo-directory style learning reports; fold user refinement
learning back into repository profiles, preset notes, prompts, and memory.
Lightroom-generated panorama DNG files such as `*-Pano.dng` are final panorama
derivatives and normally do not have matching HIF previews; do not report their
missing HIF as a problem.

The AI branch must use RAW-derived input images, not camera-rendered HIF or
Lightroom export JPGs, as the editable base. Render each selected RAW through
`rawpy`/LibRaw into a full-resolution sRGB JPEG at quality 96 with 4:4:4
chroma (`subsampling=0`) and keep those files only as temporary AI input
caches. Use `codex/rawpy_inputs/` for ordinary photos,
`portrait/<n>/codex/rawpy_inputs/` for portraits, and
`panorama/<n>/codex/rawpy_inputs/` for panorama groups. JPEG quality 96 is the
default because it is visually high quality and broadly compatible; do not use
JPEG quality 100 as a default and do not describe it as lossless. Do not make
PNG, TIFF, or DNG the default AI input format. If a high-quality rendered
master is explicitly needed, 16-bit TIFF may be generated as a separate
optional side product; DNG remains for Lightroom/Adobe workflows such as
enhance/denoise or panorama merge, not for the default AI branch.

AI outputs are final rendered derivatives, not metadata edits. Keep final AI
images and any manifest or prompt record in the corresponding `codex/`
directory, and record the source RAW path, XMP rating, rawpy render parameters,
AI edit intent, and final output path. After final images, manifests, and
contact sheets have been verified, delete the temporary `rawpy_inputs/` cache
before reporting completion unless the user explicitly asks to keep it for
reruns. AI edits should stay restrained: remove passersby when requested, but
do not replace or reshape railings, roads, terrain, buildings, or other
environment objects. For overcast scenes, only reduce some cloud cover and add
soft, plausible sunlight or a little blue sky; avoid obvious synthetic skies,
heavy relighting, focal-length exaggeration, or perspective expansion unless a
deliberate crop or edge extension is needed for composition.

Use this default AI edit intent for travel landscape candidates unless the user
requests a different look: a stronger Hasselblad-natural and user Sony ST
fusion, not a pale neutral edit. Keep natural composition and perspective,
preserve terrain/roads/railings/buildings/water/mountain lines, but give the
image richer midtones, firmer micro-contrast, protected highlights, clean
blue/green/cyan separation, grounded greens, and a more premium travel-photo
color presence. The user's `Sony ST.xmp` influence is: strong highlight
protection, light Texture, Dehaze energy, a gentle point curve, and color
energy from Camera Calibration rather than direct global saturation. Borrow
that structure visually, but do not inherit its automatic Upright, heavy
shadows, strong Dehaze, strong calibration saturation, or visible vignette.
Vignette should be off by default or extremely subtle when it genuinely helps
the composition; avoid obvious dark corners. For sky and light, reduce cloud
density only slightly when needed, add soft plausible sunlight, and reveal only
a little blue sky if it fits the scene. Avoid plastic textures, excessive
clarity, oversaturated greens, teal-orange grading, fake bokeh, obvious AI
skies, changed perspective, or expanded focal-length feel.

Editing consistency is mandatory for each batch. Final-candidate images from
the same scene/weather should share the same core edit skeleton: camera profile,
white balance baseline, highlight/shadow strategy, tone curve, Camera
Calibration range, HSL/Mixer caps, vignette policy, sharpening policy, lens
correction, and Upright policy. Per-image deviations are allowed only when the
subject or light genuinely differs, and the final report should call out those
intentional deviations.

Consistency means a unified final look, not identical slider values. Detect
exposure drift caused by different camera settings, metering, or subject
brightness by comparing RAW histogram/tonal evidence, preferably from
`rawpy`/LibRaw for Sony `.ARW` files, plus visual review. Adjust
`Exposure2012`, `Highlights2012`, `Shadows2012`, `Whites2012`, and `Blacks2012`
per image as needed so the batch lands at a shared brightness and contrast
baseline. Do not write one fixed exposure value across a batch unless the
images genuinely match.

Before assigning final-candidate ratings, group repeated compositions, burst
sequences, and same-location frames with only minor panning or zoom changes.
Usually keep one 4/5-star primary image per group, with at most one 3-star
alternate when it has clear backup value. Downgrade the rest to 2-star Skip even
when they are technically usable.
For flower-field scenes such as lavender fields, do not over-prefer close-up
flowers or insects. User refinement favored wide travel-place images with field
rows, sky, distant mountains, and strong location context; close flower/bee
frames should be selected only when focus, gesture, background, and information
value are clearly strong.

Lavender/flower-field LR refinement feedback from 2026-06-09: compared with the
Codex baseline, the user's finished style used stronger high-light protection,
much more shadow recovery, softer contrast, a slightly lifted/soft top-end point
curve, stronger Camera Calibration color energy, controlled blue HSL, and a
subtle `PostCropVignetteAmount=-5`. Treat this as a flower-field travel-scene
direction, not a universal landscape default. Keep automatic Upright off for
agent-written rough edits unless the user explicitly asks for it or has manually
confirmed it per image.

User tone-curve preference: use a gentle S-shaped point curve when it helps the
image, with protected endpoints rather than crushed blacks or clipped whites.
Lightly lift or preserve the black point, roll the white point down when needed,
slightly deepen lower-mids, and slightly lift upper-mids. This should add modest
contrast while preserving highlight and shadow texture. Keep the exact curve
scene-specific; do not force one numeric curve onto every landscape, portrait,
night, snow, or high-contrast scene.

For agent-written LR rough edits, preserve the camera white balance by default:
do not write `WhiteBalance`, `Temperature`, or `Tint` unless the user explicitly
asks for WB correction. Always enable lens profile correction, keep automatic
transform/Upright off, and keep post-crop vignette subtle; never write
`PostCropVignetteAmount` darker than `-7`.

Long-term style learning is part of the finalization workflow, not a third
separate user-facing workflow. The two user-facing workflows are:

1. Initial cull (`初筛`): organize, group, rate, write review sheets, and
   by default write LR rough edits for Lightroom refinement unless the user
   explicitly asks for initial-cull only.
2. Finalize (`成片归档`): after the user manually refines photos in Lightroom,
   export the final picks from Lightroom, then copy matching original HIF
   previews directly to the user-provided SD card directory and import
   Lightroom export JPGs into Apple Photos. The final pick list comes from
   `raw/Export/` and `portrait/<n>/raw/Export/`, not from every remaining RAW.
   When manual XMP refinements teach a new scene direction, update repository
   profiles/docs directly instead of writing a local learning report into the
   photo directory.

Do not collapse the user's style into one universal preset; maintain separate
learned directions for flower fields, grasslands, overcast travel landscapes,
portraits, panoramas, snow/mountain scenes, night/city work, and any other
recurring scenery class that emerges from manual refinements.

Legacy portrait paths such as `人像/1/` and `人像/_contact_sheet.jpg` are
obsolete. Use `portrait/` for all new work, even when the user writes in
Chinese.

Panorama stitching notes:

- This repository can identify and organize panorama source frames, but it does
  not currently provide a built-in high-quality panorama stitcher.
- For final output, prefer Lightroom Classic Photo Merge > Panorama so RAW
  source frames can produce a panorama DNG with Lightroom's projection,
  boundary warp, and fill controls.
- Open-source automation is acceptable only when the needed tools are actually
  installed and the run can be verified. The preferred open-source path is the
  Hugin/libpano toolchain (`cpfind`, `autooptimiser`, `nona`, `enblend` or
  `enfuse`) fed by RAW-derived 16-bit TIFF intermediates rendered through
  `rawpy`/LibRaw. OpenCV's stitcher may be used for low-resolution previews or
  feasibility checks, but do not treat it as the default high-quality RAW
  panorama path.
- Do not ask AI to invent a panorama from separate source frames. Stitch first,
  then use AI only on the stitched panorama for restrained finishing, small
  edge fills, cleanup, or soft sky/light adjustments. If stitched panorama
  edges are heavily irregular, prefer crop or Lightroom boundary warp/fill over
  large AI reconstruction; AI fill is acceptable only for small missing borders
  where it will not alter terrain, river, road, railing, building, or mountain
  geometry.
- Hugin/Enblend can be used as an external CLI alternative when installed; do
  not claim panorama stitching is available until the relevant binaries are
  present.
- When reviewing candidate sequences, preserve leading zeroes in filenames.
  Avoid shell brace or sequence expansions that turn `08522` into `8522`; use
  `printf '%05d'` or explicit filenames.
- `mt contact-sheet` may not follow temporary symlinks to HIF files in ad hoc
  review folders. If candidate-only review sheets are needed, convert the HIF
  previews into temporary JPEG files first, then delete the temporary cache.

## Development Rules

- Keep `media_toolkit/cli.py` as the command launcher.
- Keep `scripts/` as compatibility entry points unless a migration explicitly
  removes one.
- Add or update tests under `tests/` when command behavior changes.
- Run `python3 -m unittest discover -s tests` before claiming completion.
- Do not commit generated local runtime outputs such as `outputs/`, `work/`, or
  `*.egg-info/`.

## Install

From the repository root:

```bash
python3 -m pip install -e .
```

If `mt` installs into the Python user bin but the shell cannot find it, either
add that bin directory to `PATH` or link it into an existing PATH directory.
