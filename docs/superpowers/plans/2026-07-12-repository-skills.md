# Repository-Owned Photography Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Version and install the three photography skills directly from `media-toolkit`.

**Architecture:** Complete skill directories live under `skills/`. A small POSIX shell installer derives the repository root from its own path and registers symlinks in `${CODEX_HOME:-$HOME/.codex}/skills` without overwriting real directories.

**Tech Stack:** Markdown, YAML, POSIX shell, Python stdlib `unittest`.

## Global Constraints

- Preserve all existing user changes in the current branch and include them in the requested commit.
- Do not depend on a specific macOS username or absolute repository checkout path.
- Do not overwrite existing non-symlink skill directories.

---

### Task 1: Specify installer behavior

**Files:**
- Create: `tests/test_install_codex_skills.py`
- Create: `scripts/install-codex-skills.sh`

- [ ] Write tests for link creation and non-symlink preservation.
- [ ] Run the focused test and confirm it fails because the installer is absent.
- [ ] Implement the minimal installer.
- [ ] Re-run the focused test and confirm it passes.

### Task 2: Move skills into the repository

**Files:**
- Create: `skills/initial-cull/**`
- Create: `skills/extract-feature/**`
- Create: `skills/learn-color-style/**`

- [ ] Copy the current skill sources into the repository through patches.
- [ ] Replace hard-coded repository paths with portable repository discovery guidance.
- [ ] Validate required metadata and confirm no old absolute path remains.

### Task 3: Document and activate

**Files:**
- Modify: `README.md`
- Replace local skill directories with symlinks after exact content comparison.

- [ ] Document installation on a cloned checkout.
- [ ] Run the installer and verify all local links resolve into this repository.
- [ ] Run focused and full tests.
- [ ] Review the complete diff, commit all authorized current-branch changes, and push `main`.

