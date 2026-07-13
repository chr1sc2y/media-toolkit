# Adaptive Portrait Subject Lift Design

## Goal

Extend the initial-cull portrait workflow so every rated portrait candidate is
reviewed from its own HIF/HEIF/HEIC preview and receives an independent,
reviewable Select Subject adjustment plan. Lightroom remains responsible for
computing the AI subject pixels; Media Toolkit decides and writes different
local correction values for each image.

This feature must not turn into a fixed preset. A photo whose subject is already
well exposed may explicitly receive `skip`, while a backlit or low-contrast
subject may receive a stronger but still restrained lift.

## Scope

- Eligible files are RAW files under `portrait/<number>/raw/` with an XMP rating
  of 3, 4, or 5 and a matching HIF, HEIF, or HEIC preview.
- Every eligible file must appear exactly once in the reviewed subject plan.
- Ratings 3, 4, and 5 receive the complete existing portrait editing workflow;
  the subject correction is an additional local layer and does not replace the
  existing global portrait treatment.
- Ratings 0, 1, and 2 are not processed by this feature.
- Ordinary root scenes and panorama source frames are out of scope.
- Face-specific masks remain out of scope. The user will refine faces manually.
- No background-darkening mask is added.

## Revised Rating Policy

The Agent remains the visual rater. The Skill and detailed prompt define the
judgment policy; the CLI validates and writes the reviewed result but does not
pretend to classify artistic quality by a fixed formula.

- **5 stars:** exceptional, rare frames with outstanding expression, moment,
  composition, focus, and clear final-image value.
- **4 stars:** clearly strong frames that already meet a high final-image bar.
- **3 stars:** a deliberately broad review pool: plausible alternatives,
  uncertain or intermediate frames, images whose value may emerge after the
  Lightroom treatment, and near-duplicates with meaningful differences.
- **0–2 stars:** clear technical failures, clearly poor expressions, or repeats
  with no useful comparative difference.

There is no fixed one-alternate limit for near-duplicates. Multiple 3-star
candidates are allowed when expression, pose, sharpness, framing, or timing
provides a meaningful comparison. Four and five stars must not expand merely
because the 3-star pool expands.

## Workflow

### 1. Build review inputs

A new plan-template command enumerates eligible portraits in deterministic
numeric-group and filename order. It validates RAW/HIF pairing and produces:

- individual temporary JPEG review previews converted from the matching
  HIF/HEIF/HEIC files;
- RAW histogram evidence already supported by `rawpy_tools`;
- a TSV template with one row per eligible RAW.

The temporary review directory is outside the shoot directory and is disposable.
The command never substitutes an embedded RAW rendering for the HIF preview.

### 2. Agent reviews every image

The Agent opens every individual preview, not just the contact sheet, and uses
the RAW statistics only as supporting exposure/headroom evidence. For each row
the Agent records either `apply` or `skip` plus:

- `subject_exposure`
- `subject_contrast`
- `subject_highlights`
- `subject_shadows`
- `subject_whites`
- `subject_blacks`
- `rationale`

Values are decided independently per image. The Agent considers subject versus
background brightness, highlight risk on skin or pale clothing, blocked dark
clothing, current scene contrast, and whether lifting would make the subject
look flat. Global RAW statistics alone may not determine the values.

The intended look is a modest subject separation that preserves the user's
preferred contrast. Raising Shadows heavily by default is forbidden. Contrast
and the black anchor may be retained or strengthened when the lift would
otherwise flatten the subject.

### 3. Review and apply safely

`mt subject-apply` accepts only a reviewed TSV. It supports `--dry-run`, checks
that every current eligible file appears exactly once, rejects duplicate or
unexpected paths, verifies ratings have not changed, and rejects missing
rationales or out-of-range Lightroom values.

Safety bounds constrain mistakes but do not choose the adjustment. Accepted
Lightroom-facing ranges are Exposure `0.00..0.60` EV, Contrast `0..25`,
Highlights `-40..10`, Shadows `-10..35`, Whites `-20..20`, and Blacks
`-25..10`. The exact value within a range comes from the per-image review.
`skip` rows must contain zero in all six adjustment columns.

For an `apply` row, the command adds or replaces exactly one named correction:
`Media Toolkit Subject Lift`. It creates a Lightroom AI image mask recipe with
`MaskSubType="1"` (Select Subject), unique synchronization identifiers, and the
row's local correction values. It preserves ratings, global develop settings,
unrelated XMP namespaces, and all masks not owned by Media Toolkit. Reapplying
the same plan is idempotent.

The repository already has a local Lightroom preset proving the Select Subject
recipe structure (`Mask/Image`, `MaskSubType="1"`). The implementation must use
only a minimal sanitized recipe; it must not copy unrelated preset settings,
names, identifiers, or image-derived mask payloads into this public repository.

### 4. Lightroom computes the pixels

After the sidecars are written, the user reads metadata from files in Lightroom
Classic. Lightroom computes the Select Subject masks for the actual images. If
any AI mask is pending, the user runs Update All. Media Toolkit cannot and must
not claim that its XML writer performed Lightroom's pixel segmentation.

The handoff reports applied and skipped rows, per-image values, and any images
whose Lightroom-generated subject selection still needs visual correction.

## Interfaces

The public workflow has two distinct operations:

1. `mt subject-plan <photo-dir> --ratings ">=3" --output subject_plan.tsv
   --preview-dir <temporary-dir>` generates deterministic preview, evidence,
   and template artifacts without changing XMP.
2. `mt subject-apply <photo-dir> --plan subject_plan_reviewed.tsv --dry-run`,
   followed by the same command without `--dry-run`, validates and applies one
   reviewed per-image plan.

The reviewed TSV is retained as audit evidence until Lightroom verification is
complete. Generated previews and raw-stat artifacts may then be removed.

## XMP Ownership And Failure Handling

- The tool owns only the correction named `Media Toolkit Subject Lift` and its
  directly nested Select Subject mask recipe.
- Existing masks and corrections are never globally replaced.
- XML is written atomically using the existing sidecar machinery.
- Any parse, schema, stale-rating, missing-preview, or eligibility error aborts
  before the first write.
- Application uses a validate-all-then-write pass. A mid-write filesystem error
  is reported with the affected path; already-written sidecars remain valid and
  rerunning the same plan safely converges because the operation is idempotent.
- Plan values use Lightroom-facing slider units in the TSV. Serialization into
  Camera Raw local-correction values is centralized and covered by tests.

## Verification

Automated tests cover:

- deterministic discovery of only rated 3–5 numbered-group portraits;
- matching HIF/HEIF/HEIC preview requirements;
- rejection of missing, duplicate, stale, or out-of-scope plan rows;
- `skip` semantics;
- different rows producing different local corrections;
- preservation of existing global fields and unrelated masks;
- idempotent replacement of only the owned correction;
- valid Select Subject XMP structure and unique synchronization IDs;
- dry-run behavior and atomic writes;
- revised Skill rating language and removal of the one-alternate rule.

Before broad use, one safe portrait sidecar must be loaded into Lightroom
Classic as an integration smoke test. Success means Lightroom recognizes the
named correction, computes the subject mask after Read Metadata/Update All, and
shows the planned local values without altering unrelated edits.

## Non-Goals

- Running a separate subject-segmentation model in Media Toolkit.
- Automatically identifying or correcting faces.
- Fixed low/medium/high presets or a single adjustment shared by all images.
- Changing the existing global portrait look.
- Final archive, export, deletion, or Apple Photos import.
