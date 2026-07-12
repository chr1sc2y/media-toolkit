import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from media_toolkit.hif_prune import (
    HifPruneMode,
    build_prune_plan,
    execute_prune_plan,
)


class HifPruneTest(unittest.TestCase):
    def test_plan_keeps_exports_raw_backed_and_panorama_hifs(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0001.HIF", (120, 80, 40))
            self._write_hif(root / "hif" / "DSC0002.HIF", (120, 80, 40))
            self._write_hif(root / "hif" / "DSC0003.HIF", (10, 100, 180))
            self._write_hif(root / "panorama" / "1" / "hif" / "DSC0004.HIF", (120, 80, 40))
            (root / "raw" / "Export").mkdir(parents=True)
            (root / "raw" / "Export" / "DSC0001.jpg").write_text("export", encoding="utf-8")
            (root / "raw" / "DSC0003.ARW").write_text("raw", encoding="utf-8")

            plan = build_prune_plan(root)

            delete_names = {item.path.name for item in plan.delete}
            keep_names = {item.path.name for item in plan.keep}
            self.assertEqual(delete_names, {"DSC0002.HIF"})
            self.assertIn("DSC0001.HIF", keep_names)
            self.assertIn("DSC0003.HIF", keep_names)
            self.assertIn("DSC0004.HIF", keep_names)

    def test_execute_aggressive_deletes_only_planned_candidates_and_writes_manifest(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0100.HIF", (200, 40, 40))
            self._write_hif(root / "hif" / "DSC0101.HIF", (200, 40, 40))
            manifest = root / "hif_prune_manifest.json"

            plan = build_prune_plan(root)
            result = execute_prune_plan(
                plan,
                mode=HifPruneMode.AGGRESSIVE,
                manifest_path=manifest,
            )

            self.assertEqual(result.deleted_count, 1)
            self.assertTrue((root / "hif" / "DSC0100.HIF").exists())
            self.assertFalse((root / "hif" / "DSC0101.HIF").exists())
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "aggressive")
            self.assertEqual(payload["deleted_count"], 1)
            self.assertEqual(payload["delete"][0]["path"], "hif/DSC0101.HIF")

    def test_dry_run_writes_manifest_without_deleting(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0200.HIF", (20, 160, 40))
            self._write_hif(root / "hif" / "DSC0201.HIF", (20, 160, 40))
            manifest = root / "hif_prune_manifest.json"

            plan = build_prune_plan(root)
            result = execute_prune_plan(
                plan,
                mode=HifPruneMode.PLAN,
                manifest_path=manifest,
                dry_run=True,
            )

            self.assertEqual(result.deleted_count, 0)
            self.assertTrue((root / "hif" / "DSC0201.HIF").exists())
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["delete"][0]["action"], "would-delete")

    def _write_hif(self, path: Path, color: tuple[int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (24, 16), color)
        image.save(path, format="JPEG")


if __name__ == "__main__":
    unittest.main()
