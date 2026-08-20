import importlib.util
import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "korean_ocr_nodes_workflows", ROOT / "comfyui_korean_ocr_to_image.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class WorkflowFileTests(unittest.TestCase):
    def test_main_workflow_contains_batch_nodes_with_safe_defaults(self):
        workflow = json.loads((ROOT / "korean_ocr_to_image.workflow.json").read_text(encoding="utf-8"))
        nodes = {node["type"]: node for node in workflow["nodes"]}

        self.assertIn("KoreanBatchImagesToText", nodes)
        self.assertIn("KoreanBatchTextToImages", nodes)
        self.assertEqual(len(nodes["KoreanBatchImagesToText"]["widgets_values"]), 6)
        self.assertEqual(len(nodes["KoreanBatchTextToImages"]["widgets_values"]), 4)
        self.assertFalse(nodes["KoreanBatchImagesToText"]["widgets_values"][0])
        self.assertFalse(nodes["KoreanBatchTextToImages"]["widgets_values"][0])

    def test_every_custom_workflow_node_is_registered(self):
        for filename in ("korean_ocr_to_image.workflow.json",):
            workflow = json.loads((ROOT / filename).read_text(encoding="utf-8"))
            custom_types = {
                node["type"] for node in workflow["nodes"]
                if node["type"].startswith("Korean")
            }
            self.assertLessEqual(custom_types, set(MODULE.NODE_CLASS_MAPPINGS))


if __name__ == "__main__":
    unittest.main()
