import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from media_toolkit import rawpy_tools
from media_toolkit.commands import lr_apply, styles
from media_toolkit.style_profiles import (
    get_style_profile,
    lr_plan_styles_by_xmp_style,
    lr_style_profiles,
    list_style_profiles,
    render_style_detail,
    render_style_summary,
    style_profile_ids,
    validate_style_profile_registry,
)


class StyleProfilesTest(unittest.TestCase):
    def test_registry_covers_lr_apply_profiles(self):
        registry_ids = {profile["id"] for profile in list_style_profiles()}

        self.assertEqual(registry_ids, set(rawpy_tools.LR_STYLE_PROFILES))
        self.assertEqual(registry_ids, set(lr_apply.PLAN_STYLE_BY_XMP_STYLE))
        self.assertEqual(registry_ids, set(style_profile_ids()))

    def test_registry_is_source_for_lr_style_profiles(self):
        profiles = lr_style_profiles()

        self.assertEqual(profiles, rawpy_tools.LR_STYLE_PROFILES)
        self.assertEqual(profiles["flower-rich"]["RedSaturation"], "+10")
        self.assertEqual(
            profiles["bayanbulak-nine-bends"]["CameraProfile"],
            "Adobe Standard",
        )

    def test_registry_is_source_for_lr_plan_style_mapping(self):
        mapping = lr_plan_styles_by_xmp_style()

        self.assertEqual(mapping, lr_apply.PLAN_STYLE_BY_XMP_STYLE)
        self.assertEqual(mapping["flower-rich"], "flower")
        self.assertEqual(mapping["travel-rich"], "travel")

    def test_registry_rejects_forbidden_lightroom_fields(self):
        registry = {
            "profiles": [
                {
                    "id": "bad",
                    "plan_style": "travel",
                    "xmp_fields": {
                        "CameraProfile": "Camera ST",
                        "ToneCurveName2012": "Custom",
                        "ToneCurvePV2012": "0, 0, 255, 255",
                        "PostCropVignetteAmount": "-2",
                        "Temperature": "5200",
                    },
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "forbidden XMP fields"):
            validate_style_profile_registry(registry)

    def test_registry_rejects_too_dark_vignette(self):
        registry = {
            "profiles": [
                {
                    "id": "bad",
                    "plan_style": "travel",
                    "xmp_fields": {
                        "CameraProfile": "Camera ST",
                        "ToneCurveName2012": "Custom",
                        "ToneCurvePV2012": "0, 0, 255, 255",
                        "PostCropVignetteAmount": "-20",
                    },
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "too-dark"):
            validate_style_profile_registry(registry)

    def test_style_detail_mentions_plan_style(self):
        detail = render_style_detail(get_style_profile("flower-rich"))

        self.assertIn("flower-rich", detail)
        self.assertIn("plan style: flower", detail)
        self.assertIn("xmp fields:", detail)
        self.assertIn("明亮花田旅行", detail)

    def test_style_summary_lists_profiles(self):
        summary = render_style_summary()

        self.assertIn("travel-rich", summary)
        self.assertIn("flower-rich", summary)

    def test_styles_json_output(self):
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = styles.main(["flower-rich", "--json"])

        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["id"], "flower-rich")
        self.assertEqual(payload["plan_style"], "flower")


if __name__ == "__main__":
    unittest.main()
