# Media Toolkit Hardening Implementation Plan

> **For agentic workers:** Use `superpowers:test-driven-development` for every
> behavior change and `superpowers:verification-before-completion` before the
> final commit.

**Goal:** Close the audited safety, functionality, skill-portability, and
distribution gaps in `media-toolkit`.

**Architecture:** Keep command modules thin, put reusable behavior in
`media_toolkit/`, keep repository-owned skills under `skills/`, and make tests
the executable contract for all destructive or metadata-writing behavior.

**Tech stack:** Python 3.9+, stdlib `unittest`, Pillow/rawpy, POSIX shell, GitHub
Actions.

## Task 1: Preserve XMP and close the rating workflow

**Files:** `media_toolkit/rawpy_tools.py`, rating/LR/verification command modules,
`media_toolkit/workflows.json`, and focused tests.

- Add failing tests showing that crop, perspective, masks, labels, and custom XMP
  survive Lightroom updates.
- Implement field-scoped, atomic XMP merge behavior.
- Add a TSV ratings-manifest command and validation tests.
- Make cull verification strict by default and test missing/invalid ratings and
  missing workflow markers.
- Make `lr-apply` consume an explicitly supplied reviewed plan and remove claims
  that are not represented in the plan or implementation.

## Task 2: Make finalization complete and collision-safe

**Files:** finalization command/workflow/archive/prune modules and focused tests.

- Reproduce destination-inside-root acceptance, panorama-root discovery,
  different-content filename collision, missing-stem success, and HEIF extension
  rejection in tests.
- Enforce source-root boundaries before recursion.
- Exclude panorama descendants from scene roots.
- Compare contents for destination collisions and fail on differences.
- Fail incomplete archives and accept HIF/HEIF/HEIC.
- Require explicit confirmation for aggressive prune; verify decoder availability
  before image-based deletion.

## Task 3: Make style learning match its contract

**Files:** `media_toolkit/style_learning.py`, command output, profile schema, and
focused tests.

- Add fixtures for recursive scenes, Pixcake/direct duplicates, rating-only XMP,
  numeric distributions, and observed-field baseline deviations.
- Expand supported field discovery and typed aggregation.
- Emit deterministic counts, frequencies, medians, ranges, and deviations.
- Keep JSON output stable and human-readable.

## Task 4: Converge and migrate repository skills

**Files:** all `skills/*/SKILL.md`, skill metadata, Apple Photos location skill,
workflow references, and skill-validation tests.

- Rewrite the three existing skills around exact runnable commands, real behavior,
  and explicit safety gates.
- Migrate `apple-photos-location-fill` into the repository without absolute
  checkout paths.
- Keep folder/frontmatter names stable and narrow overly broad triggers.
- Validate command examples against CLI parsing and ensure no private-machine path
  remains.

## Task 5: Make installation transactional and portable

**Files:** `skills/manifest.json`, installer scripts, README, and installer tests.

- Add a manifest containing all four skills.
- Preflight every destination before changing any symlink.
- Support `--check`; reject real directories and unrelated links; update only
  repository-managed links.
- Test clean install, idempotence, failure without partial state, and check mode.
- Register this checkout locally after tests pass.

## Task 6: Harden packaging, self-check, CI, and privacy

**Files:** build metadata, self-check modules/tests, `.github/workflows/`, README,
`.gitignore`, and privacy tests.

- Package `workflows.json` and `style_profiles.json` and smoke-test an isolated
  wheel.
- Document venv/pipx installation.
- Expand self-check capability reporting without making optional tools fatal.
- Add CI for the full unit suite and wheel smoke test.
- Add a test preventing known Vault/Ledger/travel-spending source paths or markers
  from entering the tracked repository.

## Task 7: Integrate and publish

- Run focused tests after each task and the complete suite at the end.
- Run skill metadata validation, command-example smoke tests, build/wheel smoke,
  privacy scan, and `git diff --check`.
- Review the final diff for safety and scope.
- Commit all authorized changes on `main` and push to `origin/main`.
- Recheck repository visibility, reachable history, and the old GitHub SHA; report
  any server-side unreachable-object retention separately.
