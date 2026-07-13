# Adaptive Portrait Subject Lift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reviewed per-image portrait workflow that converts each eligible HIF/HEIF/HEIC preview, records independently chosen Select Subject corrections, and safely writes those local corrections into Lightroom XMP.

**Architecture:** A focused `subject_lift` domain module owns discovery, TSV schema, validation, and Lightroom mask serialization. Two thin commands generate review artifacts and apply a reviewed plan. The Agent—not a fixed algorithm—opens every preview and fills the plan; Lightroom computes the actual Select Subject pixels after metadata is read.

**Tech Stack:** Python 3.9+, stdlib CSV/XML/pathlib/uuid, existing rawpy analysis, existing ffmpeg/sips HIF conversion, stdlib `unittest`.

## Global Constraints

- Process only `portrait/<number>/raw/` files rated 3–5 with matching HIF/HEIF/HEIC previews.
- Preserve global develop settings, ratings, non-owned XMP namespaces, and every correction not named `Media Toolkit Subject Lift`.
- Use per-image reviewed values; never derive one fixed adjustment for the batch.
- Face masks, background masks, root scenes, panoramas, archive/export, and deletion remain out of scope.
- Keep Python 3.9 compatibility and add no dependency.
- Use validate-all-then-write, atomic sidecar writes, dry-run, stale-rating checks, and idempotent replacement.
- Accepted slider ranges: Exposure `0.00..0.60`, Contrast `0..25`, Highlights `-40..10`, Shadows `-10..35`, Whites `-20..20`, Blacks `-25..10`.

---

### Task 1: Discover eligible portraits and generate review artifacts

**Files:**
- Create: `media_toolkit/subject_lift.py`
- Create: `media_toolkit/commands/subject_plan.py`
- Create: `tests/test_subject_plan.py`

**Interfaces:**
- Produces: `PortraitCandidate(raw_path: Path, preview_path: Path, rating: int)`.
- Produces: `discover_candidates(root: Path, rating_expression: str = ">=3") -> list[PortraitCandidate]`.
- Produces: `write_plan_template(output: Path, root: Path, candidates: list[PortraitCandidate], stats_by_path: dict[Path, RawStats]) -> None`.
- Consumes: `contact_sheet.require_ffmpeg()` and `contact_sheet.render_ffmpeg_input_image()` with `run_sips()` fallback.

- [ ] **Step 1: Write failing discovery tests**

Create numbered portrait groups containing 2-, 3-, 4-, and 5-star RAW/XMP pairs, matching `.HIF`, `.HEIF`, and `.HEIC` previews, plus root and panorama decoys. Assert only the three portrait candidates rated 3–5 are returned in numeric-group/name order and each resolves to its matching preview.

- [ ] **Step 2: Run discovery tests and verify RED**

Run: `python3 -m unittest tests.test_subject_plan -v`
Expected: import failure because `media_toolkit.subject_lift` does not exist.

- [ ] **Step 3: Implement candidate discovery**

Add the immutable candidate type, enumerate only `portrait/<digits>/raw`, read ratings with `rawpy_tools.read_xmp_rating_strict`, match previews case-insensitively by stem under the sibling `hif/`, and reject duplicate/missing previews with path-specific `ValueError` messages.

- [ ] **Step 4: Add failing command tests for previews and TSV**

Patch conversion and RAW analysis functions. Assert `subject_plan.main()` converts every eligible preview to `<preview-dir>/portrait-<group>-<stem>.jpg` and writes a TSV header containing:

```text
path\trating\tpreview\tp01\tp50\tp95\tp99\tp999\tclip_ratio\tshadow_ratio\taction\tsubject_exposure\tsubject_contrast\tsubject_highlights\tsubject_shadows\tsubject_whites\tsubject_blacks\trationale
```

Assert adjustment/action/rationale cells are blank and the command never writes XMP.

- [ ] **Step 5: Implement and verify review artifact generation**

Implement `mt subject-plan` argument parsing, absolute/relative output resolution, preview-directory creation, one-file conversion, raw-stat analysis, and template serialization. Run `python3 -m unittest tests.test_subject_plan -v`; expected all tests pass.

---

### Task 2: Parse and validate a complete reviewed plan

**Files:**
- Modify: `media_toolkit/subject_lift.py`
- Create: `tests/test_subject_apply.py`

**Interfaces:**
- Produces: `SubjectAdjustment(path, rating, action, exposure, contrast, highlights, shadows, whites, blacks, rationale)`.
- Produces: `read_reviewed_plan(plan_path: Path, root: Path) -> list[SubjectAdjustment]`.
- Produces: `validate_reviewed_plan(root: Path, adjustments: list[SubjectAdjustment], rating_expression: str = ">=3") -> list[tuple[PortraitCandidate, SubjectAdjustment]]`.

- [ ] **Step 1: Write failing plan-schema and coverage tests**

Test successful parsing of two different `apply` rows and one all-zero `skip` row. Add separate failures for duplicate paths, missing eligible path, extra root/panorama path, stale rating, blank rationale, nonnumeric values, out-of-range values, and nonzero `skip` values.

- [ ] **Step 2: Run validation tests and verify RED**

Run: `python3 -m unittest tests.test_subject_apply -v`
Expected: failures because the parser and validator do not exist.

- [ ] **Step 3: Implement strict parsing and validate-all coverage**

Use `csv.DictReader`, require the exact template columns, resolve paths below `root`, parse Lightroom-facing values, enforce the six ranges, compare the plan path set to `discover_candidates`, and return deterministic candidate/adjustment pairs only after every row is valid.

- [ ] **Step 4: Run validation tests and verify GREEN**

Run: `python3 -m unittest tests.test_subject_apply -v`
Expected: all parsing and coverage tests pass.

---

### Task 3: Write an owned Select Subject correction without damaging XMP

**Files:**
- Modify: `media_toolkit/subject_lift.py`
- Modify: `tests/test_subject_apply.py`

**Interfaces:**
- Produces: `write_subject_adjustment(raw_path: Path, adjustment: SubjectAdjustment, id_factory: Callable[[], str] = ...) -> None`.
- Uses existing `rawpy_tools._parse_xmp`, `_xmp_description`, and `_atomic_write_text` so packet wrappers, namespaces, and atomic semantics remain consistent.
- Owns only `rdf:Description[@crs:CorrectionName='Media Toolkit Subject Lift']` under `crs:MaskGroupBasedCorrections`.

- [ ] **Step 1: Write failing XMP preservation tests**

Start from sidecars containing rating/global fields, a custom namespace, and an unrelated correction. Apply two rows with different values and assert different `LocalExposure2012`/tone fields, `Mask/Image`, `MaskSubType="1"`, non-inverted mask, unique sync IDs, and preserved unrelated content.

- [ ] **Step 2: Write failing idempotence and skip tests**

Apply twice and assert one owned correction remains with the latest values. Apply `skip` and assert a prior owned correction is removed while unrelated masks remain.

- [ ] **Step 3: Run XMP tests and verify RED**

Run: `python3 -m unittest tests.test_subject_apply -v`
Expected: failures because mask serialization is not implemented.

- [ ] **Step 4: Implement minimal sanitized Select Subject XML**

Serialize one correction with Lightroom local fields, one nested `CorrectionMasks/rdf:Seq/rdf:li`, `What="Mask/Image"`, `MaskSubType="1"`, `MaskInverted="false"`, and fresh uppercase UUID hex identifiers. Convert Exposure directly to EV text and the five integer local tone sliders to signed normalized decimal values in one documented helper. Remove only the owned correction for replacement or `skip`; remove an empty mask group container.

- [ ] **Step 5: Run XMP tests and verify GREEN**

Run: `python3 -m unittest tests.test_subject_apply -v`
Expected: preservation, per-image difference, idempotence, and skip tests pass.

---

### Task 4: Add the dry-run/apply command and CLI registry entries

**Files:**
- Create: `media_toolkit/commands/subject_apply.py`
- Modify: `media_toolkit/command_registry.py`
- Modify: `tests/test_subject_apply.py`
- Modify: `tests/test_media_toolkit_cli.py`

**Interfaces:**
- Command: `mt subject-apply <photo-dir> --plan <reviewed.tsv> [--ratings ">=3"] [--dry-run]`.
- Registry: `subject-plan` options `--ratings`, `--output`, `--preview-dir`; `subject-apply` options `--plan`, `--ratings` and `supports_dry_run=True`.

- [ ] **Step 1: Write failing command and registry tests**

Assert dry-run reports each `apply`/`skip` without changing sidecars, real apply writes only after full validation, a malformed final row causes zero writes, and both commands resolve through `mt` without mistaking option values for the directory.

- [ ] **Step 2: Run command tests and verify RED**

Run: `python3 -m unittest tests.test_subject_apply tests.test_media_toolkit_cli -v`
Expected: missing command/registry failures.

- [ ] **Step 3: Implement commands and registry**

Keep command modules thin: resolve root/plan, read, validate, print deterministic actions, return `2` for plan errors and `1` for filesystem write errors, and call the writer only after validation succeeds.

- [ ] **Step 4: Run command tests and verify GREEN**

Run: `python3 -m unittest tests.test_subject_apply tests.test_media_toolkit_cli -v`
Expected: all focused tests pass.

---

### Task 5: Update Agent rating and portrait-edit workflow

**Files:**
- Modify: `skills/initial-cull/SKILL.md`
- Modify: `prompts/lightroom-raw-cull-and-rough-edit.md`
- Modify: `README.md`
- Modify: `tests/test_repository_skills.py`

**Interfaces:**
- Skill requires individual HEIF/HIF preview review and a complete reviewed plan for every eligible 3–5-star portrait.
- Skill retains strict 4/5 bars, broadens 3-star candidates, and removes the one-alternate limit.

- [ ] **Step 1: Add failing repository Skill contract tests**

Assert the Skill contains `mt subject-plan`, `mt subject-apply`, `Media Toolkit Subject Lift`, individual HIF/HEIF review, all 3–5-star portraits, strict 4/5 language, and meaningful-difference near-duplicate language. Assert the old `at most one 3-star alternate` wording is absent.

- [ ] **Step 2: Run Skill tests and verify RED**

Run: `python3 -m unittest tests.test_repository_skills -v`
Expected: failures against the old rating and edit workflow.

- [ ] **Step 3: Update Skill, prompt, and README**

Document plan generation, mandatory Agent per-preview review, reviewed TSV creation, dry-run/apply, Lightroom Read Metadata plus Update All, and the fact that Lightroom—not Media Toolkit—computes mask pixels. Keep final archive separate.

- [ ] **Step 4: Verify Skill GREEN and validate package**

Run:

```bash
python3 -m unittest tests.test_repository_skills -v
/tmp/media-toolkit-verify-venv/bin/python /Users/zintrulcre/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/initial-cull
```

Expected: tests pass and validator prints `Skill is valid!`.

---

### Task 6: Full verification, commit, and push

**Files:** all files above plus this plan.

- [ ] **Step 1: Run full verification**

```bash
python3 -m unittest discover -s tests
/usr/bin/python3 -m unittest discover -s tests
sh scripts/install-codex-skills.sh --check
git diff --check
```

Expected: both suites pass, all four Skill links are current, and diff check is clean.

- [ ] **Step 2: Review privacy and scope**

Run `rg -n "/Users/|MaskValue|MaskDigest|人像-青橙|kosnio" media_toolkit skills README.md prompts tests`. Expected: no local preset names, paths, image-derived payloads, or personal data in shipped files; test fixtures may contain only synthetic identifiers.

- [ ] **Step 3: Commit and push current main**

```bash
git add docs/superpowers/plans/2026-07-13-adaptive-portrait-subject-lift.md media_toolkit tests skills/initial-cull/SKILL.md prompts/lightroom-raw-cull-and-rough-edit.md README.md
git commit -m "新增逐图人像主体提亮"
git push origin main
```

- [ ] **Step 4: Verify remote state**

Run `git status --short`, `git rev-parse HEAD`, and `git ls-remote origin refs/heads/main`. Expected: clean status and matching local/remote SHA.
