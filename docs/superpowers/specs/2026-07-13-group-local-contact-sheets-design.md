# Group-Local Contact Sheets Design

## Goal

Make portrait and panorama review more granular by keeping one final contact
sheet inside each numbered group instead of combining every group into one
parent-level overview.

## Output contract

The ordinary root overview remains unchanged:

```text
<photo-dir>/_contact_sheet.jpg
```

Numbered groups own their final overviews:

```text
<photo-dir>/portrait/1/_contact_sheet.jpg
<photo-dir>/portrait/2/_contact_sheet.jpg
<photo-dir>/panorama/1/_contact_sheet.jpg
<photo-dir>/panorama/2/_contact_sheet.jpg
```

These former aggregate outputs are retired:

```text
<photo-dir>/portrait/_contact_sheet.jpg
<photo-dir>/panorama/_contact_sheet.jpg
```

## Generation behavior

`mt portrait-organize` and `mt panorama-organize` continue rebuilding the root
ordinary overview after a successful move. They then enumerate numbered group
directories in numeric order and run `mt contact-sheet` once per group, using
that group's `hif/` directory as the visual source and writing the final overview
inside the group.

Temporary sheet pages and manifests remain under a temporary directory. They do
not become user-facing artifacts. The generic
`mt contact-sheet --section-by-numbered-dir` option remains available for other
callers, but the initial-cull workflow no longer uses it for portrait or
panorama output.

After every requested per-group overview is generated successfully, the
organizer removes a legacy parent-level aggregate overview if one exists. It
does not remove the legacy file before successful replacement generation.

## Verification

Strict `mt verify-cull` requires `_contact_sheet.jpg` in every numbered portrait
or panorama group that has an `hif/` directory. The allowed final output set is:

- the ordinary root `_contact_sheet.jpg`;
- `portrait/<number>/_contact_sheet.jpg`;
- `panorama/<number>/_contact_sheet.jpg`.

Parent-level portrait/panorama overviews and other ad hoc contact-sheet JPGs are
reported as redundant.

## Documentation and compatibility

The repository Skill, Lightroom cull prompt, and README examples use a
`<group>` placeholder for per-group regeneration. Existing media and group
layouts remain unchanged. Only generated review artifacts move to a finer
location; no RAW, HIF, XMP, Export, rating, or archive behavior changes.

## Tests

Regression tests cover:

- numeric ordering and one command per portrait/panorama group;
- exact per-group final-overview paths;
- removal of legacy aggregate sheets only after successful generation;
- strict verification of missing per-group sheets;
- rejection of retired parent-level aggregate sheets;
- preservation of the root ordinary overview behavior.
