# Lightroom Sony ST Travel Base

This is the default starting point for agent-written Lightroom / Camera Raw XMP
sidecars. It is a workflow preset description, not a claim that these numbers
are universally best.

## Stable Defaults

- Camera profile: prefer `Camera ST`; fall back to a natural Standard/ST-like
  profile if unavailable.
- Lens correction: enable profile correction with automatic lens profile setup.
- Chromatic aberration: enable automatic lateral CA removal.
- Upright: use conservative `Level` upright as the default request.
- White balance: keep `As Shot` unless the image is visibly wrong.
- Sharpening: do not add extra sharpening by default.
- Noise reduction: apply stronger luminance/color noise reduction only when
  ISO is high, starting at ISO >= 800.

## Color Calibration

The previous experimental values `RedSaturation=8`, `GreenSaturation=6`,
`BlueSaturation=8` were hand-picked starting values, not proven best values.
Use a softer default:

```text
RedSaturation=4
GreenSaturation=3
BlueSaturation=4
```

Treat these as a gentle travel-photo starting point. For already vivid sunset,
grassland, lake, neon, or skin-tone images, reduce or skip calibration
saturation.

## Suggested XMP Fields

```text
XMP-crs:CameraProfile=Camera ST
XMP-crs:LensProfileEnable=1
XMP-crs:LensProfileSetup=Auto
XMP-crs:LensProfileDistortionScale=100
XMP-crs:LensProfileVignettingScale=100
XMP-crs:AutoLateralCA=1
XMP-crs:PerspectiveUpright=Level
XMP-crs:RedHue=0
XMP-crs:RedSaturation=4
XMP-crs:GreenHue=0
XMP-crs:GreenSaturation=3
XMP-crs:BlueHue=0
XMP-crs:BlueSaturation=4
XMP-crs:ColorNoiseReduction=25
XMP-crs:ColorNoiseReductionDetail=50
XMP-crs:ColorNoiseReductionSmoothness=50
```

For ISO >= 800, add:

```text
XMP-crs:LuminanceSmoothing=22
XMP-crs:LuminanceNoiseReductionDetail=50
XMP-crs:LuminanceNoiseReductionContrast=0
XMP-crs:ColorNoiseReduction=35
```

Do not write these by default:

```text
XMP-crs:Sharpness
XMP-crs:SharpenRadius
XMP-crs:SharpenDetail
XMP-crs:SharpenEdgeMasking
```

Sharpening should be decided during final edit/export after denoise, crop, and
output size are known.

