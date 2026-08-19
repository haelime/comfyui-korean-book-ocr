import importlib.util
import json
import pathlib
import unittest
from unittest.mock import MagicMock, patch


MODULE_PATH = pathlib.Path(__file__).parents[1] / "comfyui_korean_ocr_to_image.py"
SPEC = importlib.util.spec_from_file_location("korean_ocr_nodes_ai", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AICorrectionPromptTests(unittest.TestCase):
    def test_precise_mode_requests_two_pass_typo_review(self):
        def context_for(payload):
            response = MagicMock()
            response.read.return_value = json.dumps({
                "response": json.dumps(payload, ensure_ascii=False),
            }, ensure_ascii=False).encode("utf-8")
            context = MagicMock()
            context.__enter__.return_value = response
            return context

        responses = [
            context_for({"corrected_text": "봄비가 조용이 내렸다."}),
            context_for({"corrected_text": "봄비가 조용히 내렸다."}),
            context_for({"recommended_markdown": "~~봄비가 조용히 내렸다.~~"}),
        ]

        with patch.object(MODULE.urllib.request, "urlopen", side_effect=responses) as call:
            recommended, corrected, _ = MODULE.KoreanOCRAutoCorrect().교정(
                "봄비가 조용이 내렸다.", True, "qwen3:8b", "정밀", True,
                "http://127.0.0.1:11434", 180,
            )

        self.assertEqual(call.call_count, 3)
        payloads = [json.loads(item.args[0].data.decode("utf-8")) for item in call.call_args_list]
        self.assertIn("음절 누락", payloads[0]["prompt"])
        self.assertIn("독립 검수", payloads[1]["prompt"])
        self.assertIn("모든 여는 꾸밈 기호", payloads[2]["prompt"])
        self.assertTrue(all(item["options"]["temperature"] == 0 for item in payloads))
        self.assertEqual(corrected, "봄비가 조용히 내렸다.")
        self.assertEqual(recommended, "~~봄비가 조용히 내렸다.~~")

    def test_precise_mode_is_the_default_choice(self):
        correction_config = MODULE.KoreanOCRAutoCorrect.INPUT_TYPES()["required"]["교정_강도"]
        self.assertEqual(correction_config[1]["default"], "정밀")

    def test_decoration_that_changes_body_text_is_retried(self):
        def context_for(payload):
            response = MagicMock()
            response.read.return_value = json.dumps({
                "response": json.dumps(payload, ensure_ascii=False),
            }, ensure_ascii=False).encode("utf-8")
            context = MagicMock()
            context.__enter__.return_value = response
            return context

        responses = [
            context_for({"corrected_text": "봄비가 조용히 내렸다."}),
            context_for({"recommended_markdown": "봄비가 조용히 내렸다. __색연필 밑줄__"}),
            context_for({"recommended_markdown": "~~봄비가 조용히 내렸다.~~"}),
        ]

        with patch.object(MODULE.urllib.request, "urlopen", side_effect=responses) as call:
            recommended, corrected, _ = MODULE.KoreanOCRAutoCorrect().교정(
                "봄비가 조용이 내렸다.", True, "qwen3:8b", "보수적", True,
                "http://127.0.0.1:11434", 180,
            )

        self.assertEqual(call.call_count, 3)
        self.assertEqual(corrected, "봄비가 조용히 내렸다.")
        self.assertEqual(recommended, "~~봄비가 조용히 내렸다.~~")

    def test_orphan_footnote_is_not_a_valid_recommendation(self):
        source = "봄비가 조용히 내렸다."
        self.assertFalse(MODULE._markdown_preserves_source(source + "\n\n[^1]: 댓글", source))
        self.assertEqual(
            MODULE._sanitize_markdown_recommendation(source + "\n\n[^1]: 댓글"),
            source,
        )
        self.assertTrue(MODULE._markdown_preserves_source("~~" + source + "~~", source))


if __name__ == "__main__":
    unittest.main()
