# Apple Photos Location Fill Design

> **Updated by the 2026-07-12 hardening design:** The workflow remains
> time-based, but plan parsing and apply are now strict, auditable operations.
> The canonical Skill lives in this repository rather than a machine-local
> directory.

## Goal

Split Apple Photos missing-location repair into an auditable two-stage workflow:
first scan and plan, then apply a reviewed plan without rescanning Photos.

## Design

`mt fill-locations` remains the command entrypoint. Its default mode scans Apple
Photos, builds a two-pass timeline plan, writes one compact HTML run-log table
for review, and also writes a machine-readable JSON plan under
`work/photos-location-fill/`.

The planner computes the nearest previous located item and nearest next located
item for every missing-location item. It chooses the candidate with the smaller
time delta when both exist, marks skipped rows when neither candidate exists,
and keeps previous/next deltas plus notes in the plan for audit. Source
selection is not gated by a time threshold; unusually distant matches are
handled by reviewing the dry-run plan before applying it.

`mt fill-locations --apply-plan <path>` is the write stage. It reads the reviewed
JSON plan and writes only planned rows with latitude and longitude. It does not
refresh or reuse the Photos timeline cache, and it does not rebuild candidate
choices.

The first version remains time-based. Visual similarity can be added later by
exporting temporary thumbnails and adding similarity scores to the same plan
schema.

## Skill

Store `apple-photos-location-fill` under
`skills/apple-photos-location-fill/` and register it with the repository's
manifest-driven installer. The skill directs future agents to run the plan
stage first, ask the user to review the outputs, and only use `--apply-plan`
after explicit confirmation.

## Validation

Add unit tests for previous/next two-pass selection, JSON plan write/read, and
apply-from-plan behavior. Run `python3 -m unittest discover -s tests`.
