import importlib.util
import json
import pathlib
import unittest
from unittest.mock import MagicMock, patch


MODULE_PATH = pathlib.Path(__file__).parents[1] / "comfyui_korean_ocr_to_image.py"
SPEC = importlib.util.spec_from_file_location("korean_ocr_nodes_ai", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def context_for(payload):
    response = MagicMock()
    response.read.return_value = json.dumps({
        "response": json.dumps(payload, ensure_ascii=False),
    }, ensure_ascii=False).encode("utf-8")
    context = MagicMock()
    context.__enter__.return_value = response
    return context


class AICorrectionPromptTests(unittest.TestCase):
    def test_precise_mode_uses_two_correction_passes_only(self):
        responses = [
            context_for({"corrected_text": "봄비가 조용이 내렸다."}),
            context_for({"corrected_text": "봄비가 조용히 내렸다."}),
        ]

        with patch.object(MODULE.urllib.request, "urlopen", side_effect=responses) as call:
            corrected, original = MODULE.KoreanOCRAutoCorrect().교정(
                "봄비가 조용이 내렸다.", True, "qwen3:8b", "정밀", True,
                "http://127.0.0.1:11434", 180,
            )

        self.assertEqual(call.call_count, 2)
        payloads = [json.loads(item.args[0].data.decode("utf-8")) for item in call.call_args_list]
        self.assertIn("음절 누락", payloads[0]["prompt"])
        self.assertIn("독립 검수", payloads[1]["prompt"])
        self.assertNotIn("recommended_markdown", json.dumps(payloads, ensure_ascii=False))
        self.assertTrue(all(item["options"]["temperature"] == 0 for item in payloads))
        self.assertEqual(corrected, "봄비가 조용히 내렸다.")
        self.assertEqual(original, "봄비가 조용이 내렸다.")

    def test_precise_mode_is_the_default_choice(self):
        correction_config = MODULE.KoreanOCRAutoCorrect.INPUT_TYPES()["required"]["교정_강도"]
        self.assertEqual(correction_config[1]["default"], "정밀")


if __name__ == "__main__":
    unittest.main()
