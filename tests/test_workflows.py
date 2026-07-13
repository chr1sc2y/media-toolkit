import unittest

from media_toolkit.workflows import (
    get_workflow,
    load_workflow_registry,
    list_workflows,
    render_workflow_detail,
    render_workflow_summary,
    workflow_choices,
    workflow_ids,
)


class WorkflowsTest(unittest.TestCase):
    def test_registry_lists_agent_facing_workflows(self):
        registry = load_workflow_registry()
        workflow_ids = {workflow["id"] for workflow in list_workflows()}

        self.assertEqual(registry["version"], 1)
        self.assertIn("initial-cull", workflow_ids)
        self.assertIn("finalize", workflow_ids)
        self.assertIn("learn-style", workflow_ids)
        self.assertIn("apple-photos-location-fill", workflow_ids)

    def test_workflow_choices_are_registry_derived(self):
        self.assertEqual(
            set(workflow_ids()),
            {
                "initial-cull",
                "finalize",
                "learn-style",
                "apple-photos-location-fill",
            },
        )
        self.assertEqual(
            set(workflow_choices(include_auto=True)),
            {"auto", "initial-cull", "finalize", "learn-style"},
        )

    def test_apple_photos_location_workflow_requires_reviewed_apply_plan(self):
        workflow = get_workflow("apple-photos-location-fill")

        self.assertFalse(workflow["source_path_required"])
        self.assertIn("--apply-plan", workflow["apply_command"])
        self.assertIn("timestamp-based", " ".join(workflow["must_not"]))
        self.assertIn("--apply-plan", render_workflow_detail(workflow))

    def test_registry_references_real_mt_commands(self):
        all_text = "\n".join(
            str(value)
            for workflow in list_workflows()
            for value in workflow.values()
        )

        self.assertIn("mt preflight-run", all_text)
        self.assertIn("mt learn-style", all_text)
        self.assertIn("mt ratings-apply", all_text)

    def test_finalize_workflow_requires_explicit_external_destination(self):
        workflow = get_workflow("finalize")

        self.assertTrue(workflow["source_path_required"])
        self.assertTrue(workflow["destination_path_required"])
        must_not = " ".join(workflow["must_not"]).lower()
        self.assertIn("single provided path", must_not)
        self.assertIn("featured", must_not)
        self.assertIn("--copy-to", " ".join(workflow["preflight"]))
        self.assertIn("mt preflight-run", " ".join(workflow["preflight"]))
        self.assertIn("mt status", " ".join(workflow["preflight"]))
        self.assertIn("mt doctor", " ".join(workflow["preflight"]))
        self.assertIn("mt hif-prune", workflow["default_behavior"])
        self.assertIn("plan", workflow["default_behavior"])
        self.assertIn("--confirm-delete", workflow["default_behavior"])
        self.assertIn("--apply-plan", workflow["default_behavior"])
        self.assertNotIn("by default", workflow["default_behavior"].lower())
        self.assertIn("mt hif-prune", " ".join(workflow["preflight"]))

    def test_summary_includes_chinese_workflow_names(self):
        summary = render_workflow_summary()

        self.assertIn("初筛", summary)
        self.assertIn("成片归档", summary)
        self.assertIn("学习调色", summary)

    def test_detail_includes_preflight_and_agent_notes(self):
        detail = render_workflow_detail(get_workflow("initial-cull"))

        self.assertIn("preflight:", detail)
        self.assertIn("mt status", detail)
        self.assertIn("mt doctor", detail)
        self.assertIn("agent notes:", detail)

    def test_initial_cull_workflow_includes_per_image_portrait_subject_review(self):
        workflow = get_workflow("initial-cull")
        all_text = " ".join(str(value) for value in workflow.values())

        self.assertIn("mt subject-plan", all_text)
        self.assertIn("mt subject-apply", all_text)
        self.assertIn("strict 4- and 5-star", all_text)
        self.assertIn("broad 3-star", all_text)
        self.assertIn("individual HIF/HEIF/HEIC", all_text)

    def test_learn_style_points_to_style_registry(self):
        detail = render_workflow_detail(get_workflow("learn-style"))

        self.assertIn("mt styles", detail)
        self.assertIn("--baseline", detail)


if __name__ == "__main__":
    unittest.main()
