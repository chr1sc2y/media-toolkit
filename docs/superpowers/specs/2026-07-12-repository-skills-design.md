# Repository-Owned Photography Skills Design

## Goal

Make `media-toolkit` the canonical, version-controlled source for the
`initial-cull`, `extract-feature`, `learn-color-style`, and
`apple-photos-location-fill` Codex skills so a new machine can acquire the
workflows from the repository.

## Design

- Store each complete skill under `skills/<skill-name>/`, including `SKILL.md` and `agents/openai.yaml`.
- Remove machine-specific `/Users/zintrulcre/...` paths from the skill instructions. Skills use the `mt` command first and resolve repository resources relative to their own repository-owned location when needed.
- Add a manifest-driven `scripts/install-codex-skills.sh` entrypoint. It
  discovers the repository root from its own location and creates links beneath
  `${CODEX_HOME:-$HOME/.codex}/skills`.
- Preflight every manifest entry before creating any link. Refuse to overwrite
  an existing non-symlink directory or unrelated symlink so installation cannot
  silently lose local edits or stop halfway through the set.
- Document the clone, editable package install, skill registration, and Codex restart steps in the repository README.

## Verification

- An isolated temporary `HOME` test verifies that all four links resolve to
  repository-owned skill directories.
- A second test verifies that an existing non-symlink destination is preserved and installation fails clearly.
- Skill metadata and repository-path portability are checked directly.
- Run the full repository unit test suite before committing and pushing.
