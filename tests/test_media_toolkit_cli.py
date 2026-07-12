import unittest
import re
from dataclasses import replace
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit.cli import (
    build_script_argv,
    run_module,
    command_table,
    main,
    prompt_for_directory,
    resolve_command,
    resolve_default_directory,
)


class MediaToolkitCliTest(unittest.TestCase):
    def test_resolves_short_aliases(self):
        self.assertEqual(resolve_command("o").script_name, "organize.py")
        self.assertEqual(resolve_command("loc").script_name, "fill_missing_photo_locations.py")
        self.assertEqual(resolve_command("drone").script_name, "compress_drone_video.py")
        self.assertEqual(resolve_command("png").script_name, "png_to_jpg.py")

    def test_resolves_long_commands(self):
        self.assertEqual(resolve_command("finalize").script_name, "finalize.py")
        self.assertEqual(resolve_command("hif-prune").script_name, "hif_prune.py")
        self.assertEqual(resolve_command("organize").script_name, "organize.py")
        self.assertEqual(resolve_command("fill-locations").script_name, "fill_missing_photo_locations.py")
        self.assertEqual(resolve_command("contact-sheet").script_name, "generate_contact_sheets.py")
        self.assertEqual(resolve_command("portrait-organize").script_name, "portrait_organize.py")
        self.assertEqual(resolve_command("panorama-organize").script_name, "panorama_organize.py")
        self.assertEqual(resolve_command("manifest-template").script_name, "manifest_template.py")
        self.assertEqual(resolve_command("verify-cull").script_name, "verify_cull.py")
        self.assertEqual(resolve_command("doctor").script_name, "doctor.py")
        self.assertEqual(resolve_command("status").script_name, "status.py")
        self.assertEqual(resolve_command("preflight-run").script_name, "preflight_run.py")
        self.assertEqual(resolve_command("batch-report").script_name, "batch_report.py")
        self.assertEqual(resolve_command("raw-analyze").script_name, "raw_analyze.py")
        self.assertEqual(resolve_command("ratings-apply").script_name, "ratings_apply.py")
        self.assertEqual(resolve_command("lr-plan").script_name, "lr_plan.py")
        self.assertEqual(resolve_command("lr-apply").script_name, "lr_apply.py")
        self.assertEqual(resolve_command("styles").script_name, "styles.py")
        self.assertEqual(resolve_command("learn-style").script_name, "learn_style.py")
        self.assertEqual(resolve_command("rawpy-render").script_name, "rawpy_render.py")
        self.assertEqual(resolve_command("image-compress").script_name, "compress_images_under_size.py")
        self.assertEqual(resolve_command("png-to-jpg").script_name, "png_to_jpg.py")
        self.assertEqual(resolve_command("commands").script_name, "commands.py")
        self.assertEqual(resolve_command("workflows").script_name, "workflows.py")
        self.assertEqual(resolve_command("self-check").script_name, "self_check.py")

    def test_featured_compatibility_aliases_are_removed_from_mt(self):
        for name in ("featured", "feature", "f"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    resolve_command(name)

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

    def test_ratings_apply_value_options_do_not_count_as_directory(self):
        command = resolve_command("ratings-apply")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                ["--manifest", "/tmp/ratings.tsv"],
                interactive=False,
            )

        self.assertIsNone(argv)
        self.assertIn("directory required", stderr.getvalue())

    def test_hif_prune_value_options_do_not_count_as_directory(self):
        command = resolve_command("hif-prune")
        stderr = StringIO()
        with patch("sys.stderr", stderr):
            argv = build_script_argv(
                command,
                ["--mode", "aggressive", "--scene", "grassland", "--manifest", "/tmp/plan.json"],
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
        command = resolve_command("finalize")
        argv = build_script_argv(
            command,
            ["/tmp/event", "--copy-to", "/tmp/archive", "--recursive", "--hif-only"],
        )

        self.assertEqual(
            argv,
            [
                "finalize.py",
                "/tmp/event",
                "--copy-to",
                "/tmp/archive",
                "--recursive",
                "--hif-only",
            ],
        )

    def test_does_not_add_current_directory_for_location_command(self):
        command = resolve_command("loc")
        argv = build_script_argv(command, ["--describe"])

        self.assertEqual(argv, ["fill_missing_photo_locations.py", "--describe"])

    def test_migrated_commands_run_package_modules_without_runpy(self):
        command = resolve_command("workflows")
        stdout = StringIO()
        with patch("media_toolkit.cli.runpy.run_path") as run_path, patch("sys.stdout", stdout):
            exit_code = run_module(command, ["finalize"])

        self.assertEqual(exit_code, 0)
        run_path.assert_not_called()
        self.assertIn("成片归档", stdout.getvalue())

    def test_verify_and_manifest_commands_are_package_modules(self):
        self.assertEqual(
            resolve_command("verify-cull").module_name,
            "media_toolkit.commands.verify_cull",
        )
        self.assertEqual(
            resolve_command("manifest-template").module_name,
            "media_toolkit.commands.manifest_template",
        )
        self.assertEqual(
            resolve_command("portrait-organize").module_name,
            "media_toolkit.commands.portrait_organize",
        )
        self.assertEqual(
            resolve_command("panorama-organize").module_name,
            "media_toolkit.commands.panorama_organize",
        )
        self.assertEqual(
            resolve_command("organize").module_name,
            "media_toolkit.commands.organize",
        )
        self.assertEqual(
            resolve_command("fill-locations").module_name,
            "media_toolkit.commands.fill_locations",
        )
        self.assertEqual(
            resolve_command("contact-sheet").module_name,
            "media_toolkit.commands.contact_sheet",
        )
        self.assertIn("move", resolve_command("organize").side_effects)
        self.assertTrue(resolve_command("organize").supports_dry_run)
        self.assertEqual(
            resolve_command("raw-analyze").module_name,
            "media_toolkit.commands.raw_analyze",
        )
        self.assertEqual(
            resolve_command("lr-plan").module_name,
            "media_toolkit.commands.lr_plan",
        )
        self.assertEqual(
            resolve_command("ratings-apply").module_name,
            "media_toolkit.commands.ratings_apply",
        )
        self.assertEqual(
            resolve_command("lr-apply").module_name,
            "media_toolkit.commands.lr_apply",
        )
        self.assertEqual(
            resolve_command("rawpy-render").module_name,
            "media_toolkit.commands.rawpy_render",
        )
        self.assertEqual(
            resolve_command("image-compress").module_name,
            "media_toolkit.commands.image_compress",
        )
        self.assertEqual(
            resolve_command("drone").module_name,
            "media_toolkit.commands.drone",
        )
        self.assertEqual(
            resolve_command("png-to-jpg").module_name,
            "media_toolkit.commands.png_to_jpg",
        )
        self.assertTrue(resolve_command("lr-apply").supports_dry_run)
        self.assertTrue(resolve_command("image-compress").supports_dry_run)

    def test_command_without_package_module_falls_back_to_script_runner(self):
        command = replace(resolve_command("contact-sheet"), module_name=None)
        with patch("media_toolkit.cli.run_script", return_value=0) as run_script:
            exit_code = run_module(command, ["--help"])

        self.assertEqual(exit_code, 0)
        run_script.assert_called_once_with(command, ["--help"])

    def test_command_table_prioritizes_clear_long_commands(self):
        table = command_table()

        self.assertIn("mt finalize", table)
        self.assertIn("mt organize", table)
        self.assertIn("mt fill-locations", table)
        self.assertIn("mt portrait-organize", table)
        self.assertIn("mt panorama-organize", table)
        self.assertIn("mt manifest-template", table)
        self.assertIn("mt verify-cull", table)
        self.assertIn("mt doctor", table)
        self.assertIn("mt status", table)
        self.assertIn("mt preflight-run", table)
        self.assertIn("mt batch-report", table)
        self.assertIn("mt raw-analyze", table)
        self.assertIn("mt lr-plan", table)
        self.assertIn("mt ratings-apply", table)
        self.assertIn("mt lr-apply", table)
        self.assertIn("mt styles", table)
        self.assertIn("mt learn-style", table)
        self.assertIn("mt rawpy-render", table)
        self.assertIn("mt commands", table)
        self.assertIn("mt workflows", table)
        self.assertIn("mt self-check", table)
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
