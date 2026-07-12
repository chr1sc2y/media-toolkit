---
name: apple-photos-location-fill
description: Audit and repair missing geolocation in Apple Photos using media-toolkit. Use when the user asks to review Apple Photos for photos or videos without location data, generate a dry-run location-fill plan, compare previous and next timestamp neighbors, or apply an explicitly reviewed geolocation plan back to Photos.
---

# Apple Photos Location Fill

Use `mt fill-locations`. Keep planning and writing as two separate,
user-visible stages. Never write locations directly through AppleScript while
this command is available.

## 1. Create a review plan

For the full library:

```bash
mt fill-locations --force-refresh
```

For a bounded date range:

```bash
mt fill-locations --start 2026-06-01 --end 2026-06-07 --force-refresh
```

`--start` is inclusive and `--end` is exclusive. They filter rows in the
generated plan only; they do not shorten the full Photos library scan. Use
`--scan-start` when a lower-bounded incremental scan is intended.

For an incremental scan after a known completion point:

```bash
mt fill-locations --scan-start "2026-04-30 00:00:00" --force-refresh
```

Review these generated artifacts:

- `outputs/photos_location_fill_plan.html`
- `work/photos-location-fill/photos_location_fill_plan.json`
- `work/photos-location-fill/run_history.json`

Record the printed `Plan SHA-256` and bind approval to that exact JSON digest.

Report the latest run's planned count, warnings, source-location read errors,
and largest chosen time delta. Each proposed row must preserve the previous and
next located candidates so the choice is auditable.

Apple Photos queries can take several minutes. Let a bounded scan finish unless
Photos reports an error or the user asks to stop. Never apply an interrupted or
partial plan.

## 2. Apply only after explicit confirmation

After the user has reviewed and explicitly approved that exact JSON plan:

```bash
mt fill-locations --apply-plan work/photos-location-fill/photos_location_fill_plan.json
```

`--apply-plan` must use the reviewed coordinates without rescanning Photos or
rebuilding neighbor choices. Confirm that its printed `Plan SHA-256` matches the
approved digest. The former combined `--apply` path is disabled.

Photos writes are item-by-item, not transactional. If apply is interrupted, or
returns any error count, treat the library as potentially partially updated:
do not blindly rerun the old plan; generate or inspect a fresh audit and review
the remaining targets first.

To reject a proposed row, edit a copy of the JSON so that row has empty
`source_id`, `latitude`, and `longitude` strings, add a clear rejection note,
then re-review and approve the complete modified JSON and its new SHA-256. Do
not delete schema fields or apply a partially reviewed file.

## Rules

- Choose the closer timestamp neighbor when both previous and next candidates
  exist. Record both deltas; do not impose an automatic time cutoff.
- Leave a row unresolved when no acceptable located neighbor exists.
- The implemented method is time-based. Do not claim visual similarity,
  thumbnail comparison, or embeddings are used.
- Reuse a reviewed cached plan for repeated review/apply work unless the user
  requests a refresh.
- A future watermark may narrow scans, but it must never remove neighbor
  evidence or make apply rescan. Advance it only after an approved apply, or
  after the user explicitly accepts a dry-run-only watermark update.
