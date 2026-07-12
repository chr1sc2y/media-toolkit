import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from media_toolkit.commands import self_check
from media_toolkit.self_check import (
    SelfCheckResult,
    run_self_checks,
    self_check_ok,
    self_check_payload,
)


class SelfCheckTest(unittest.TestCase):
    def test_self_checks_pass_for_current_repo(self):
        results = run_self_checks()

        self.assertTrue(self_check_ok(results))
        self.assertEqual(
            {result.name for result in results},
            {
                "command-registry",
                "command-modules",
                "script-wrappers",
                "workflow-registry",
                "style-registry",
                "package-resources",
                "raw-support",
                "ffmpeg",
                "heif-decoder",
                "repository-skills",
            },
        )

    def test_self_check_payload_reports_overall_status(self):
        payload = self_check_payload(run_self_checks())

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["checks"])

    def test_self_check_json_command(self):
        stdout = StringIO()

        with redirect_stdout(stdout):
            exit_code = self_check.main(["--json"])

        payload = json.loads(stdout.getvalue())

        self.assertEqual(exit_code, 0)
        self.assertTrue(payload["ok"])
        self.assertTrue(
            any(check["name"] == "style-registry" for check in payload["checks"])
        )

    def test_optional_capability_failure_does_not_fail_overall_check(self):
        results = [
            SelfCheckResult("required", True, "present", required=True),
            SelfCheckResult("optional", False, "not installed", required=False),
        ]

        self.assertTrue(self_check_ok(results))
        payload = self_check_payload(results)
        self.assertTrue(payload["ok"])
        self.assertFalse(payload["checks"][1]["required"])

    def test_installed_distribution_does_not_require_repository_scripts(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            results = run_self_checks(Path(directory))

        scripts = next(result for result in results if result.name == "script-wrappers")
        skills = next(result for result in results if result.name == "repository-skills")
        self.assertTrue(scripts.ok)
        self.assertIn("installed distribution", scripts.message)
        self.assertTrue(skills.ok)
        self.assertIn("installed distribution", skills.message)

    def test_ffmpeg_check_warns_when_contact_sheet_drawtext_is_unavailable(self):
        result = type(
            "Completed",
            (),
            {"returncode": 0, "stdout": " T.. scale V->V Scale video", "stderr": ""},
        )()
        with (
            patch("media_toolkit.self_check.shutil.which", return_value="/usr/bin/ffmpeg"),
            patch("media_toolkit.self_check.subprocess.run", return_value=result),
            self.assertRaisesRegex(RuntimeError, "drawtext"),
        ):
            from media_toolkit.self_check import _check_ffmpeg

            _check_ffmpeg()


if __name__ == "__main__":
    unittest.main()
