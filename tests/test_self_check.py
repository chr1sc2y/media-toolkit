import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from media_toolkit.commands import self_check
from media_toolkit.self_check import run_self_checks, self_check_ok, self_check_payload


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


if __name__ == "__main__":
    unittest.main()
