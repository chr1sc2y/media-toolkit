import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from media_toolkit.commands import contact_sheet as generate_contact_sheets


class GenerateContactSheetsTest(unittest.TestCase):
    def test_collect_images_includes_hif_files(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "DSC0002.hif").write_text("hif", encoding="utf-8")
            (root / "DSC0003.ARW").write_text("raw", encoding="utf-8")

            images = generate_contact_sheets.collect_images(root, False, [])

        self.assertEqual([image.name for image in images], ["DSC0001.HIF", "DSC0002.hif"])

    def test_collect_images_hif_only_only_uses_hif_directories(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "hif").mkdir()
            (root / "hif" / "DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "raw" / "Export" / "DSC0001.jpg").write_text("jpg", encoding="utf-8")
            (root / "portrait" / "1" / "hif").mkdir(parents=True)
            (root / "portrait" / "1" / "hif" / "DSC0002.HIF").write_text(
                "hif", encoding="utf-8"
            )
            (root / "other").mkdir()
            (root / "other" / "DSC0003.HIF").write_text("hif", encoding="utf-8")

            images = generate_contact_sheets.collect_images(root, False, [], True)

        self.assertEqual(
            [image.relative_to(root) for image in images],
            [
                Path("hif/DSC0001.HIF"),
                Path("portrait/1/hif/DSC0002.HIF"),
            ],
        )

    def test_render_tile_decodes_hif_with_ffmpeg_before_labeling(self):
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

            run_sips.assert_not_called()
            self.assertEqual(run_ffmpeg.call_count, 2)
            decode_cmd = run_ffmpeg.call_args_list[0].args[0]
            render_cmd = run_ffmpeg.call_args_list[1].args[0]
            self.assertIn(str(image), decode_cmd)
            self.assertIn(str(tile.with_name("tile_input.jpg")), render_cmd)

    def test_render_tile_falls_back_to_sips_when_ffmpeg_hif_decode_fails(self):
        with TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            image = temp_dir / "DSC0001.HIF"
            tile = temp_dir / "tile.jpg"
            image.write_text("hif", encoding="utf-8")

            with patch.object(
                generate_contact_sheets,
                "run_ffmpeg",
                side_effect=[RuntimeError("decode failed"), None],
            ) as run_ffmpeg:
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

            self.assertEqual(run_ffmpeg.call_count, 2)
            run_sips.assert_called_once_with(image, tile.with_name("tile_input.jpg"))
            ffmpeg_cmd = run_ffmpeg.call_args.args[0]
            self.assertIn(str(tile.with_name("tile_input.jpg")), ffmpeg_cmd)

    def test_render_tile_uses_sips_when_hif_ffmpeg_decode_fails(self):
        with TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            image = temp_dir / "DSC0001.HIF"
            tile = temp_dir / "tile.jpg"
            image.write_text("hif", encoding="utf-8")

            with patch.object(
                generate_contact_sheets,
                "run_ffmpeg",
                side_effect=[RuntimeError("decode failed"), None],
            ) as run_ffmpeg:
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

    def test_render_tile_falls_back_to_sips_when_decoded_hif_render_fails(self):
        with TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            image = temp_dir / "DSC0001.HIF"
            tile = temp_dir / "tile.jpg"
            image.write_text("hif", encoding="utf-8")

            with patch.object(
                generate_contact_sheets,
                "run_ffmpeg",
                side_effect=[None, RuntimeError("render failed"), None],
            ) as run_ffmpeg:
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

            self.assertEqual(run_ffmpeg.call_count, 3)
            run_sips.assert_called_once_with(image, tile.with_name("tile_input.jpg"))
            retry_cmd = run_ffmpeg.call_args.args[0]
            self.assertIn(str(tile.with_name("tile_input.jpg")), retry_cmd)

    def test_render_sheet_uses_only_existing_tiles(self):
        with TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            sheet = temp_dir / "sheet.jpg"
            for index in range(1, 4):
                (temp_dir / f"tile_{index:04d}.jpg").write_text("tile", encoding="utf-8")

            with patch.object(generate_contact_sheets, "run_ffmpeg") as run_ffmpeg:
                generate_contact_sheets.render_sheet(
                    "ffmpeg",
                    temp_dir,
                    sheet,
                    cols=5,
                    tile_count=3,
                    tile_width=360,
                    tile_height=320,
                    quality=3,
                )

            cmd = run_ffmpeg.call_args.args[0]
            self.assertEqual(cmd.count("-i"), 3)
            filter_complex = cmd[cmd.index("-filter_complex") + 1]
            self.assertIn("xstack=inputs=3", filter_complex)
            self.assertNotIn("tile_0004.jpg", cmd)

    def test_render_sheet_handles_single_tile_without_xstack(self):
        with TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            sheet = temp_dir / "sheet.jpg"
            (temp_dir / "tile_0001.jpg").write_text("tile", encoding="utf-8")

            with patch.object(generate_contact_sheets, "run_ffmpeg") as run_ffmpeg:
                generate_contact_sheets.render_sheet(
                    "ffmpeg",
                    temp_dir,
                    sheet,
                    cols=5,
                    tile_count=1,
                    tile_width=360,
                    tile_height=320,
                    quality=3,
                )

            cmd = run_ffmpeg.call_args.args[0]
            self.assertEqual(cmd.count("-i"), 1)
            self.assertIn(str(temp_dir / "tile_0001.jpg"), cmd)
            filter_complex = cmd[cmd.index("-filter_complex") + 1]
            self.assertNotIn("xstack", filter_complex)
            self.assertIn("pad=384:344:12:12:white", filter_complex)

    def test_build_sheet_plan_groups_numbered_dirs_with_section_titles(self):
        root = Path("/photos/portrait")
        images = [
            root / "1" / "hif" / "DSC0001.HIF",
            root / "1" / "hif" / "DSC0002.HIF",
            root / "2" / "hif" / "DSC0003.HIF",
        ]

        plan = generate_contact_sheets.build_sheet_plan(
            images,
            root,
            per_sheet=2,
            section_by_numbered_dir=True,
            section_prefix="Portrait",
        )

        self.assertEqual(
            [(page.title, [image.name for image in page.images]) for page in plan],
            [
                ("Portrait 1", ["DSC0001.HIF", "DSC0002.HIF"]),
                ("Portrait 2", ["DSC0003.HIF"]),
            ],
        )

    def test_build_sheet_plan_omits_section_titles_by_default(self):
        root = Path("/photos")
        images = [
            root / "hif" / "DSC0001.HIF",
            root / "hif" / "DSC0002.HIF",
            root / "hif" / "DSC0003.HIF",
        ]

        plan = generate_contact_sheets.build_sheet_plan(
            images,
            root,
            per_sheet=2,
            section_by_numbered_dir=False,
            section_prefix=None,
        )

        self.assertEqual(
            [(page.title, [image.name for image in page.images]) for page in plan],
            [
                (None, ["DSC0001.HIF", "DSC0002.HIF"]),
                (None, ["DSC0003.HIF"]),
            ],
        )

    def test_combine_contact_sheets_adds_section_headers(self):
        with TemporaryDirectory() as tmp:
            temp_dir = Path(tmp)
            sheet1 = temp_dir / "sheet1.jpg"
            sheet2 = temp_dir / "sheet2.jpg"
            output = temp_dir / "_contact_sheet.jpg"
            generate_contact_sheets.Image.new("RGB", (100, 50), "white").save(sheet1)
            generate_contact_sheets.Image.new("RGB", (100, 40), "white").save(sheet2)

            generate_contact_sheets.combine_contact_sheets(
                [(sheet1, "Portrait 1"), (sheet2, "Portrait 2")],
                output,
                quality=90,
            )

            with generate_contact_sheets.Image.open(output) as image:
                self.assertEqual(image.size, (100, 50 + 40 + 2 * 82))

    def test_format_label_omits_index_by_default(self):
        label = generate_contact_sheets.format_label(Path("DSC0001.HIF"), 7, False)

        self.assertEqual(label, "DSC0001.HIF")

    def test_format_label_can_include_index(self):
        label = generate_contact_sheets.format_label(Path("DSC0001.HIF"), 7, True)

        self.assertEqual(label, "007 DSC0001.HIF")


if __name__ == "__main__":
    unittest.main()
