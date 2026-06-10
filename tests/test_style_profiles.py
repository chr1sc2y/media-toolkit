import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from media_toolkit import rawpy_tools
from media_toolkit.commands import lr_apply, styles
from media_toolkit.style_profiles import (
    get_style_profile,
    list_style_profiles,
    render_style_detail,
    render_style_summary,
)


class StyleProfilesTest(unittest.TestCase):
    def test_registry_covers_lr_apply_profiles(self):
        registry_ids = {profile["id"] for profile in list_style_profiles()}

        self.assertEqual(registry_ids, set(rawpy_tools.LR_STYLE_PROFILES))
        self.assertEqual(registry_ids, set(lr_apply.PLAN_STYLE_BY_XMP_STYLE))

    def test_style_detail_mentions_plan_style(self):
        detail = render_style_detail(get_style_profile("flower-rich"))

        self.assertIn("flower-rich", detail)
        self.assertIn("plan style: flower", detail)
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
