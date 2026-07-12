import csv
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from media_toolkit.commands import ratings_apply


class RatingsApplyTest(unittest.TestCase):
    def test_applies_reviewed_manifest_ratings_and_required_markers(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_file = root / "raw" / "DSC0001.ARW"
            raw_file.parent.mkdir()
            raw_file.write_text("raw", encoding="utf-8")
            manifest = root / "ratings.tsv"
            self._write_manifest(manifest, [("raw/DSC0001.ARW", "4")])

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = ratings_apply.main([str(root), "--manifest", str(manifest)])

            xmp_file = raw_file.with_suffix(".xmp")
            root_element = ET.fromstring(self._xmp_root_text(xmp_file.read_text(encoding="utf-8")))

        ns = {
            "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
            "xmp": "http://ns.adobe.com/xap/1.0/",
            "crs": "http://ns.adobe.com/camera-raw-settings/1.0/",
            "photoshop": "http://ns.adobe.com/photoshop/1.0/",
            "dc": "http://purl.org/dc/elements/1.1/",
            "xmpMM": "http://ns.adobe.com/xap/1.0/mm/",
        }
        description = root_element.find("rdf:RDF/rdf:Description", ns)
        self.assertEqual(exit_code, 0)
        self.assertEqual(description.get(f"{{{ns['xmp']}}}Rating"), "4")
        self.assertEqual(description.get(f"{{{ns['crs']}}}HasSettings"), "True")
        self.assertEqual(description.get(f"{{{ns['crs']}}}AlreadyApplied"), "False")
        self.assertEqual(description.get(f"{{{ns['photoshop']}}}SidecarForExtension"), "ARW")
        self.assertEqual(description.get(f"{{{ns['dc']}}}format"), "image/x-sony-arw")
        self.assertEqual(description.get(f"{{{ns['xmpMM']}}}PreservedFileName"), "DSC0001.ARW")

    def test_rejects_any_invalid_row_before_writing_sidecars(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            first = raw_dir / "DSC0001.ARW"
            second = raw_dir / "DSC0002.ARW"
            first.write_text("raw", encoding="utf-8")
            second.write_text("raw", encoding="utf-8")
            manifest = root / "ratings.tsv"
            self._write_manifest(
                manifest,
                [("raw/DSC0001.ARW", "4"), ("raw/DSC0002.ARW", "6")],
            )

            stderr = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                exit_code = ratings_apply.main([str(root), "--manifest", str(manifest)])

            first_xmp_exists = first.with_suffix(".xmp").exists()
            second_xmp_exists = second.with_suffix(".xmp").exists()

        self.assertEqual(exit_code, 2)
        self.assertFalse(first_xmp_exists)
        self.assertFalse(second_xmp_exists)
        self.assertIn("rating must be an integer from 0 to 5", stderr.getvalue())

    def test_rejects_manifest_path_that_escapes_or_resolves_outside_root(self):
        with TemporaryDirectory() as tmp:
            parent = Path(tmp)
            root = parent / "shoot"
            root.mkdir()
            outside = parent / "outside.ARW"
            outside.write_text("raw", encoding="utf-8")
            manifest = root / "ratings.tsv"
            self._write_manifest(manifest, [("../outside.ARW", "4")])

            stderr = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                exit_code = ratings_apply.main([str(root), "--manifest", str(manifest)])

        self.assertEqual(exit_code, 2)
        self.assertIn("outside the shoot directory", stderr.getvalue())

    def test_invalid_existing_xmp_is_detected_before_any_sidecar_is_written(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            first = raw_dir / "DSC0001.ARW"
            second = raw_dir / "DSC0002.ARW"
            first.write_text("raw", encoding="utf-8")
            second.write_text("raw", encoding="utf-8")
            second.with_suffix(".xmp").write_text(
                '<rdf:Description xmp:Rating="4" />',
                encoding="utf-8",
            )
            manifest = root / "ratings.tsv"
            self._write_manifest(
                manifest,
                [("raw/DSC0001.ARW", "4"), ("raw/DSC0002.ARW", "4")],
            )

            stderr = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                exit_code = ratings_apply.main([str(root), "--manifest", str(manifest)])

        self.assertEqual(exit_code, 2)
        self.assertFalse(first.with_suffix(".xmp").exists())
        self.assertIn("invalid existing XMP", stderr.getvalue())

    def test_default_rejects_manifest_that_omits_any_raw_even_with_stale_xmp(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            first = raw_dir / "DSC0001.ARW"
            omitted = raw_dir / "DSC0002.ARW"
            first.write_text("raw", encoding="utf-8")
            omitted.write_text("raw", encoding="utf-8")
            omitted_xmp = omitted.with_suffix(".xmp")
            omitted_xmp.write_text(
                '''<x:xmpmeta xmlns:x="adobe:ns:meta/"
 xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
 xmlns:xmp="http://ns.adobe.com/xap/1.0/">
 <rdf:RDF><rdf:Description xmp:Rating="5" /></rdf:RDF>
</x:xmpmeta>''',
                encoding="utf-8",
            )
            original = omitted_xmp.read_text(encoding="utf-8")
            manifest = root / "ratings.tsv"
            self._write_manifest(manifest, [("raw/DSC0001.ARW", "4")])

            stderr = StringIO()
            with redirect_stdout(StringIO()), redirect_stderr(stderr):
                exit_code = ratings_apply.main([str(root), "--manifest", str(manifest)])

            first_xmp_exists = first.with_suffix(".xmp").exists()
            omitted_text = omitted_xmp.read_text(encoding="utf-8")

        self.assertEqual(exit_code, 2)
        self.assertIn("omits 1 RAW", stderr.getvalue())
        self.assertFalse(first_xmp_exists)
        self.assertEqual(omitted_text, original)

    def test_allow_partial_is_explicit_for_targeted_rating_corrections(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            raw_dir = root / "raw"
            raw_dir.mkdir()
            first = raw_dir / "DSC0001.ARW"
            omitted = raw_dir / "DSC0002.ARW"
            first.write_text("raw", encoding="utf-8")
            omitted.write_text("raw", encoding="utf-8")
            manifest = root / "ratings.tsv"
            self._write_manifest(manifest, [("raw/DSC0001.ARW", "4")])

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = ratings_apply.main(
                    [
                        str(root),
                        "--manifest",
                        str(manifest),
                        "--allow-partial",
                    ]
                )

            first_xmp_exists = first.with_suffix(".xmp").exists()
            omitted_xmp_exists = omitted.with_suffix(".xmp").exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(first_xmp_exists)
        self.assertFalse(omitted_xmp_exists)

    def _write_manifest(self, path: Path, rows: list[tuple[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(["path", "rating"])
            writer.writerows(rows)

    def _xmp_root_text(self, text: str) -> str:
        start = text.index("<x:xmpmeta")
        end = text.index("</x:xmpmeta>") + len("</x:xmpmeta>")
        return text[start:end]


if __name__ == "__main__":
    unittest.main()
