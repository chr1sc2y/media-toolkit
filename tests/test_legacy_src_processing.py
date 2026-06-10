import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from src import FileContext, compress_image


class LegacySrcProcessingTest(unittest.TestCase):
    def test_src_package_reexports_safe_legacy_processing(self):
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


if __name__ == "__main__":
    unittest.main()
