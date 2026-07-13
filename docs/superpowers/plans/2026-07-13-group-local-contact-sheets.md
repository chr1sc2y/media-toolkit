# Group-Local Contact Sheets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate portrait and panorama contact sheets inside each numbered group instead of combining groups into parent-level overviews.

**Architecture:** Keep the generic `mt contact-sheet` command unchanged. Change `group_organize.rebuild_contact_sheets` to enumerate numbered groups and invoke the existing command once per group; then make strict cull verification derive its allowed paths from those groups. Update the repository Skill and operator docs to the same output contract.

**Tech Stack:** Python 3.9+, stdlib `unittest`, pathlib, existing `mt contact-sheet` CLI.

## Global Constraints

- Preserve `<photo-dir>/_contact_sheet.jpg` for ordinary root HIF files.
- Generate `portrait/<number>/_contact_sheet.jpg` and `panorama/<number>/_contact_sheet.jpg` in numeric group order.
- Do not generate or retain `portrait/_contact_sheet.jpg` or `panorama/_contact_sheet.jpg` after successful replacements.
- Do not change RAW, HIF, XMP, Export, rating, grouping, or archive behavior.
- Keep `mt contact-sheet --section-by-numbered-dir` available for compatibility.

---

### Task 1: Generate one overview per numbered group

**Files:**
- Modify: `tests/test_portrait_organize.py`
- Modify: `tests/test_panorama_organize.py`
- Modify: `media_toolkit/group_organize.py`

**Interfaces:**
- Consumes: `rebuild_contact_sheets(root: Path, group_kind: str, section_prefix: str, runner=run_command) -> None`.
- Produces: deterministic root plus group-local `mt contact-sheet` command sequence; removes the legacy aggregate only after all runner calls succeed.

- [ ] **Step 1: Write failing portrait and panorama command-plan tests**

Create two numbered groups, add a legacy parent overview, capture runner calls,
and assert commands target each group directly:

```python
self.assertEqual(len(commands), 3)
self.assertIn(str(root / "portrait/1"), commands[1])
self.assertIn(str(root / "portrait/1/_contact_sheet.jpg"), commands[1])
self.assertIn(str(root / "portrait/2"), commands[2])
self.assertIn(str(root / "portrait/2/_contact_sheet.jpg"), commands[2])
self.assertNotIn("--section-by-numbered-dir", commands[1])
self.assertFalse((root / "portrait/_contact_sheet.jpg").exists())
```

For panorama, assert the corresponding exact paths:

```python
self.assertIn(str(root / "panorama/1"), commands[1])
self.assertIn(str(root / "panorama/1/_contact_sheet.jpg"), commands[1])
self.assertIn(str(root / "panorama/2"), commands[2])
self.assertIn(str(root / "panorama/2/_contact_sheet.jpg"), commands[2])
self.assertFalse((root / "panorama/_contact_sheet.jpg").exists())
```

Add a runner that raises on the second group and assert the legacy parent
overview still exists.

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_portrait_organize tests.test_panorama_organize -v
```

Expected: failures because the implementation still emits one parent-level
sectioned command and removes no legacy aggregate.

- [ ] **Step 3: Implement deterministic group-local generation**

Add a small helper and replace the aggregate runner call:

```python
def numbered_group_dirs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        (path for path in directory.iterdir() if path.is_dir() and path.name.isdigit()),
        key=lambda path: int(path.name),
    )

for numbered_dir in numbered_group_dirs(group_dir):
    runner([
        "mt", "contact-sheet", str(numbered_dir), "--hif-only",
        "--output", str(temp_dir / group_kind / numbered_dir.name),
        "--final-overview", str(numbered_dir / "_contact_sheet.jpg"),
    ])

legacy_overview = group_dir / "_contact_sheet.jpg"
if legacy_overview.exists():
    legacy_overview.unlink()
```

The unlink remains after the complete loop so any runner failure preserves the
legacy file.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run the command from Step 2. Expected: all portrait and panorama organizer tests pass.

---

### Task 2: Verify the per-group output contract

**Files:**
- Modify: `tests/test_verify_cull.py`
- Modify: `media_toolkit/commands/verify_cull.py`

**Interfaces:**
- Consumes: `numbered_children(directory: Path) -> list[Path]`.
- Produces: `allowed_contact_sheet(path: Path) -> bool` and per-group missing-sheet issues.

- [ ] **Step 1: Rewrite verification fixtures and add failing regressions**

Change the passing fixture to create:

```python
(root / "portrait/1/_contact_sheet.jpg").write_text("sheet", encoding="utf-8")
(root / "panorama/1/_contact_sheet.jpg").write_text("sheet", encoding="utf-8")
```

Assert a missing portrait group reports
`missing portrait/1/_contact_sheet.jpg`. Add a second portrait group to prove
each group is required. Add legacy parent sheets and assert both are reported as
redundant.

- [ ] **Step 2: Run verification tests and verify RED**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_verify_cull -v
```

Expected: failures because verification still requires and allows parent-level sheets.

- [ ] **Step 3: Implement dynamic allowed paths and group checks**

Keep the static set root-only and add the exact path predicate:

```python
ALLOWED_CONTACT_SHEETS = {Path("_contact_sheet.jpg")}

def allowed_contact_sheet(path: Path) -> bool:
    if path in ALLOWED_CONTACT_SHEETS:
        return True
    parts = path.parts
    return (
        len(parts) == 3
        and parts[0] in {"portrait", "panorama"}
        and parts[1].isdigit()
        and parts[2] == "_contact_sheet.jpg"
    )
```

Require sheets per eligible child and use the predicate during redundant-file
inspection:

```python
for kind in ("portrait", "panorama"):
    for child in numbered_children(root / kind):
        if (child / "hif").is_dir() and not (child / "_contact_sheet.jpg").is_file():
            report.issues.append(
                f"missing {child.relative_to(root)}/_contact_sheet.jpg"
            )

for path in sorted(root.rglob("*contact_sheet*.jpg")):
    rel = path.relative_to(root)
    if not allowed_contact_sheet(rel):
        report.issues.append(f"redundant contact sheet remains: {rel}")
```

- [ ] **Step 4: Run verification tests and verify GREEN**

Run the command from Step 2. Expected: all verification tests pass.

---

### Task 3: Align the repository Skill and operator documentation

**Files:**
- Modify: `skills/initial-cull/SKILL.md`
- Modify: `prompts/lightroom-raw-cull-and-rough-edit.md`
- Modify: `README.md`
- Modify: `tests/test_repository_skills.py`

**Interfaces:**
- Consumes: the output paths implemented in Tasks 1–2.
- Produces: one documented command template per `<group>` and a regression preventing parent-level paths from returning.

- [ ] **Step 1: Add a failing Skill contract test**

Assert the Skill contains both group-local final paths and excludes the old
aggregate paths:

```python
self.assertIn('portrait/<group>/_contact_sheet.jpg', text)
self.assertIn('panorama/<group>/_contact_sheet.jpg', text)
self.assertNotIn('portrait/_contact_sheet.jpg', text)
self.assertNotIn('panorama/_contact_sheet.jpg', text)
```

- [ ] **Step 2: Run the Skill test and verify RED**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_repository_skills -v
```

Expected: failure because the Skill still documents parent-level overviews.

- [ ] **Step 3: Update commands and prose**

Document manual regeneration as:

```bash
mt contact-sheet "<photo-dir>/portrait/<group>" --hif-only --output "/tmp/mt-portrait-<group>-sheet" --final-overview "<photo-dir>/portrait/<group>/_contact_sheet.jpg"
mt contact-sheet "<photo-dir>/panorama/<group>" --hif-only --output "/tmp/mt-panorama-<group>-sheet" --final-overview "<photo-dir>/panorama/<group>/_contact_sheet.jpg"
```

State that the commands repeat for every numbered group and that the organizer
performs this rebuild automatically.

- [ ] **Step 4: Run the Skill test and official validator**

Run:

```bash
/usr/bin/python3 -m unittest tests.test_repository_skills -v
/tmp/media-toolkit-verify-venv/bin/python /Users/zintrulcre/.codex/skills/.system/skill-creator/scripts/quick_validate.py skills/initial-cull
```

Expected: tests pass and validator prints `Skill is valid!`.

---

### Task 4: Final verification, commit, and push

**Files:**
- All files changed by Tasks 1–3.

**Interfaces:**
- Produces: verified commit on `main`, pushed to `origin/main`.

- [ ] **Step 1: Run full verification**

```bash
python3 -m unittest discover -s tests
/usr/bin/python3 -m unittest discover -s tests
sh scripts/install-codex-skills.sh --check
git diff --check
```

Expected: both Python suites pass, four Skill links are current, and diff check is clean.

- [ ] **Step 2: Review scope and commit**

```bash
git status --short
git diff --stat
git add media_toolkit/group_organize.py media_toolkit/commands/verify_cull.py \
  tests/test_portrait_organize.py tests/test_panorama_organize.py \
  tests/test_verify_cull.py tests/test_repository_skills.py \
  skills/initial-cull/SKILL.md prompts/lightroom-raw-cull-and-rough-edit.md \
  README.md docs/superpowers/plans/2026-07-13-group-local-contact-sheets.md
git commit -m "按分组生成接触表"
```

- [ ] **Step 3: Push and verify the remote commit**

```bash
git push origin main
git fetch origin
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)"
```

Expected: push succeeds and local/remote SHAs match.
