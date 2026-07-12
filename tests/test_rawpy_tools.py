import csv
import os
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import numpy as np
from PIL import Image

from media_toolkit import rawpy_tools


class FakeRaw:
    def __init__(
        self,
        image,
        *,
        colors=None,
        black_levels=None,
        white_level=1023,
        camera_white=None,
        postprocessed=None,
    ):
        self.raw_image_visible = np.array(image, dtype=np.uint16)
        self.raw_colors_visible = (
            np.array(colors, dtype=np.uint8)
            if colors is not None
            else np.zeros_like(self.raw_image_visible, dtype=np.uint8)
        )
        self.black_level_per_channel = black_levels or [0, 0, 0, 0]
        self.white_level = white_level
        self.camera_white_level_per_channel = camera_white
        self.camera_whitebalance = [2.0, 1.0, 1.5, 1.0]
        self.daylight_whitebalance = [2.1, 1.0, 1.4, 1.0]
        self._postprocessed = postprocessed

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def postprocess(self, **kwargs):
        self.postprocess_kwargs = kwargs
        return np.array(self._postprocessed, dtype=np.uint8)


class RawPyToolsTest(unittest.TestCase):
    def test_analyze_raw_reports_histogram_and_clipping_metrics(self):
        raw = FakeRaw(
            [
                [64, 128, 512, 1023],
                [80, 256, 900, 1000],
            ],
            black_levels=[64, 64, 64, 64],
            white_level=1023,
        )

        stats = rawpy_tools.analyze_raw(
            Path("DSC0001.ARW"),
            imread=lambda _path: raw,
        )

        self.assertEqual(stats.stem, "DSC0001")
        self.assertEqual(stats.width, 4)
        self.assertEqual(stats.height, 2)
        self.assertAlmostEqual(stats.clip_ratio, 0.125)
        self.assertAlmostEqual(stats.shadow_ratio, 0.125)
        self.assertGreater(stats.p99, stats.p50)

    def test_analyze_raw_reports_per_channel_clip_ratios(self):
        raw = FakeRaw(
            [
                [1023, 20],
                [1020, 30],
            ],
            colors=[
                [0, 1],
                [2, 3],
            ],
            white_level=1023,
        )

        stats = rawpy_tools.analyze_raw(
            Path("DSC0002.ARW"),
            imread=lambda _path: raw,
        )

        self.assertAlmostEqual(stats.channel_clip_ratios["0"], 1.0)
        self.assertAlmostEqual(stats.channel_clip_ratios["2"], 1.0)
        self.assertAlmostEqual(stats.channel_clip_ratios["1"], 0.0)

    def test_write_raw_stats_tsv_uses_stable_columns(self):
        stats = rawpy_tools.RawStats(
            path=Path("/shoot/raw/DSC0001.ARW"),
            stem="DSC0001",
            width=2,
            height=1,
            black_level=64,
            white_level=1023,
            p01=0.01,
            p50=0.5,
            p95=0.95,
            p99=0.99,
            p999=0.999,
            clip_ratio=0.1,
            shadow_ratio=0.2,
            channel_clip_ratios={"0": 0.1},
            camera_wb=[2.0, 1.0, 1.5, 1.0],
            daylight_wb=[2.1, 1.0, 1.4, 1.0],
        )

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "raw_stats.tsv"
            rawpy_tools.write_raw_stats_tsv(output, [stats], root=Path("/shoot"))
            with output.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh, delimiter="\t"))

        self.assertEqual(rows[0]["path"], "raw/DSC0001.ARW")
        self.assertEqual(rows[0]["clip_ratio"], "0.100000")
        self.assertEqual(rows[0]["channel_clip_ratios"], "0:0.100000")

    def test_read_xmp_rating_supports_xmp_and_acr_rating_forms(self):
        with TemporaryDirectory() as tmp:
            xmp = Path(tmp) / "DSC0001.xmp"
            xmp.write_text(
                '<rdf:Description xmp:Rating="4"><crs:Rating>5</crs:Rating></rdf:Description>',
                encoding="utf-8",
            )

            self.assertEqual(rawpy_tools.read_xmp_rating(xmp), 4)

    def test_filter_raws_by_rating_keeps_requested_candidates(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            for stem, rating in (("DSC0001", 2), ("DSC0002", 3), ("DSC0003", 5)):
                (raw_dir / f"{stem}.ARW").write_text("raw", encoding="utf-8")
                (raw_dir / f"{stem}.xmp").write_text(
                    f'<rdf:Description xmp:Rating="{rating}" />',
                    encoding="utf-8",
                )

            raws = rawpy_tools.collect_raw_files(root, rating_filter=">=3")

        self.assertEqual([path.name for path in raws], ["DSC0002.ARW", "DSC0003.ARW"])

    def test_render_raw_to_jpeg_writes_quality_96_subsampled_output(self):
        image = np.array(
            [
                [[255, 0, 0], [0, 255, 0]],
                [[0, 0, 255], [255, 255, 255]],
            ],
            dtype=np.uint8,
        )
        raw = FakeRaw([[1, 2], [3, 4]], postprocessed=image)

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "DSC0001.jpg"
            rawpy_tools.render_raw_to_jpeg(
                Path("DSC0001.ARW"),
                output,
                imread=lambda _path: raw,
            )

            with Image.open(output) as rendered:
                self.assertEqual(rendered.size, (2, 2))
            self.assertTrue(output.exists())

    def test_build_lr_plan_aligns_batch_exposure_from_raw_medians(self):
        dark = self._stats("DSC0001", p50=0.18, p99=0.82, p999=0.88)
        bright = self._stats("DSC0002", p50=0.42, p99=0.96, p999=0.99)

        plans = rawpy_tools.build_lr_plans([dark, bright], {"DSC0001": 4, "DSC0002": 4})
        by_stem = {plan.stem: plan for plan in plans}

        self.assertGreater(by_stem["DSC0001"].exposure2012, 0)
        self.assertLess(by_stem["DSC0002"].exposure2012, 0)
        self.assertLessEqual(by_stem["DSC0002"].highlights2012, -70)

    def test_build_lr_plans_keeps_ratings_distinct_for_same_stem_paths(self):
        first = self._stats("DSC0001", p50=0.2)
        second = self._stats("DSC0001", p50=0.4)
        first = rawpy_tools.RawStats(**{**first.__dict__, "path": Path("/shoot/lake/raw/DSC0001.ARW")})
        second = rawpy_tools.RawStats(**{**second.__dict__, "path": Path("/shoot/portrait/1/raw/DSC0001.ARW")})

        plans = rawpy_tools.build_lr_plans(
            [first, second],
            {first.path.resolve(): 4, second.path.resolve(): 3},
        )

        self.assertEqual([plan.rating for plan in plans], [4, 3])

    def test_build_lr_plan_protects_clipped_highlights_and_lifts_shadow_risk(self):
        clipped = self._stats(
            "DSC0003",
            p01=0.001,
            p50=0.22,
            p99=0.99,
            p999=1.0,
            clip_ratio=0.02,
            shadow_ratio=0.12,
        )

        plan = rawpy_tools.build_lr_plans([clipped], {"DSC0003": 5})[0]

        self.assertEqual(plan.highlights2012, -90)
        self.assertLess(plan.whites2012, 0)
        self.assertGreaterEqual(plan.shadows2012, 35)
        self.assertGreater(plan.blacks2012, 0)
        self.assertIn("highlight clipping", plan.rationale)

    def test_build_lr_plan_flower_style_uses_softer_contrast_and_airier_shadows(self):
        stats = self._stats("DSC0004", p50=0.28, p99=0.94, p999=0.98, shadow_ratio=0.04)

        plan = rawpy_tools.build_lr_plans([stats], {"DSC0004": 4}, style="flower")[0]

        self.assertLess(plan.contrast2012, 0)
        self.assertGreaterEqual(plan.shadows2012, 50)
        self.assertLessEqual(plan.highlights2012, -78)

    def test_write_lr_plan_tsv_uses_stable_columns(self):
        plan = rawpy_tools.LrPlan(
            path=Path("/shoot/raw/DSC0001.ARW"),
            stem="DSC0001",
            rating=4,
            exposure2012=0.25,
            highlights2012=-70,
            shadows2012=24,
            whites2012=-8,
            blacks2012=3,
            contrast2012=0,
            rationale="example",
        )

        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "lr_plan.tsv"
            rawpy_tools.write_lr_plan_tsv(output, [plan], root=Path("/shoot"))
            with output.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh, delimiter="\t"))

        self.assertEqual(rows[0]["path"], "raw/DSC0001.ARW")
        self.assertEqual(rows[0]["plan_style"], "travel")
        self.assertEqual(rows[0]["Exposure2012"], "0.25")
        self.assertEqual(rows[0]["Highlights2012"], "-70")

    def test_build_lr_xmp_fields_uses_flower_rich_style_skeleton(self):
        plan = rawpy_tools.LrPlan(
            path=Path("/shoot/raw/DSC0001.ARW"),
            stem="DSC0001",
            rating=4,
            exposure2012=0.34,
            highlights2012=-82,
            shadows2012=75,
            whites2012=8,
            blacks2012=-8,
            contrast2012=-12,
            rationale="example",
        )

        fields = rawpy_tools.build_lr_xmp_fields(plan, style="flower-rich")

        self.assertEqual(fields["CameraProfile"], "Camera ST")
        self.assertNotIn("WhiteBalance", fields)
        self.assertNotIn("Temperature", fields)
        self.assertNotIn("Tint", fields)
        self.assertEqual(fields["Exposure2012"], "+0.34")
        self.assertEqual(fields["Highlights2012"], "-82")
        self.assertEqual(fields["Shadows2012"], "+75")
        self.assertEqual(fields["Contrast2012"], "-12")
        self.assertEqual(fields["ProcessVersion"], "15.4")
        self.assertEqual(fields["ToneCurvePV2012"], "2, 5, 68, 55, 125, 124, 186, 193, 255, 250")
        self.assertEqual(fields["RedSaturation"], "+10")
        self.assertEqual(fields["GreenSaturation"], "+12")
        self.assertEqual(fields["BlueSaturation"], "+11")
        self.assertEqual(fields["SaturationAdjustmentBlue"], "-4")
        self.assertEqual(fields["PostCropVignetteAmount"], "-5")
        self.assertNotIn("PerspectiveUpright", fields)

    def test_build_lr_xmp_fields_has_learned_lake_and_nine_bends_profiles(self):
        plan = rawpy_tools.LrPlan(
            path=Path("/shoot/raw/DSC0001.ARW"),
            stem="DSC0001",
            rating=4,
            exposure2012=0.01,
            highlights2012=-85,
            shadows2012=81,
            whites2012=8,
            blacks2012=-12,
            contrast2012=-1,
            rationale="example",
        )

        lake = rawpy_tools.build_lr_xmp_fields(plan, style="sairim-lake-east")
        bends = rawpy_tools.build_lr_xmp_fields(plan, style="bayanbulak-nine-bends")

        self.assertNotIn("WhiteBalance", lake)
        self.assertNotIn("Temperature", lake)
        self.assertNotIn("Tint", lake)
        self.assertEqual(lake["RedSaturation"], "+4")
        self.assertEqual(lake["GreenSaturation"], "+2")
        self.assertEqual(lake["BlueSaturation"], "+6")
        self.assertEqual(bends["ToneCurvePV2012"], "2, 5, 66, 59, 125, 125, 182, 188, 255, 250")
        self.assertEqual(bends["CameraProfile"], "Adobe Standard")
        self.assertEqual(bends["Dehaze"], "+6")
        self.assertEqual(bends["GreenSaturation"], "+14")
        self.assertEqual(bends["SaturationAdjustmentYellow"], "+17")

    def test_build_lr_xmp_fields_enforces_fixed_lr_rules(self):
        plan = rawpy_tools.LrPlan(
            path=Path("/shoot/raw/DSC0001.ARW"),
            stem="DSC0001",
            rating=4,
            exposure2012=0.0,
            highlights2012=-55,
            shadows2012=20,
            whites2012=0,
            blacks2012=0,
            contrast2012=0,
            rationale="example",
        )

        fields = rawpy_tools.build_lr_xmp_fields(plan, style="travel-rich")

        self.assertNotIn("WhiteBalance", fields)
        self.assertNotIn("Temperature", fields)
        self.assertNotIn("Tint", fields)
        self.assertEqual(fields["ToneCurvePV2012"], "2, 5, 66, 59, 125, 125, 182, 188, 255, 250")
        self.assertGreaterEqual(int(fields["PostCropVignetteAmount"]), -7)
        self.assertEqual(fields["LensProfileEnable"], "1")
        self.assertEqual(fields["LensProfileSetup"], "Auto")

    def test_build_lr_xmp_fields_does_not_fake_iso_or_manual_transform_tuning(self):
        plan = rawpy_tools.LrPlan(
            path=Path("/shoot/raw/DSC0001.ARW"),
            stem="DSC0001",
            rating=4,
            exposure2012=0.0,
            highlights2012=-55,
            shadows2012=20,
            whites2012=0,
            blacks2012=0,
            contrast2012=0,
            rationale="histogram only",
        )

        fields = rawpy_tools.build_lr_xmp_fields(plan, style="travel-rich")

        self.assertNotIn("Sharpness", fields)
        self.assertNotIn("LuminanceSmoothing", fields)
        self.assertNotIn("ColorNoiseReduction", fields)
        self.assertNotIn("PerspectiveUpright", fields)

    def test_panorama_source_plan_forces_zero_post_crop_vignette(self):
        plan = rawpy_tools.LrPlan(
            path=Path("/shoot/panorama/1/raw/DSC0001.ARW"),
            stem="DSC0001",
            rating=4,
            exposure2012=0.0,
            highlights2012=-70,
            shadows2012=20,
            whites2012=0,
            blacks2012=0,
            contrast2012=0,
            rationale="panorama source",
        )

        fields = rawpy_tools.build_lr_xmp_fields(plan, style="flower-rich")

        self.assertEqual(fields["PostCropVignetteAmount"], "0")

    def test_write_lr_xmp_preserves_rating_and_adds_sidecar_markers(self):
        plan = rawpy_tools.LrPlan(
            path=Path("/shoot/raw/DSC0001.ARW"),
            stem="DSC0001",
            rating=5,
            exposure2012=0.5,
            highlights2012=-85,
            shadows2012=81,
            whites2012=8,
            blacks2012=-12,
            contrast2012=-10,
            rationale="example",
        )

        with TemporaryDirectory() as tmp:
            raw_file = Path(tmp) / "raw" / "DSC0001.ARW"
            raw_file.parent.mkdir()
            raw_file.write_text("raw", encoding="utf-8")
            xmp_file = raw_file.with_suffix(".xmp")
            xmp_file.write_text(
                '''<x:xmpmeta xmlns:x="adobe:ns:meta/">
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
<rdf:Description xmlns:xmp="http://ns.adobe.com/xap/1.0/" xmp:Rating="5" />
</rdf:RDF></x:xmpmeta>''',
                encoding="utf-8",
            )

            rawpy_tools.write_lr_xmp_sidecar(
                raw_file,
                rawpy_tools.build_lr_xmp_fields(plan, style="flower-rich"),
                rating=5,
            )
            text = xmp_file.read_text(encoding="utf-8")

        self.assertIn('xmp:Rating="5"', text)
        self.assertIn('crs:CameraProfile="Camera ST"', text)
        self.assertIn('crs:Exposure2012="+0.50"', text)
        self.assertIn('crs:Highlights2012="-85"', text)
        self.assertIn('crs:ProcessVersion="15.4"', text)
        self.assertIn('crs:RedSaturation="+10"', text)
        self.assertIn("<crs:ToneCurvePV2012>", text)
        self.assertIn("<rdf:li>2, 5</rdf:li>", text)
        self.assertIn("<rdf:li>255, 250</rdf:li>", text)
        self.assertNotIn('crs:PerspectiveUpright="0"', text)
        self.assertIn('photoshop:SidecarForExtension="ARW"', text)
        self.assertIn('dc:format="image/x-sony-arw"', text)
        self.assertIn('xmpMM:PreservedFileName="DSC0001.ARW"', text)

    def test_write_lr_xmp_updates_owned_fields_without_destroying_manual_metadata(self):
        plan = rawpy_tools.LrPlan(
            path=Path("/shoot/raw/DSC0001.ARW"),
            stem="DSC0001",
            rating=5,
            exposure2012=0.5,
            highlights2012=-85,
            shadows2012=81,
            whites2012=8,
            blacks2012=-12,
            contrast2012=-10,
            rationale="reviewed plan",
        )

        with TemporaryDirectory() as tmp:
            raw_file = Path(tmp) / "raw" / "DSC0001.ARW"
            raw_file.parent.mkdir()
            raw_file.write_text("raw", encoding="utf-8")
            xmp_file = raw_file.with_suffix(".xmp")
            xmp_file.write_text(
                '''<?xpacket begin="" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
   xmlns:xmp="http://ns.adobe.com/xap/1.0/"
   xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
   xmlns:custom="https://example.invalid/custom/"
   xmp:Rating="5" xmp:Label="manual-label"
   crs:Exposure2012="-0.25" crs:CropTop="0.123"
   crs:PerspectiveUpright="1" crs:PerspectiveRotate="1.75"
   custom:Reviewer="human">
   <crs:MaskGroupBasedCorrections>
    <rdf:Seq><rdf:li custom:MaskId="keep-me" /></rdf:Seq>
   </crs:MaskGroupBasedCorrections>
   <!-- manual review note must survive -->
   <custom:Payload>custom element</custom:Payload>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>
''',
                encoding="utf-8",
            )

            with patch(
                "media_toolkit.rawpy_tools.os.replace",
                wraps=os.replace,
            ) as replace:
                rawpy_tools.write_lr_xmp_sidecar(
                    raw_file,
                    rawpy_tools.build_lr_xmp_fields(plan, style="flower-rich"),
                    rating=5,
                )

            replace.assert_called_once()
            updated_text = xmp_file.read_text(encoding="utf-8")
            root = ET.fromstring(self._xmp_root_text(updated_text))

        namespaces = {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "xmp": "http://ns.adobe.com/xap/1.0/",
            "crs": "http://ns.adobe.com/camera-raw-settings/1.0/",
            "custom": "https://example.invalid/custom/",
        }
        description = root.find("rdf:RDF/rdf:Description", namespaces)
        self.assertIsNotNone(description)
        self.assertEqual(description.get(f"{{{namespaces['xmp']}}}Rating"), "5")
        self.assertEqual(description.get(f"{{{namespaces['xmp']}}}Label"), "manual-label")
        self.assertEqual(description.get(f"{{{namespaces['crs']}}}Exposure2012"), "+0.50")
        self.assertEqual(description.get(f"{{{namespaces['crs']}}}CropTop"), "0.123")
        self.assertEqual(description.get(f"{{{namespaces['crs']}}}PerspectiveUpright"), "1")
        self.assertEqual(description.get(f"{{{namespaces['crs']}}}PerspectiveRotate"), "1.75")
        self.assertEqual(description.get(f"{{{namespaces['custom']}}}Reviewer"), "human")
        mask = description.find("crs:MaskGroupBasedCorrections/rdf:Seq/rdf:li", namespaces)
        self.assertIsNotNone(mask)
        self.assertEqual(mask.get(f"{{{namespaces['custom']}}}MaskId"), "keep-me")
        payload = description.find("custom:Payload", namespaces)
        self.assertEqual(payload.text, "custom element")
        self.assertIn("manual review note must survive", updated_text)

    def test_write_lr_xmp_normalizes_owned_element_fields_without_duplicates(self):
        with TemporaryDirectory() as tmp:
            raw_file = Path(tmp) / "DSC0001.ARW"
            raw_file.write_text("raw", encoding="utf-8")
            xmp_file = raw_file.with_suffix(".xmp")
            xmp_file.write_text(
                '''<x:xmpmeta xmlns:x="adobe:ns:meta/"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:xmp="http://ns.adobe.com/xap/1.0/"
 xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
 <rdf:RDF><rdf:Description crs:ToneCurvePV2012="0, 0, 255, 255">
  <xmp:Rating>2</xmp:Rating>
  <crs:Exposure2012>-0.25</crs:Exposure2012>
  <crs:HasSettings>False</crs:HasSettings>
 </rdf:Description></rdf:RDF>
</x:xmpmeta>''',
                encoding="utf-8",
            )

            rawpy_tools.write_lr_xmp_sidecar(
                raw_file,
                {
                    "Exposure2012": "+0.50",
                    "HasSettings": "True",
                    "ToneCurvePV2012": "2, 5, 255, 250",
                },
                rating=4,
            )
            root = ET.fromstring(self._xmp_root_text(xmp_file.read_text(encoding="utf-8")))

        namespaces = {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "xmp": "http://ns.adobe.com/xap/1.0/",
            "crs": "http://ns.adobe.com/camera-raw-settings/1.0/",
        }
        description = root.find("rdf:RDF/rdf:Description", namespaces)
        self.assertEqual(description.get(f"{{{namespaces['xmp']}}}Rating"), "4")
        self.assertEqual(description.get(f"{{{namespaces['crs']}}}Exposure2012"), "+0.50")
        self.assertEqual(description.get(f"{{{namespaces['crs']}}}HasSettings"), "True")
        self.assertIsNone(description.find("xmp:Rating", namespaces))
        self.assertIsNone(description.find("crs:Exposure2012", namespaces))
        self.assertIsNone(description.find("crs:HasSettings", namespaces))
        self.assertIsNone(description.get(f"{{{namespaces['crs']}}}ToneCurvePV2012"))
        self.assertIsNotNone(description.find("crs:ToneCurvePV2012", namespaces))

    def test_read_lr_plan_rejects_paths_that_escape_shoot_root(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "shoot"
            root.mkdir()
            plan = root / "lr_plan.tsv"
            plan.write_text(
                "path\tstem\trating\tplan_style\tExposure2012\tHighlights2012\tShadows2012\tWhites2012\tBlacks2012\tContrast2012\trationale\n"
                "../outside.ARW\toutside\t4\ttravel\t0.1\t-50\t20\t0\t0\t0\treviewed\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "outside the shoot directory"):
                rawpy_tools.read_lr_plan_tsv(plan, root=root)

    def _xmp_root_text(self, text: str) -> str:
        start = text.index("<x:xmpmeta")
        end = text.index("</x:xmpmeta>") + len("</x:xmpmeta>")
        return text[start:end]

    def _stats(
        self,
        stem,
        *,
        p01=0.01,
        p50=0.3,
        p95=0.78,
        p99=0.9,
        p999=0.96,
        clip_ratio=0.0,
        shadow_ratio=0.01,
    ):
        return rawpy_tools.RawStats(
            path=Path(f"/shoot/raw/{stem}.ARW"),
            stem=stem,
            width=2,
            height=1,
            black_level=64,
            white_level=1023,
            p01=p01,
            p50=p50,
            p95=p95,
            p99=p99,
            p999=p999,
            clip_ratio=clip_ratio,
            shadow_ratio=shadow_ratio,
            channel_clip_ratios={},
            camera_wb=[2.0, 1.0, 1.5, 1.0],
            daylight_wb=[2.1, 1.0, 1.4, 1.0],
        )


if __name__ == "__main__":
    unittest.main()
