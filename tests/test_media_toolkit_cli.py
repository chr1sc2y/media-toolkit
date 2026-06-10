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
        self.assertEqual(resolve_command("finalize").script_name, "finalize.py")
        self.assertEqual(resolve_command("featured").script_name, "extract_featured_raw.py")
        self.assertEqual(resolve_command("organize").script_name, "organize.py")
        self.assertEqual(resolve_command("fill-locations").script_name, "fill_missing_photo_locations.py")
        self.assertEqual(resolve_command("contact-sheet").script_name, "generate_contact_sheets.py")
        self.assertEqual(resolve_command("portrait-organize").script_name, "portrait_organize.py")
        self.assertEqual(resolve_command("panorama-organize").script_name, "panorama_organize.py")
        self.assertEqual(resolve_command("manifest-template").script_name, "manifest_template.py")
        self.assertEqual(resolve_command("verify-cull").script_name, "verify_cull.py")
        self.assertEqual(resolve_command("raw-analyze").script_name, "raw_analyze.py")
        self.assertEqual(resolve_command("lr-plan").script_name, "lr_plan.py")
        self.assertEqual(resolve_command("lr-apply").script_name, "lr_apply.py")
        self.assertEqual(resolve_command("rawpy-render").script_name, "rawpy_render.py")
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

    def test_help_option_does_not_require_directory(self):
        command = resolve_command("verify-cull")
        argv = build_script_argv(command, ["--help"], interactive=False)

        self.assertEqual(argv, ["verify_cull.py", "--help"])

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

    def test_contact_sheet_value_options_do_not_count_as_directory(self):
        command = resolve_command("contact-sheet")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                [
                    "--hif-only",
                    "--final-overview",
                    "/tmp/_contact_sheet.jpg",
                    "--section-prefix",
                    "Portrait",
                ],
                interactive=False,
            )

        self.assertIsNone(argv)
        self.assertIn("directory required", stderr.getvalue())

    def test_portrait_organize_manifest_option_does_not_count_as_directory(self):
        command = resolve_command("portrait-organize")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                ["--manifest", "/tmp/portraits.tsv"],
                interactive=False,
            )

        self.assertIsNone(argv)
        self.assertIn("directory required", stderr.getvalue())

    def test_portrait_organize_with_directory_passes_manifest_option(self):
        command = resolve_command("portrait-organize")
        argv = build_script_argv(
            command,
            ["/tmp/photos", "--manifest", "/tmp/portraits.tsv"],
            interactive=False,
        )

        self.assertEqual(
            argv,
            ["portrait_organize.py", "/tmp/photos", "--manifest", "/tmp/portraits.tsv"],
        )

    def test_portrait_organize_with_directory_can_use_default_manifest(self):
        command = resolve_command("portrait-organize")
        argv = build_script_argv(command, ["/tmp/photos"], interactive=False)

        self.assertEqual(argv, ["portrait_organize.py", "/tmp/photos"])

    def test_panorama_organize_with_directory_passes_manifest_option(self):
        command = resolve_command("panorama-organize")
        argv = build_script_argv(
            command,
            ["/tmp/photos", "--manifest", "/tmp/panorama.tsv"],
            interactive=False,
        )

        self.assertEqual(
            argv,
            ["panorama_organize.py", "/tmp/photos", "--manifest", "/tmp/panorama.tsv"],
        )

    def test_panorama_organize_with_directory_can_use_default_manifest(self):
        command = resolve_command("panorama-organize")
        argv = build_script_argv(command, ["/tmp/photos"], interactive=False)

        self.assertEqual(argv, ["panorama_organize.py", "/tmp/photos"])

    def test_manifest_template_value_options_do_not_count_as_directory(self):
        command = resolve_command("manifest-template")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                ["--kind", "portrait", "--output", "/tmp/portrait_manifest.tsv"],
                interactive=False,
            )

        self.assertIsNone(argv)
        self.assertIn("directory required", stderr.getvalue())

    def test_manifest_template_with_directory_passes_kind_option(self):
        command = resolve_command("manifest-template")
        argv = build_script_argv(
            command,
            ["/tmp/photos", "--kind", "panorama"],
            interactive=False,
        )

        self.assertEqual(argv, ["manifest_template.py", "/tmp/photos", "--kind", "panorama"])

    def test_verify_cull_with_directory_passes_path(self):
        command = resolve_command("verify-cull")
        argv = build_script_argv(command, ["/tmp/photos"], interactive=False)

        self.assertEqual(argv, ["verify_cull.py", "/tmp/photos"])

    def test_raw_analyze_value_options_do_not_count_as_directory(self):
        command = resolve_command("raw-analyze")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                ["--output", "/tmp/raw_stats.tsv", "--ratings", ">=3"],
                interactive=False,
            )

        self.assertIsNone(argv)
        self.assertIn("directory required", stderr.getvalue())

    def test_finalize_value_options_do_not_count_as_directory(self):
        command = resolve_command("finalize")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                [
                    "--copy-to",
                    "/tmp/archive",
                    "--scene",
                    "flower-field",
                    "--photos-album",
                    "Sony",
                    "--recursive",
                ],
                interactive=False,
            )

        self.assertIsNone(argv)
        self.assertIn("directory required", stderr.getvalue())

    def test_lr_plan_value_options_do_not_count_as_directory(self):
        command = resolve_command("lr-plan")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                ["--output", "/tmp/lr_plan.tsv", "--ratings", ">=3", "--style", "flower"],
                interactive=False,
            )

        self.assertIsNone(argv)
        self.assertIn("directory required", stderr.getvalue())

    def test_lr_apply_value_options_do_not_count_as_directory(self):
        command = resolve_command("lr-apply")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                ["--ratings", ">=3", "--style", "flower-rich"],
                interactive=False,
            )

        self.assertIsNone(argv)
        self.assertIn("directory required", stderr.getvalue())

    def test_rawpy_render_value_options_do_not_count_as_directory(self):
        command = resolve_command("rawpy-render")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                ["--output-dir", "/tmp/rawpy_inputs", "--ratings", ">=3", "--quality", "96"],
                interactive=False,
            )

        self.assertIsNone(argv)
        self.assertIn("directory required", stderr.getvalue())

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
        argv = build_script_argv(
            command,
            ["/tmp/event", "--copy-to", "/tmp/archive", "--recursive"],
        )

        self.assertEqual(
            argv,
            [
                "extract_featured_raw.py",
                "/tmp/event",
                "--copy-to",
                "/tmp/archive",
                "--recursive",
            ],
        )

    def test_does_not_add_current_directory_for_location_command(self):
        command = resolve_command("loc")
        argv = build_script_argv(command, ["--describe"])

        self.assertEqual(argv, ["fill_missing_photo_locations.py", "--describe"])

    def test_command_table_prioritizes_clear_long_commands(self):
        table = command_table()

        self.assertIn("mt finalize", table)
        self.assertIn("mt organize", table)
        self.assertIn("mt fill-locations", table)
        self.assertIn("mt portrait-organize", table)
        self.assertIn("mt panorama-organize", table)
        self.assertIn("mt manifest-template", table)
        self.assertIn("mt verify-cull", table)
        self.assertIn("mt raw-analyze", table)
        self.assertIn("mt lr-plan", table)
        self.assertIn("mt lr-apply", table)
        self.assertIn("mt rawpy-render", table)
        self.assertIsNone(re.search(r"^\s*mt f\s", table, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s*mt featured\s", table, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s*mt o\s", table, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s*mt loc\s", table, re.MULTILINE))

    def test_mt_without_args_shows_clear_long_commands(self):
        stdout = StringIO()
        with patch("sys.stdout", stdout):
            exit_code = main([])

        output = stdout.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("mt finalize", output)
        self.assertIsNone(re.search(r"^\s*mt featured\s", output, re.MULTILINE))
        self.assertIn("mt organize", output)
        self.assertIsNone(re.search(r"^\s*mt f\s", output, re.MULTILINE))
        self.assertIsNone(re.search(r"^\s*mt o\s", output, re.MULTILINE))


if __name__ == "__main__":
    unittest.main()
