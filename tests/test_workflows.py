import unittest

from media_toolkit.workflows import (
    get_workflow,
    load_workflow_registry,
    list_workflows,
    render_workflow_detail,
    render_workflow_summary,
)


class WorkflowsTest(unittest.TestCase):
    def test_registry_lists_agent_facing_workflows(self):
        registry = load_workflow_registry()
        workflow_ids = {workflow["id"] for workflow in list_workflows()}

        self.assertEqual(registry["version"], 1)
        self.assertIn("initial-cull", workflow_ids)
        self.assertIn("finalize", workflow_ids)
        self.assertIn("learn-style", workflow_ids)

    def test_registry_references_real_mt_commands(self):
        all_text = "\n".join(
            str(value)
            for workflow in list_workflows()
            for value in workflow.values()
        )

        self.assertIn("mt preflight-run", all_text)
        self.assertIn("mt learn-style", all_text)

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

    def test_learn_style_points_to_style_registry(self):
        detail = render_workflow_detail(get_workflow("learn-style"))

        self.assertIn("mt styles", detail)


if __name__ == "__main__":
    unittest.main()
