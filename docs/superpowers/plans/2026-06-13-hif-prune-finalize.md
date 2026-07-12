# HIF Prune Finalize Implementation Plan

> **Superseded (2026-07-12):** Historical implementation record only. The
> current plan is `docs/superpowers/plans/2026-07-12-media-toolkit-hardening.md`.
> Any statement below about default or automatic aggressive deletion is no
> longer valid; current behavior is plan → review → apply that exact plan with
> `--confirm-delete`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dedicated `mt hif-prune` command and wire it into the agent-facing finalized archive workflow.

**Architecture (superseded):** Implement reusable pruning logic in
`media_toolkit/hif_prune.py`, expose it through
`media_toolkit.commands.hif_prune`, and register it in the command registry.
The current command defaults to planning; deletion requires
`--mode aggressive --apply-plan <reviewed.json> --confirm-delete`.

**Tech Stack:** Python standard library, Pillow for testable image similarity, existing `mt` command registry and unittest suite.

---

### Task 1: Prune Planning Tests

**Files:**
- Create: `tests/test_hif_prune.py`
- Create: `media_toolkit/hif_prune.py`

- [x] **Step 1: Write failing tests**

Write tests that create JPEG-encoded `.HIF` fixtures and assert that exported stems, RAW-backed stems, and panorama stems are kept while duplicate HIF-only frames are selected for deletion.

- [x] **Step 2: Verify failure**

Run: `python3 -m unittest tests.test_hif_prune`

Expected: import failure for `media_toolkit.hif_prune`.

- [x] **Step 3: Implement prune planner**

Add a planner that scans HIF directories, detects protected stems, computes small perceptual hashes for decodable images, groups adjacent filename-neighbor HIF-only files, and marks high-similarity repeats for deletion.

- [x] **Step 4: Verify planner tests pass**

Run: `python3 -m unittest tests.test_hif_prune`

Expected: all tests pass.

### Task 2: Command and Registry

**Files:**
- Create: `media_toolkit/commands/hif_prune.py`
- Create: `scripts/hif_prune.py`
- Modify: `media_toolkit/command_registry.py`
- Modify: `media_toolkit/cli.py`
- Modify: `tests/test_command_registry.py`
- Modify: `tests/test_media_toolkit_cli.py`

- [x] **Step 1: Write failing command tests**

Assert `resolve_command("hif-prune")` resolves to the new script, command metadata includes delete/write-manifest side effects, and value options do not count as directory arguments.

- [x] **Step 2: Verify failure**

Run command registry and CLI tests.

- [x] **Step 3: Implement command wrapper**

Add CLI parsing for `--mode`, `--scene`, `--manifest`, and `--dry-run`. Current
behavior defaults to plan mode and requires `--apply-plan` plus
`--confirm-delete` for aggressive mode.

- [x] **Step 4: Verify command tests pass**

Run command registry and CLI tests again.

### Task 3: Workflow and Agent Instructions

**Files:**
- Modify: `media_toolkit/workflows.json`
- Modify: `prompts/lightroom-raw-cull-and-rough-edit.md`
- Modify: `docs/agent-workflows.md`
- Modify: `tests/test_workflows.py`

- [x] **Step 1: Write failing workflow test**

Assert finalize workflow text says HIF cleanup is separately requested and
starts with a non-destructive plan.

- [x] **Step 2: Update workflow registry and docs**

Document the three-step finalized archive chain and the hard keep rules.

- [x] **Step 3: Verify workflow test passes**

Run: `python3 -m unittest tests.test_workflows`

Expected: all tests pass.

### Task 4: Full Verification

**Files:**
- All changed files

- [x] **Step 1: Run full suite**

Run: `python3 -m unittest discover -s tests`

Expected: all tests pass.
