import importlib.util
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "generate_contact_sheets.py"
SPEC = importlib.util.spec_from_file_location("generate_contact_sheets", SCRIPT_PATH)
generate_contact_sheets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(generate_contact_sheets)


class GenerateContactSheetsTest(unittest.TestCase):
    def test_collect_images_includes_hif_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "DSC0002.hif").write_text("hif", encoding="utf-8")
            (root / "DSC0003.ARW").write_text("raw", encoding="utf-8")

            images = generate_contact_sheets.collect_images(root, False, [])

        self.assertEqual([image.name for image in images], ["DSC0001.HIF", "DSC0002.hif"])

    def test_render_tile_converts_hif_with_sips_before_ffmpeg(self):
        with TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            image = temp_dir / "DSC0001.HIF"
            tile = temp_dir / "tile.jpg"
            image.write_text("hif", encoding="utf-8")

            with patch.object(generate_contact_sheets, "run_ffmpeg") as run_ffmpeg:
                with patch.object(generate_contact_sheets, "run_sips") as run_sips:
                    generate_contact_sheets.render_tile(
                        "ffmpeg",
                        image,
                        tile,
                        1,
                        360,
                        320,
                        52,
                        3,
                    )

            run_sips.assert_called_once_with(image, tile.with_name("tile_input.jpg"))
            ffmpeg_cmd = run_ffmpeg.call_args.args[0]
            self.assertIn(str(tile.with_name("tile_input.jpg")), ffmpeg_cmd)

    def test_format_label_omits_index_by_default(self):
        label = generate_contact_sheets.format_label(Path("DSC0001.HIF"), 7, False)

        self.assertEqual(label, "DSC0001.HIF")

    def test_format_label_can_include_index(self):
        label = generate_contact_sheets.format_label(Path("DSC0001.HIF"), 7, True)

        self.assertEqual(label, "007 DSC0001.HIF")


if __name__ == "__main__":
    unittest.main()
