import unittest
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit.commands import drone, image_compress, png_to_jpg
from media_toolkit.legacy_processing import FileContext, compress_image, traverse


class LegacyProcessingTest(unittest.TestCase):
    def test_compress_image_invokes_ffmpeg_without_shell_string_escaping(self):
        with TemporaryDirectory() as tmp:
            source = Path(tmp) / "name with ' quote.png"
            source.write_text("source", encoding="utf-8")
            ctx = FileContext(str(source))

            def fake_run(args, **kwargs):
                Path(ctx.temp_file).write_text("converted", encoding="utf-8")
                return type("Result", (), {"returncode": 0})()

            with (
                patch("media_toolkit.legacy_processing.subprocess.run", side_effect=fake_run) as run,
                redirect_stdout(StringIO()),
            ):
                self.assertTrue(compress_image(ctx, "iw:ih", "jpg"))

            args = run.call_args.args[0]
            self.assertIn(str(source), args)
            self.assertNotIn("\\'", args)
            self.assertTrue((Path(tmp) / "compressed" / "name with ' quote.jpg").exists())

    def test_traverse_returns_success_and_failure_counts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "good.png").write_text("good", encoding="utf-8")
            (root / "bad.png").write_text("bad", encoding="utf-8")

            def process(ctx, _var1, _var2, _var3):
                return Path(ctx.original_file).name == "good.png"

            succeeded, failed = traverse(str(root), ".png", process)

        self.assertEqual((succeeded, failed), (1, 1))

    def test_png_to_jpg_returns_nonzero_when_any_conversion_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.png").write_text("bad", encoding="utf-8")

            with (
                patch.object(png_to_jpg, "compress_image", return_value=False),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                exit_code = png_to_jpg.main([str(root)])

        self.assertEqual(exit_code, 1)

    def test_drone_returns_nonzero_when_any_conversion_fails(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bad.mp4").write_text("bad", encoding="utf-8")

            with (
                patch.object(drone, "compress_drone_video", return_value=False),
                redirect_stdout(StringIO()),
                redirect_stderr(StringIO()),
            ):
                exit_code = drone.main([str(root)])

        self.assertEqual(exit_code, 1)

    def test_image_compress_continues_after_ffmpeg_process_failure(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first.jpg"
            second = root / "second.jpg"
            first.write_bytes(b"first")
            second.write_bytes(b"second")
            stderr = StringIO()
            stdout = StringIO()

            with (
                patch.object(
                    image_compress,
                    "collect_oversized",
                    return_value=[first, second],
                ),
                patch.object(image_compress, "require_ffmpeg", return_value="ffmpeg"),
                patch.object(
                    image_compress,
                    "compress_one",
                    side_effect=[
                        subprocess.CalledProcessError(1, ["ffmpeg"]),
                        (True, 6, 3),
                    ],
                ) as compress_one,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                exit_code = image_compress.main([str(root), "--max-bytes", "1"])

        self.assertEqual(exit_code, 1)
        self.assertEqual(compress_one.call_count, 2)
        self.assertIn("compressed=1 failed=1", stdout.getvalue())
        self.assertIn("failed", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
