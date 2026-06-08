# Lightroom Sony ST Travel Base

This is the default starting point for agent-written Lightroom / Camera Raw XMP
sidecars. It is not a fixed preset to apply blindly. Treat it as a guardrail for
custom rough edits based on exposure metadata, lens, subject, RAW histogram
evidence, visual review, and the desired batch consistency.

HIF previews are useful for culling, composition/focus review, and contact
sheets, but they already include Sony camera rendering. Do not use HIF
brightness or color as the source of truth for RAW exposure or color grading.
Prefer `rawpy`/LibRaw linear RAW statistics for final-candidate exposure
decisions.

## Stable Defaults

- Camera profile: prefer `Camera ST` for non-portraits; for Sony portraits,
  prefer `Camera PT`. Fall back to a natural Standard/ST/PT-like profile if
  unavailable.
- Lens correction: enable profile correction with automatic lens profile setup.
- Chromatic aberration: enable automatic lateral CA removal.
- Upright: keep automatic Upright off by default. Inspect previews and use small
  manual `PerspectiveRotate` corrections only when the horizon is visibly wrong.
- White balance: keep `As Shot` only while exploring or when the batch is
  visually consistent. For final-candidate photos from the same scene/weather,
  write an explicit shared `ColorTemperature` and `Tint` so neighboring
  candidates do not drift in color.
- Sharpening: do not add extra sharpening by default, except a small amount for
  Tamron 50-400mm F4.5-6.3 A067 images.
- Noise reduction: apply stronger luminance/color noise reduction only when
  ISO is high, starting at ISO >= 800.
- Sidecars: always write lowercase `.xmp` files and include Lightroom-readable
  sidecar markers: `crs:HasSettings=True`, `crs:AlreadyApplied=False`,
  `photoshop:SidecarForExtension=ARW`, `dc:format=image/x-sony-arw`, and
  `xmpMM:PreservedFileName=<RAW filename>`.

## Color Calibration

The previous experimental values `RedSaturation=8`, `GreenSaturation=6`,
`BlueSaturation=8` were too strong for the user's preferred direction. Keep
global Saturation at `0` by default, use little or no Vibrance, and prefer subtle
Camera Calibration changes over direct saturation boosts.

Use a softer default:

```text
RedSaturation=2
GreenSaturation=1
BlueSaturation=1
```

Treat these as a gentle travel-photo starting point. For already vivid sunset,
grassland, lake, neon, or skin-tone images, reduce or skip calibration
saturation. For a Hasselblad-leaning direction, keep saturation restrained,
protect highlight roll-off, make midtones slightly thicker, and separate blue
and green subtly through calibration rather than high Vibrance.

## Sony ST Influence, Capped

The user's personal `Sony ST.xmp` preset has useful structure: strong highlight
protection, global Saturation and Vibrance held at zero, a little Texture, and
color energy coming from Camera Calibration rather than direct HSL saturation.
Borrow those ideas at low strength only, so the result stays closer to the
Hasselblad / Prov1dence direction.

Good ideas to borrow:

```text
Highlights2012=-55 to -70
Texture=5 to 7
Vibrance=0 to 4
Saturation=0
ToneCurvePV2012=0, 0, 66, 59, 125, 125, 182, 188, 255, 255
```

Caps to keep the look natural:

```text
Shadows2012=10 to 24
Dehaze=1 to 4
RedSaturation=2 to 4
GreenSaturation=1 to 3
BlueSaturation=0 to 2
PostCropVignetteAmount=0 by default, or -3 to -6 only when it helps a centered landscape
```

Do not inherit these `Sony ST.xmp` choices as defaults:

```text
PerspectiveUpright=Auto
Shadows2012=42
Dehaze=8
RedSaturation=11
GreenSaturation=12
BlueSaturation=12
```

For non-portraits, keep `Camera ST`. Reserve `Camera PT` for portraits.

## Tone Curve

Use a very light contrast curve when the image benefits from it. The goal is
more depth, not a crushed look. The user's `Sony ST.xmp` point curve is a good
low-strength reference for landscapes because it slightly deepens lower tones,
leaves the midtone anchor neutral, and gently lifts upper tones:

```text
ToneCurveName2012=Custom
ToneCurvePV2012=0, 0, 66, 59, 125, 125, 182, 188, 255, 255
ToneCurvePV2012Red=0, 0, 255, 255
ToneCurvePV2012Green=0, 0, 255, 255
ToneCurvePV2012Blue=0, 0, 255, 255
```

When writing only parametric curve fields, use this restrained equivalent:

```text
ParametricHighlights=4
ParametricLights=6
ParametricDarks=-4
ParametricShadows=-2
```

Skip or reduce this for already contrasty scenes, fog, portraits with delicate
skin, or night images.

## HSL And Vignette

For batch rough edits, keep HSL/Mixer moves small. Use them to prevent grass,
water, and sky from becoming too saturated or synthetic, not to create the main
look:

```text
SaturationAdjustmentGreen=-4 to +4
SaturationAdjustmentAqua=-6 to +2
SaturationAdjustmentBlue=-6 to +2
LuminanceAdjustmentGreen=0 to +5
LuminanceAdjustmentYellow=0 to +5
LuminanceAdjustmentBlue=-3 to +2
```

For final single-image edits on `>=3` star photos, larger HSL moves are allowed
when the preview proves they help, but avoid pushing grassland, water, or sky
into banding or a synthetic orange/teal look.

Keep post-crop vignette off by default:

```text
PostCropVignetteAmount=0
```

Use `-3` to `-6` only for centered landscapes or loose edges that need a little
containment. Do not add vignette to panorama source frames before stitching;
decide after the panorama has been merged.

## Batch White Balance Consistency

When a group of selected photos comes from the same scene and weather, use a
shared white balance after visual review. This prevents one candidate from
looking like a different edit just because `As Shot` stored a slightly different
camera interpretation.

For overcast Xinjiang grassland/river scenes, this has worked as a neutral
starting point:

```text
WhiteBalance=Custom
ColorTemperature=5250
Tint=14
```

Adjust per image only when the subject or light genuinely differs, such as
indoor light, portraits under a reflector, sunset, night scenes, or mixed light.

## Suggested XMP Fields

```text
XMP-crs:CameraProfile=Camera ST
XMP-crs:LensProfileEnable=1
XMP-crs:LensProfileSetup=Auto
XMP-crs:LensProfileDistortionScale=100
XMP-crs:LensProfileVignettingScale=100
XMP-crs:AutoLateralCA=1
XMP-crs:PerspectiveUpright=Off
XMP-crs:RedHue=0
XMP-crs:RedSaturation=2
XMP-crs:GreenHue=0
XMP-crs:GreenSaturation=1
XMP-crs:BlueHue=0
XMP-crs:BlueSaturation=1
XMP-crs:Saturation=0
XMP-crs:ColorNoiseReduction=25
XMP-crs:ColorNoiseReductionDetail=50
XMP-crs:ColorNoiseReductionSmoothness=50
XMP-crs:HasSettings=True
XMP-crs:AlreadyApplied=False
XMP-photoshop:SidecarForExtension=ARW
XMP-dc:Format=image/x-sony-arw
```

For ISO >= 800, add:

```text
XMP-crs:LuminanceSmoothing=22
XMP-crs:LuminanceNoiseReductionDetail=50
XMP-crs:LuminanceNoiseReductionContrast=0
XMP-crs:ColorNoiseReduction=35
```

For Tamron 50-400mm F4.5-6.3 A067 only, a small sharpening baseline is allowed:

```text
XMP-crs:Sharpness=45
XMP-crs:SharpenRadius=1.0
XMP-crs:SharpenDetail=25
XMP-crs:SharpenEdgeMasking=20
```

For other lenses, leave sharpening for final edit/export after denoise, crop,
and output size are known.
