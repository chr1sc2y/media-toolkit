import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from media_toolkit.commands import learn_style
from media_toolkit.style_learning import learn_style_from_directory


class StyleLearningTest(unittest.TestCase):
    def test_learns_fields_from_root_and_portrait_exports(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_export_and_xmp(root / "raw", "DSC0001", "Camera ST", "-85")
            self._write_export_and_xmp(root / "portrait/1/raw", "DSC0002", "Camera PT", "-70")

            report = learn_style_from_directory(root, scene="flower-field")

        self.assertEqual(report.sample_count, 2)
        self.assertEqual(report.field_values["CameraProfile"], ["Camera PT", "Camera ST"])
        self.assertEqual(report.field_values["Highlights2012"], ["-70", "-85"])

    def test_reports_missing_xmp_for_export(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw/Export").mkdir(parents=True)
            (root / "raw/Export/DSC0001.jpg").write_text("export", encoding="utf-8")

            report = learn_style_from_directory(root, scene="grassland")

        self.assertEqual(report.sample_count, 0)
        self.assertEqual(report.missing_xmp, ["raw/Export/DSC0001.jpg"])

    def test_learn_style_json_output(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_export_and_xmp(root / "raw", "DSC0001", "Camera ST", "-85")
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = learn_style.main([str(root), "--scene", "flower-field", "--json"])

            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["scene"], "flower-field")
        self.assertEqual(payload["sample_count"], 1)

    def test_recurses_scene_roots_and_prefers_pixcake_once_per_stem(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "lake-valley/raw"
            (raw_dir / "Export/Pixcake").mkdir(parents=True)
            (raw_dir / "Export/DSC0001.jpg").write_text("direct", encoding="utf-8")
            (raw_dir / "Export/Pixcake/DSC0001.jpg").write_text(
                "pixcake", encoding="utf-8"
            )
            (raw_dir / "DSC0001.xmp").write_text(
                '<rdf:Description crs:Texture="+6" />', encoding="utf-8"
            )

            report = learn_style_from_directory(root, scene="lake-valley")

        self.assertEqual(report.sample_count, 1)
        self.assertEqual(
            report.samples[0].export_path,
            "lake-valley/raw/Export/Pixcake/DSC0001.jpg",
        )

    def test_rating_only_sidecar_is_not_counted_as_style_sample(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw/Export").mkdir(parents=True)
            (root / "raw/Export/DSC0001.jpg").write_text("export", encoding="utf-8")
            (root / "raw/DSC0001.xmp").write_text(
                '<rdf:Description xmp:Rating="4" crs:HasSettings="True" />',
                encoding="utf-8",
            )

            report = learn_style_from_directory(root, scene="travel")

        self.assertEqual(report.sample_count, 0)
        self.assertEqual(report.ignored_xmp, ["raw/DSC0001.xmp"])

    def test_summarizes_numeric_frequency_median_range_and_baseline_deviations(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_fields(root / "raw", "DSC0001", {"Texture": "+6"})
            self._write_fields(root / "raw", "DSC0002", {"Texture": "+10"})

            report = learn_style_from_directory(
                root,
                scene="travel",
                baseline_profile="travel-rich",
            )

        texture = report.field_summaries["Texture"]
        self.assertEqual(texture["count"], 2)
        self.assertEqual(texture["frequencies"], {"+10": 1, "+6": 1})
        self.assertEqual(texture["numeric"], {"min": 6.0, "median": 8.0, "max": 10.0})
        self.assertEqual(texture["baseline"], "+6")
        self.assertEqual(len(report.deviations["Texture"]), 1)
        self.assertEqual(report.deviations["Texture"][0]["value"], "+10")

    def test_extracts_global_curve_hsl_calibration_detail_lens_and_rotate_fields(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            fields = {
                "ParametricHighlights": "+4",
                "HueAdjustmentBlue": "-3",
                "BlueSaturation": "+6",
                "Sharpness": "35",
                "LuminanceSmoothing": "20",
                "LensProfileEnable": "1",
                "PerspectiveRotate": "-0.25",
            }
            self._write_fields(root / "raw", "DSC0001", fields)

            report = learn_style_from_directory(root, scene="travel")

        self.assertEqual(report.sample_count, 1)
        for field, value in fields.items():
            self.assertEqual(report.samples[0].fields[field], value)

    def test_local_mask_settings_do_not_override_global_style_fields(self):
        with TemporaryDirectory() as tmp:
            xmp = Path(tmp) / "masked.xmp"
            xmp.write_text(
                """<x:xmpmeta xmlns:x="adobe:ns:meta/"
                    xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
                    xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/">
                  <rdf:RDF>
                    <rdf:Description crs:Exposure2012="+0.20" crs:Texture="+6"
                        crs:CropTop="0.123" crs:RawFileDigest="private-file-id">
                      <crs:ToneCurvePV2012><rdf:Seq>
                        <rdf:li>0, 0</rdf:li><rdf:li>255, 255</rdf:li>
                      </rdf:Seq></crs:ToneCurvePV2012>
                      <crs:MaskGroupBasedCorrections><rdf:Seq><rdf:li>
                        <rdf:Description crs:Exposure2012="+1.50" crs:Texture="+40" />
                      </rdf:li></rdf:Seq></crs:MaskGroupBasedCorrections>
                    </rdf:Description>
                  </rdf:RDF>
                </x:xmpmeta>""",
                encoding="utf-8",
            )

            fields = __import__(
                "media_toolkit.style_learning", fromlist=["read_style_fields"]
            ).read_style_fields(xmp)

        self.assertEqual(fields["Exposure2012"], "+0.20")
        self.assertEqual(fields["Texture"], "+6")
        self.assertEqual(fields["ToneCurvePV2012"], "0, 0 / 255, 255")
        self.assertNotIn("MaskGroupBasedCorrections", fields)
        self.assertNotIn("CropTop", fields)
        self.assertNotIn("RawFileDigest", fields)

    def test_cli_accepts_explicit_baseline_profile(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_fields(root / "raw", "DSC0001", {"Texture": "+10"})
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = learn_style.main(
                    [
                        str(root),
                        "--scene",
                        "travel",
                        "--baseline",
                        "travel-rich",
                        "--json",
                    ]
                )

            payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["baseline_profile"], "travel-rich")
        self.assertEqual(payload["deviations"]["Texture"][0]["value"], "+10")

    def _write_export_and_xmp(self, raw_dir: Path, stem: str, profile: str, highlights: str) -> None:
        (raw_dir / "Export").mkdir(parents=True)
        (raw_dir / "Export" / f"{stem}.jpg").write_text("export", encoding="utf-8")
        (raw_dir / f"{stem}.xmp").write_text(
            f'<rdf:Description crs:CameraProfile="{profile}" crs:Highlights2012="{highlights}" />',
            encoding="utf-8",
        )

    def _write_fields(self, raw_dir: Path, stem: str, fields: dict[str, str]) -> None:
        (raw_dir / "Export").mkdir(parents=True, exist_ok=True)
        (raw_dir / "Export" / f"{stem}.jpg").write_text("export", encoding="utf-8")
        attributes = " ".join(
            f'crs:{key}="{value}"' for key, value in fields.items()
        )
        (raw_dir / f"{stem}.xmp").write_text(
            f"<rdf:Description {attributes} />", encoding="utf-8"
        )


if __name__ == "__main__":
    unittest.main()
