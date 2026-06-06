import unittest
from pathlib import Path
from unittest.mock import patch

from media_toolkit.cli import build_script_argv, resolve_command


class MediaToolkitCliTest(unittest.TestCase):
    def test_resolves_short_aliases(self):
        self.assertEqual(resolve_command("f").script_name, "extract_featured_raw.py")
        self.assertEqual(resolve_command("o").script_name, "organize.py")
        self.assertEqual(resolve_command("loc").script_name, "fill_missing_photo_locations.py")
        self.assertEqual(resolve_command("drone").script_name, "compress_drone_video.py")
        self.assertEqual(resolve_command("png").script_name, "png_to_jpg.py")

    def test_adds_current_directory_for_directory_commands_without_positionals(self):
        with patch("pathlib.Path.cwd", return_value=Path("/tmp/photos")):
            command = resolve_command("o")
            argv = build_script_argv(command, ["--dry-run"])

        self.assertEqual(argv, ["organize.py", "/tmp/photos", "--dry-run"])

    def test_adds_current_directory_for_legacy_directory_commands(self):
        with patch("pathlib.Path.cwd", return_value=Path("/tmp/photos")):
            self.assertEqual(
                build_script_argv(resolve_command("drone"), []),
                ["compress_drone_video.py", "/tmp/photos"],
            )
            self.assertEqual(
                build_script_argv(resolve_command("png"), []),
                ["png_to_jpg.py", "/tmp/photos"],
            )

    def test_does_not_add_current_directory_when_positional_is_present(self):
        command = resolve_command("f")
        argv = build_script_argv(command, ["/tmp/event", "--recursive"])

        self.assertEqual(argv, ["extract_featured_raw.py", "/tmp/event", "--recursive"])

    def test_does_not_add_current_directory_for_location_command(self):
        command = resolve_command("loc")
        argv = build_script_argv(command, ["--describe"])

        self.assertEqual(argv, ["fill_missing_photo_locations.py", "--describe"])


if __name__ == "__main__":
    unittest.main()
