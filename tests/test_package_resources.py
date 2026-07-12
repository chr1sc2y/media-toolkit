from __future__ import annotations

from importlib import resources
import json
import unittest


class PackageResourceTests(unittest.TestCase):
    def test_runtime_json_resources_are_readable_from_package_api(self) -> None:
        package = resources.files("media_toolkit")

        workflows = json.loads(
            package.joinpath("workflows.json").read_text(encoding="utf-8")
        )
        styles = json.loads(
            package.joinpath("style_profiles.json").read_text(encoding="utf-8")
        )

        self.assertTrue(workflows["workflows"])
        self.assertTrue(styles["profiles"])


if __name__ == "__main__":
    unittest.main()
