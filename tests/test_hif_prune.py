import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

from media_toolkit.hif_prune import (
    HifPruneMode,
    PruneExecutionError,
    PrunePlanValidationError,
    apply_reviewed_prune_plan,
    build_prune_plan,
    execute_prune_plan,
)
from media_toolkit.commands import hif_prune as hif_prune_command


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

    def test_plan_protects_raw_backed_hif_for_every_supported_raw_extension(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0001.HIF", (120, 80, 40))
            self._write_hif(root / "hif" / "DSC0002.HIF", (120, 80, 40))
            (root / "raw").mkdir()
            (root / "raw" / "DSC0002.X3F").write_text("raw", encoding="utf-8")

            plan = build_prune_plan(root)

            protected = next(item for item in plan.keep if item.path.stem == "DSC0002")
            self.assertEqual(protected.reason, "raw-backed-hif")

    def test_plan_manifest_records_reviewable_file_identities(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0100.HIF", (200, 40, 40))
            self._write_hif(root / "hif" / "DSC0101.HIF", (200, 40, 40))
            manifest = root / "hif_prune_manifest.json"

            plan = build_prune_plan(root)
            result = execute_prune_plan(
                plan,
                mode=HifPruneMode.PLAN,
                manifest_path=manifest,
            )

            self.assertEqual(result.deleted_count, 0)
            self.assertTrue((root / "hif" / "DSC0100.HIF").exists())
            self.assertTrue((root / "hif" / "DSC0101.HIF").exists())
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "media-toolkit/hif-prune-plan")
            self.assertEqual(payload["version"], 1)
            self.assertEqual(payload["status"], "review-required")
            self.assertEqual(payload["root"], str(root.resolve()))
            candidate = payload["delete"][0]
            self.assertEqual(candidate["path"], "hif/DSC0101.HIF")
            self.assertGreater(candidate["size"], 0)
            self.assertEqual(len(candidate["sha256"]), 64)
            self.assertEqual(candidate["representative"]["path"], "hif/DSC0100.HIF")
            self.assertGreater(candidate["representative"]["size"], 0)
            self.assertEqual(len(candidate["representative"]["sha256"]), 64)

    def test_aggressive_applies_reviewed_manifest_without_rebuilding_plan(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            representative = root / "hif" / "DSC0100.HIF"
            candidate = root / "hif" / "DSC0101.HIF"
            self._write_hif(representative, (200, 40, 40))
            self._write_hif(candidate, (200, 40, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), patch(
                "media_toolkit.hif_prune.build_prune_plan",
                side_effect=AssertionError("reviewed apply must not rebuild"),
            ):
                result = apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    manifest_path=execution,
                    confirmed=True,
                )

            self.assertEqual(result.deleted_count, 1)
            self.assertTrue(representative.exists())
            self.assertFalse(candidate.exists())
            payload = json.loads(execution.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema"], "media-toolkit/hif-prune-execution")
            self.assertEqual(payload["status"], "completed")
            self.assertEqual(payload["delete"][0]["status"], "deleted")

    def test_aggressive_execution_requires_explicit_confirmation(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0110.HIF", (200, 40, 40))
            candidate = root / "hif" / "DSC0111.HIF"
            self._write_hif(candidate, (200, 40, 40))
            reviewed = root / "reviewed.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            with self.assertRaises(ValueError):
                apply_reviewed_prune_plan(reviewed, root=root)

            self.assertTrue(candidate.exists())

    def test_in_memory_plan_cannot_be_executed_aggressively(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0115.HIF", (200, 40, 40))
            candidate = root / "hif" / "DSC0116.HIF"
            self._write_hif(candidate, (200, 40, 40))

            with self.assertRaises(ValueError):
                execute_prune_plan(
                    build_prune_plan(root),
                    mode=HifPruneMode.AGGRESSIVE,
                    confirmed=True,
                )

            self.assertTrue(candidate.exists())

    def test_aggressive_execution_requires_heif_decoder(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0120.HIF", (200, 40, 40))
            candidate = root / "hif" / "DSC0121.HIF"
            self._write_hif(candidate, (200, 40, 40))
            reviewed = root / "reviewed.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=False,
            ), self.assertRaises(RuntimeError):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    confirmed=True,
                )

            self.assertTrue(candidate.exists())

    def test_command_defaults_to_plan_mode(self):
        args = hif_prune_command.parse_args(["/tmp/photos"])

        self.assertEqual(args.mode, HifPruneMode.PLAN.value)

    def test_command_rejects_aggressive_mode_without_confirmation(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0130.HIF", (200, 40, 40))
            candidate = root / "hif" / "DSC0131.HIF"
            self._write_hif(candidate, (200, 40, 40))

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = hif_prune_command.main(
                    [str(root), "--mode", "aggressive"]
                )

            self.assertEqual(exit_code, 2)
            self.assertTrue(candidate.exists())

    def test_command_rejects_aggressive_mode_without_reviewed_plan(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = hif_prune_command.main(
                    [str(root), "--mode", "aggressive", "--confirm-delete"]
                )

            self.assertEqual(exit_code, 2)

    def test_command_accepts_explicit_delete_confirmation_flag(self):
        try:
            args = hif_prune_command.parse_args(
                ["/tmp/photos", "--mode", "aggressive", "--confirm-delete"]
            )
        except SystemExit as exc:
            self.fail(f"confirmation flag was rejected with exit code {exc.code}")

        self.assertTrue(args.confirm_delete)

    def test_command_applies_reviewed_plan_and_writes_execution_audit(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0140.HIF", (200, 40, 40))
            candidate = root / "hif" / "DSC0141.HIF"
            self._write_hif(candidate, (200, 40, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = hif_prune_command.main(
                    [
                        str(root),
                        "--mode",
                        "aggressive",
                        "--apply-plan",
                        str(reviewed),
                        "--confirm-delete",
                        "--manifest",
                        str(execution),
                    ]
                )

            self.assertEqual(exit_code, 0)
            self.assertFalse(candidate.exists())
            self.assertEqual(
                json.loads(execution.read_text(encoding="utf-8"))["status"],
                "completed",
            )

    def test_command_rejects_non_object_plan_with_validation_audit(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            reviewed.write_text("[]", encoding="utf-8")

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                exit_code = hif_prune_command.main(
                    [
                        str(root),
                        "--mode",
                        "aggressive",
                        "--apply-plan",
                        str(reviewed),
                        "--confirm-delete",
                        "--manifest",
                        str(execution),
                    ]
                )

            self.assertNotEqual(exit_code, 0)
            payload = json.loads(execution.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "validation-failed")
            self.assertTrue(any("JSON object" in error for error in payload["errors"]))

    def test_execution_audit_cannot_overwrite_reviewed_plan(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0150.HIF", (200, 40, 40))
            candidate = root / "hif" / "DSC0151.HIF"
            self._write_hif(candidate, (200, 40, 40))
            reviewed = root / "reviewed.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), self.assertRaises(ValueError):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    manifest_path=reviewed,
                    confirmed=True,
                )

            self.assertTrue(candidate.exists())
            self.assertEqual(
                json.loads(reviewed.read_text(encoding="utf-8"))["schema"],
                "media-toolkit/hif-prune-plan",
            )

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

    def test_stale_candidate_aborts_batch_without_deleting_anything(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0300.HIF", (20, 160, 40))
            first = root / "hif" / "DSC0301.HIF"
            second = root / "hif" / "DSC0302.HIF"
            self._write_hif(first, (20, 160, 40))
            self._write_hif(second, (20, 160, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            self._write_hif(second, (160, 20, 40))

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), self.assertRaises(PrunePlanValidationError):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    manifest_path=execution,
                    confirmed=True,
                )

            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            payload = json.loads(execution.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "validation-failed")
            self.assertTrue(all(item["status"] == "not-attempted" for item in payload["delete"]))

    def test_new_export_protection_makes_reviewed_plan_stale(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0310.HIF", (20, 160, 40))
            candidate = root / "hif" / "DSC0311.HIF"
            self._write_hif(candidate, (20, 160, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            export = root / "raw" / "Export" / "DSC0311.jpg"
            export.parent.mkdir(parents=True)
            export.write_text("selected", encoding="utf-8")

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), self.assertRaises(PrunePlanValidationError):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    manifest_path=execution,
                    confirmed=True,
                )

            self.assertTrue(candidate.exists())
            self.assertEqual(
                json.loads(execution.read_text(encoding="utf-8"))["status"],
                "validation-failed",
            )

    def test_new_sibling_raw_protection_makes_reviewed_plan_stale(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0315.HIF", (20, 160, 40))
            candidate = root / "hif" / "DSC0316.HIF"
            self._write_hif(candidate, (20, 160, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            raw = root / "raw" / "DSC0316.ARW"
            raw.parent.mkdir(parents=True)
            raw.write_text("source", encoding="utf-8")

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), self.assertRaises(PrunePlanValidationError):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    manifest_path=execution,
                    confirmed=True,
                )

            self.assertTrue(candidate.exists())

    def test_reviewed_plan_root_mismatch_aborts_without_deleting(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / "photos"
            self._write_hif(root / "hif" / "DSC0317.HIF", (20, 160, 40))
            candidate = root / "hif" / "DSC0318.HIF"
            self._write_hif(candidate, (20, 160, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), self.assertRaises(PrunePlanValidationError):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=workspace,
                    manifest_path=execution,
                    confirmed=True,
                )

            self.assertTrue(candidate.exists())

    def test_modified_representative_aborts_batch_without_deleting(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            representative = root / "hif" / "DSC0320.HIF"
            candidate = root / "hif" / "DSC0321.HIF"
            self._write_hif(representative, (20, 160, 40))
            self._write_hif(candidate, (20, 160, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            self._write_hif(representative, (160, 20, 40))

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), self.assertRaises(PrunePlanValidationError):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    manifest_path=execution,
                    confirmed=True,
                )

            self.assertTrue(candidate.exists())

    def test_delete_candidate_cannot_serve_as_another_items_representative(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0325.HIF", (20, 160, 40))
            first = root / "hif" / "DSC0326.HIF"
            second = root / "hif" / "DSC0327.HIF"
            self._write_hif(first, (20, 160, 40))
            self._write_hif(second, (20, 160, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            payload = json.loads(reviewed.read_text(encoding="utf-8"))
            replacement = payload["delete"][1]
            payload["delete"][0]["representative"] = {
                "path": replacement["path"],
                "size": replacement["size"],
                "sha256": replacement["sha256"],
            }
            reviewed.write_text(json.dumps(payload), encoding="utf-8")

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), self.assertRaises(PrunePlanValidationError):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    manifest_path=execution,
                    confirmed=True,
                )

            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_path_escape_in_reviewed_plan_aborts_without_deleting(self):
        with TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            root = workspace / "photos"
            outside = workspace / "outside.HIF"
            self._write_hif(root / "hif" / "DSC0330.HIF", (20, 160, 40))
            candidate = root / "hif" / "DSC0331.HIF"
            self._write_hif(candidate, (20, 160, 40))
            self._write_hif(outside, (20, 160, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            payload = json.loads(reviewed.read_text(encoding="utf-8"))
            payload["delete"][0]["path"] = "../outside.HIF"
            reviewed.write_text(json.dumps(payload), encoding="utf-8")

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), self.assertRaises(PrunePlanValidationError):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    manifest_path=execution,
                    confirmed=True,
                )

            self.assertTrue(candidate.exists())
            self.assertTrue(outside.exists())

    def test_delete_failure_updates_atomic_execution_audit_and_stops(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0340.HIF", (20, 160, 40))
            first = root / "hif" / "DSC0341.HIF"
            failed = root / "hif" / "DSC0342.HIF"
            not_attempted = root / "hif" / "DSC0343.HIF"
            for candidate in (first, failed, not_attempted):
                self._write_hif(candidate, (20, 160, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            original_unlink = Path.unlink

            def flaky_unlink(path: Path, *args, **kwargs):
                if path.name == failed.name:
                    raise OSError("simulated delete failure")
                return original_unlink(path, *args, **kwargs)

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), patch.object(Path, "unlink", flaky_unlink), self.assertRaises(
                PruneExecutionError
            ):
                apply_reviewed_prune_plan(
                    reviewed,
                    root=root,
                    manifest_path=execution,
                    confirmed=True,
                )

            self.assertFalse(first.exists())
            self.assertTrue(failed.exists())
            self.assertTrue(not_attempted.exists())
            payload = json.loads(execution.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "partial-failure")
            self.assertEqual(
                [item["status"] for item in payload["delete"]],
                ["deleted", "failed", "not-attempted"],
            )

    def test_delete_io_failure_returns_nonzero_from_cli(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_hif(root / "hif" / "DSC0350.HIF", (20, 160, 40))
            self._write_hif(root / "hif" / "DSC0351.HIF", (20, 160, 40))
            failed = root / "hif" / "DSC0352.HIF"
            not_attempted = root / "hif" / "DSC0353.HIF"
            self._write_hif(failed, (20, 160, 40))
            self._write_hif(not_attempted, (20, 160, 40))
            reviewed = root / "reviewed.json"
            execution = root / "execution.json"
            execute_prune_plan(
                build_prune_plan(root),
                mode=HifPruneMode.PLAN,
                manifest_path=reviewed,
            )
            original_unlink = Path.unlink

            def flaky_unlink(path: Path, *args, **kwargs):
                if path.name == failed.name:
                    raise OSError("simulated delete failure")
                return original_unlink(path, *args, **kwargs)

            with patch(
                "media_toolkit.hif_prune.heif_decoder_available",
                return_value=True,
            ), patch.object(Path, "unlink", flaky_unlink), redirect_stdout(
                StringIO()
            ), redirect_stderr(StringIO()):
                exit_code = hif_prune_command.main(
                    [
                        str(root),
                        "--mode",
                        "aggressive",
                        "--apply-plan",
                        str(reviewed),
                        "--confirm-delete",
                        "--manifest",
                        str(execution),
                    ]
                )

            self.assertNotEqual(exit_code, 0)
            self.assertTrue(failed.exists())
            self.assertTrue(not_attempted.exists())
            payload = json.loads(execution.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "partial-failure")
            self.assertEqual(payload["delete"][-1]["status"], "not-attempted")

    def test_noncanonical_backup_hif_is_reported_but_never_delete_candidate(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            self._write_hif(root / "hif" / "DSC0400.HIF", (20, 160, 40))
            self._write_hif(root / "hif" / "DSC0401.HIF", (20, 160, 40))
            backup = root / "backup" / "hif" / "DSC0402.HIF"
            panorama = root / "panorama" / "1" / "hif" / "DSC0403.HIF"
            self._write_hif(backup, (20, 160, 40))
            self._write_hif(panorama, (20, 160, 40))

            plan = build_prune_plan(root)

            self.assertNotIn(backup.resolve(), {item.path for item in plan.delete})
            self.assertTrue(
                any(
                    item.path == backup.resolve()
                    and item.reason == "noncanonical-hif-kept"
                    for item in plan.warnings
                )
            )
            self.assertTrue(
                any(
                    item.path == panorama.resolve()
                    and item.reason == "panorama-source-hif"
                    for item in plan.keep
                )
            )

    def test_duplicate_detection_never_crosses_canonical_workflow_roots(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for scene, stem in (("scene-a", "DSC0500"), ("scene-b", "DSC0501")):
                (root / scene / "raw").mkdir(parents=True)
                self._write_hif(
                    root / scene / "hif" / f"{stem}.HIF",
                    (20, 160, 40),
                )

            plan = build_prune_plan(root)

            self.assertEqual(plan.delete, [])
            self.assertEqual(
                {item.path.parent for item in plan.keep},
                {
                    (root / "scene-a" / "hif").resolve(),
                    (root / "scene-b" / "hif").resolve(),
                },
            )

    def test_nested_ordinary_scene_base_remains_canonical(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "raw").mkdir()
            (root / "lake-valley" / "raw").mkdir(parents=True)
            for path in (
                root / "hif" / "DSC0600.HIF",
                root / "hif" / "DSC0601.HIF",
                root / "lake-valley" / "hif" / "DSC0700.HIF",
                root / "lake-valley" / "hif" / "DSC0701.HIF",
            ):
                self._write_hif(path, (20, 160, 40))

            plan = build_prune_plan(root)

            self.assertEqual(
                {item.path.name for item in plan.delete},
                {"DSC0601.HIF", "DSC0701.HIF"},
            )

    def _write_hif(self, path: Path, color: tuple[int, int, int]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (24, 16), color)
        image.save(path, format="JPEG")


if __name__ == "__main__":
    unittest.main()
