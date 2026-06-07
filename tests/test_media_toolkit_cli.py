import unittest
import re
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit.cli import (
    build_script_argv,
    command_table,
    main,
    prompt_for_directory,
    resolve_command,
    resolve_default_directory,
)


class MediaToolkitCliTest(unittest.TestCase):
    def test_resolves_short_aliases(self):
        self.assertEqual(resolve_command("f").script_name, "extract_featured_raw.py")
        self.assertEqual(resolve_command("o").script_name, "organize.py")
        self.assertEqual(resolve_command("loc").script_name, "fill_missing_photo_locations.py")
        self.assertEqual(resolve_command("drone").script_name, "compress_drone_video.py")
        self.assertEqual(resolve_command("png").script_name, "png_to_jpg.py")

    def test_resolves_long_commands(self):
        self.assertEqual(resolve_command("featured").script_name, "extract_featured_raw.py")
        self.assertEqual(resolve_command("organize").script_name, "organize.py")
        self.assertEqual(resolve_command("fill-locations").script_name, "fill_missing_photo_locations.py")
        self.assertEqual(resolve_command("contact-sheet").script_name, "generate_contact_sheets.py")
        self.assertEqual(resolve_command("image-compress").script_name, "compress_images_under_size.py")
        self.assertEqual(resolve_command("png-to-jpg").script_name, "png_to_jpg.py")

    def test_confirms_current_directory_when_user_enters_y(self):
        command = resolve_command("o")
        argv = build_script_argv(
            command,
            ["--dry-run"],
            input_func=lambda _: "y",
            cwd_func=lambda: Path("/tmp/photos"),
            interactive=True,
        )

        self.assertEqual(
            argv,
            ["organize.py", str(Path("/tmp/photos").resolve()), "--dry-run"],
        )

    def test_prompts_for_directory_when_user_does_not_confirm(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "imports"
            target.mkdir()
            command = resolve_command("organize")
            argv = build_script_argv(
                command,
                [],
                input_func=lambda prompt: (
                    "n" if "Type y" in prompt else str(target)
                ),
                cwd_func=lambda: Path("/tmp/photos"),
                interactive=True,
            )

            self.assertEqual(argv, ["organize.py", str(target.resolve())])

    def test_requires_directory_argument_when_not_interactive(self):
        command = resolve_command("organize")
        stderr = StringIO()
        argv = build_script_argv(
            command,
            ["--dry-run"],
            interactive=False,
            output=stderr,
        )

        self.assertIsNone(argv)

    def test_explicit_directory_skips_confirmation_prompt(self):
        command = resolve_command("drone")
        argv = build_script_argv(
            command,
            ["/tmp/videos"],
            input_func=lambda _: (_ for _ in ()).throw(
                AssertionError("should not prompt")
            ),
            interactive=True,
        )

        self.assertEqual(argv, ["compress_drone_video.py", "/tmp/videos"])

    def test_resolve_default_directory_accepts_only_lowercase_y(self):
        with TemporaryDirectory() as tmp:
            valid = Path(tmp) / "imports"
            valid.mkdir()
            directory = resolve_default_directory(
                input_func=lambda prompt: (
                    "Y" if "Type y" in prompt else str(valid)
                ),
                cwd_func=lambda: Path("/tmp/photos"),
            )

            self.assertEqual(directory, valid.resolve())
            self.assertNotEqual(directory, Path("/tmp/photos"))

    def test_prompt_for_directory_rejects_missing_paths(self):
        with TemporaryDirectory() as tmp:
            valid = Path(tmp) / "photos"
            valid.mkdir()
            responses = iter(["", str(valid.with_name("missing")), str(valid)])
            stderr = StringIO()
            directory = prompt_for_directory(
                input_func=lambda _: next(responses),
                output=stderr,
            )

        self.assertEqual(directory, valid.resolve())
        self.assertIn("Directory is required.", stderr.getvalue())
        self.assertIn("Directory does not exist:", stderr.getvalue())

    def test_does_not_add_current_directory_when_positional_is_present(self):
        command = resolve_command("f")
        argv = build_script_argv(command, ["/tmp/event", "--recursive"])

        self.assertEqual(argv, ["extract_featured_raw.py", "/tmp/event", "--recursive"])

    def test_does_not_add_current_directory_for_location_command(self):
        command = resolve_command("loc")
        argv = build_script_argv(command, ["--describe"])

        self.assertEqual(argv, ["fill_missing_photo_locations.py", "--describe"])

    def test_command_table_prioritizes_clear_long_commands(self):
        table = command_table()

        self.assertIn("mt featured", table)
        self.assertIn("mt organize", table)
        self.assertIn("mt fill-locations", table)
        self.assertIsNone(re.search(r"^\s*mt f\s", table, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s*mt o\s", table, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s*mt loc\s", table, re.MULTILINE))

    def test_mt_without_args_shows_clear_long_commands(self):
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main([])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("mt featured", output)
        self.assertIn("mt organize", output)
        self.assertIsNone(re.search(r"^\s*mt f\s", output, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s*mt o\s", output, re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
