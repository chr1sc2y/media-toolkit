import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from media_toolkit.commands import manifest_template


class ManifestTemplateTest(unittest.TestCase):
    def test_collect_paired_stems_uses_only_root_raw_hif_pairs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "portrait/1/raw").mkdir(parents=True)
            (root / "portrait/1/hif").mkdir(parents=True)
            (root / "raw/DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif/DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "raw/DSC0002.ARW").write_text("raw", encoding="utf-8")
            (root / "portrait/1/raw/DSC9999.ARW").write_text("raw", encoding="utf-8")
            (root / "portrait/1/hif/DSC9999.HIF").write_text("hif", encoding="utf-8")

            result = manifest_template.collect_paired_stems(root)

        self.assertEqual(result.paired, ["DSC0001"])
        self.assertEqual(result.raw_only, ["DSC0002"])
        self.assertEqual(result.hif_only, [])

    def test_collect_paired_stems_accepts_case_insensitive_heif_extensions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw/DSC0001.arw").write_text("raw", encoding="utf-8")
            (root / "hif/DSC0001.heic").write_text("heif", encoding="utf-8")

            result = manifest_template.collect_paired_stems(root)

        self.assertEqual(result.paired, ["DSC0001"])
        self.assertEqual(result.raw_only, [])
        self.assertEqual(result.hif_only, [])

    def test_collect_paired_stems_accepts_supported_non_sony_raw_extensions(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw/FUJI0001.RAF").write_text("raw", encoding="utf-8")
            (root / "hif/FUJI0001.HEIF").write_text("heif", encoding="utf-8")

            result = manifest_template.collect_paired_stems(root)

        self.assertEqual(result.paired, ["FUJI0001"])
        self.assertEqual(result.raw_only, [])
        self.assertEqual(result.hif_only, [])

    def test_collect_paired_stems_uses_the_complete_supported_raw_registry(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw/SIGMA0001.X3F").write_text("raw", encoding="utf-8")
            (root / "hif/SIGMA0001.HIF").write_text("hif", encoding="utf-8")

            result = manifest_template.collect_paired_stems(root)

        self.assertEqual(result.paired, ["SIGMA0001"])
        self.assertEqual(result.raw_only, [])
        self.assertEqual(result.hif_only, [])

    def test_default_manifest_path_uses_kind_directory(self):
        root = Path("/photos/shoot")

        self.assertEqual(
            manifest_template.default_manifest_path(root, "portrait"),
            root / "portrait" / "portrait_manifest.tsv",
        )
        self.assertEqual(
            manifest_template.default_manifest_path(root, "panorama"),
            root / "panorama" / "panorama_manifest.tsv",
        )

    def test_write_template_creates_blank_group_rows(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "portrait" / "portrait_manifest.tsv"

            manifest_template.write_template(output, ["DSC0001", "DSC0002"])

            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "stem\tgroup\nDSC0001\t\nDSC0002\t\n",
            )

    def test_write_template_preserves_existing_group_assignments(self):
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "portrait" / "portrait_manifest.tsv"
            output.parent.mkdir()
            output.write_text("stem\tgroup\nDSC0001\t1\n", encoding="utf-8")

            manifest_template.write_template(
                output,
                ["DSC0001", "DSC0002"],
                preserve_existing=True,
            )

            self.assertEqual(
                output.read_text(encoding="utf-8"),
                "stem\tgroup\nDSC0001\t1\nDSC0002\t\n",
            )

    def test_generate_template_writes_default_portrait_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "raw/DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif/DSC0001.HIF").write_text("hif", encoding="utf-8")
            args = manifest_template.parse_args([str(root), "--kind", "portrait"])

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = manifest_template.generate_template(args)

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / "portrait/portrait_manifest.tsv").exists())

    def test_generate_template_does_not_overwrite_without_force_or_preserve(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "hif").mkdir()
            (root / "portrait").mkdir()
            (root / "raw/DSC0001.ARW").write_text("raw", encoding="utf-8")
            (root / "hif/DSC0001.HIF").write_text("hif", encoding="utf-8")
            (root / "portrait/portrait_manifest.tsv").write_text(
                "stem\tgroup\nDSC0001\t1\n", encoding="utf-8"
            )
            args = manifest_template.parse_args([str(root), "--kind", "portrait"])

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = manifest_template.generate_template(args)

            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
