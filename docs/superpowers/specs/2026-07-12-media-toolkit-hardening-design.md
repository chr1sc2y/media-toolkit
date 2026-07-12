# Media Toolkit Safety, Portability, and Skill Hardening Design

## Goal

Make `media-toolkit` safe enough to run unattended on the owner's photo archive,
portable across machines, and self-consistent across its CLI, skills, tests, and
packaging. The repository remains a reusable media tool and must contain no
private Vault, Ledger, or personal spending source data, regardless of GitHub
visibility.

## Decisions

### Repository privacy and history

- Keep the GitHub repository private because it is a single-user operational
  tool and its workflows expose personal conventions even after source data is
  removed.
- Treat privacy as a content boundary, not as a substitute for data hygiene.
  Ledger, Vault, trip-spending, and other personal source data do not belong in
  the repository.
- Add a checkout-level privacy regression test for known forbidden paths and
  markers. It is a guardrail, not a general secret scanner.
- Rewrite the reachable branch history to remove accidentally committed private
  files. Document that GitHub may retain unreachable objects temporarily; a
  GitHub Support purge is the only supported way to guarantee immediate removal
  from GitHub's object cache without deleting and recreating the repository.

### Non-destructive XMP updates

- XMP writes update only fields owned by a command and preserve all unrelated
  XML elements and attributes, including Lightroom crop, perspective, masks,
  labels, and third-party metadata.
- Write through a temporary file and atomically replace the sidecar.
- Add a manifest-driven rating command so the initial-cull workflow can create
  the ratings that its later stages consume.
- `verify-cull` validates sidecar presence, rating range, and required workflow
  markers by default; an explicit compatibility flag may relax the check.
- Lightroom application consumes a reviewable plan when supplied. Claims in
  skills and help text are limited to behavior actually implemented.

### Archive completeness and boundaries

- Validate the destination against the user-supplied source root before any
  recursive scene discovery. A destination inside the source is always invalid.
- Never treat directories beneath `panorama/` as independent finalization roots.
- Accept `.hif`, `.heif`, and `.heic` case-insensitively.
- Flattened-name collisions are safe only when contents are byte-identical. A
  different file with the same destination name is a hard error.
- Any missing exported stem makes finalization incomplete and returns failure,
  even when other files copied successfully.
- HIF pruning is plan-first. Deletion requires an explicit aggressive mode and
  confirmation flag; skills never infer permission for destructive cleanup from
  a finalization request.
- Real HEIF inspection uses an installed Pillow HEIF decoder. Decoder absence is
  reported by self-check and blocks destructive image-based pruning.

### Style learning

- Recursively discover valid scene roots while excluding generated work output.
- Prefer Pixcake exports over same-stem direct exports and analyze each logical
  image once.
- Summaries include sample counts, value frequencies, numeric median/range, and
  deviations from the selected baseline for supported develop fields actually
  present in sample XMP. Omitted fields are not inferred. Rating-only sidecars
  are not counted as style samples.
- The repository skill keeps the stable machine name `learn-color-style`; broad
  natural-language triggers remain in the description without renaming the
  skill to a generic word.

### Repository-owned skills

- The canonical copies of `initial-cull`, `extract-feature`,
  `learn-color-style`, and `apple-photos-location-fill` live under `skills/`.
- Skills contain exact executable commands with explicit target paths and
  confirmation gates. They point to CLI help and repository references instead
  of duplicating long algorithmic rules.
- A manifest enumerates installable skills. The installer preflights the whole
  operation, never replaces a real directory, updates only repository-managed
  symlinks, supports `--check`, and avoids partial installs.

### Packaging, self-check, and CI

- Build metadata includes every runtime JSON resource and supports isolated wheel
  installation.
- Installation documentation uses a virtual environment or `pipx`, not mutation
  of an externally managed Homebrew Python.
- Self-check covers package resources, RAW support, FFmpeg, HEIF decoding, and
  repository skill registration where relevant, with required versus optional
  capabilities reported separately.
- CI runs the unit suite and an isolated wheel smoke test.

## Compatibility

- Keep Python 3.9 compatibility.
- Preserve existing command names and add flags or commands rather than silently
  changing unrelated workflows.
- Destructive behavior becomes more explicit; callers that relied on implicit
  aggressive pruning must opt in.
- Existing XMP files remain valid and gain no schema migration.

## Acceptance Criteria

1. Regression tests reproduce and prevent XMP metadata loss, recursive
   destination escape, panorama HIF inclusion, same-name data loss, incomplete
   archive success, and style-learning deduplication errors.
2. A clean initial-cull path can apply a reviewed ratings manifest and pass
   strict verification.
3. All four skills install from a cloned repository and pass metadata/command
   checks without username-specific paths.
4. An isolated wheel can run `mt styles` and `mt self-check` without missing
   packaged resources.
5. The full unit suite, focused command smoke tests, and repository privacy scan
   pass before commit and push.
