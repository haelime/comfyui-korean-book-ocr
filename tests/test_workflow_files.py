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
        self.assertEqual(len(nodes["KoreanBatchTextToImages"]["widgets_values"]), 3)
        self.assertFalse(nodes["KoreanBatchImagesToText"]["widgets_values"][0])
        self.assertFalse(nodes["KoreanBatchTextToImages"]["widgets_values"][0])
        path_links = [link for link in workflow["links"] if link[5] == "STRING" and link[1] == nodes["KoreanBatchImagesToText"]["id"]]
        self.assertIn([13, 13, 1, 14, 1, "STRING"], path_links)

    def test_every_custom_workflow_node_is_registered(self):
        for filename in ("korean_ocr_to_image.workflow.json",):
            workflow = json.loads((ROOT / filename).read_text(encoding="utf-8"))
            custom_types = {
                node["type"] for node in workflow["nodes"]
                if node["type"].startswith("Korean")
            }
            self.assertLessEqual(custom_types, set(MODULE.NODE_CLASS_MAPPINGS))

    def test_desktop_docs_do_not_point_batch_users_at_install_local_input(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        workflow_doc = (ROOT / "docs" / "WORKFLOW.ko.md").read_text(encoding="utf-8")
        installer = (ROOT / "scripts" / "install_windows.ps1").read_text(encoding="utf-8")

        self.assertNotIn("ComfyUI/input/대량_OCR_사진", readme)
        self.assertNotIn("ComfyUI/input/대량_OCR_사진", workflow_doc)
        self.assertIn("ComfyUI-Shared", installer)


if __name__ == "__main__":
    unittest.main()
