# Sony Travel Lightroom — Manual Artistic Reference

This note is for human/agent review during manual Lightroom refinement. It is
not a machine preset and does not define `mt lr-apply` behavior. Actual automated
fields live only in `media_toolkit/style_profiles.json`; inspect them with
`mt styles`.

In particular, the current CLI does **not** automatically infer subject type,
Camera PT portrait treatment, ISO-dependent noise reduction, lens-dependent
sharpening, white balance, crop, Upright, or rotation. Apply any such decision
only after visual/metadata review in Lightroom.

## General direction

- Natural Sony travel color with more depth than straight-out-of-camera output.
- Preserve real weather and atmosphere; do not force an overcast scene into a
  sunny/HDR look.
- Protect highlights, retain a believable black point, and avoid grey lifted
  shadows.
- Prefer restrained global saturation and clean blue/green/cyan separation.
- Use a gentle curve and calibration/HSL only at the strength supported by the
  individual scene.
- Avoid orange-teal grading, plastic texture, oversaturated grass/sky, obvious
  vignette, and automatic perspective changes that damage composition.

## Scene-specific observations

`travel-rich` is the general landscape baseline. It suits ordinary travel
landscapes, roads, towns, grasslands, and mixed weather, but is not a portrait
profile.

`flower-rich` reflects the brighter flower-field direction learned from manual
refinement: stronger highlight protection, softer contrast, more open shadows,
controlled blues, and stronger—but still reviewed—calibration color. Do not
transfer that strength to portraits, night/city scenes, snow, or already
saturated close-ups.

`sairim-lake-east` keeps water/sky/grass separation restrained for open lake
scenes. `bayanbulak-nine-bends` is grounded around broad meadow and winding-river
color. See `mt styles <profile>` for exact current machine values.

## Manual-only review ideas

These are questions, not automatic rules:

- Portrait: would a natural Camera PT-like profile and gentler Texture/Clarity
  improve skin and hair, and is that profile actually available?
- Lens: does the specific file need correction or sharpening after 100% review?
- High ISO: does luminance NR remove noise without smearing detail?
- Horizon: is a small manual rotation worth its crop/composition cost?
- White balance: is As Shot credible, or has a reviewed batch correction been
  requested?
- Panorama: keep source-frame vignette at zero and make finishing decisions only
  after stitching.

## Point-curve and color intent

A restrained S curve can add depth while keeping endpoints smooth. A commonly
useful reference shape is near `2,5 / 66,59 / 125,125 / 182,188 / 255,250`, but
it is not universal. Saturation normally stays near zero; small Vibrance,
calibration, or HSL moves should solve a specific color problem rather than
create the whole style.

For a Hasselblad-leaning interpretation, aim for smoother highlight roll-off,
slightly richer midtones, restrained saturation, and clean blue/green
separation—not a filter or a global saturation boost.

## Learning loop

After the user manually refines and exports a coherent scene, inspect evidence
with:

```bash
mt learn-style <photo-dir> --scene <scene> --baseline <profile> --json
```

Promote a lesson into `style_profiles.json` only when the user asks and multiple
valid final Export/XMP samples support it. Keep profiles scene-specific and run
the style/profile tests after changes.
