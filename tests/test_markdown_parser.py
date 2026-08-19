import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "comfyui_korean_ocr_to_image.py"
SPEC = importlib.util.spec_from_file_location("korean_ocr_nodes", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MultilineMarkdownTests(unittest.TestCase):
    def test_each_supported_style_can_cross_a_source_line(self):
        cases = {
            "underline": "__첫 줄\n둘째 줄__",
            "italic": "*첫 줄\n둘째 줄*",
            "highlight": "~~첫 줄\n둘째 줄~~",
        }

        for expected_style, source in cases.items():
            with self.subTest(style=expected_style):
                lines, _ = MODULE._parse_markdown_document(source)
                self.assertEqual(len(lines), 2)
                self.assertEqual(
                    [[token["style"] for token in line] for line in lines],
                    [[expected_style], [expected_style]],
                )

    def test_multiline_style_keeps_following_footnote_reference(self):
        source = "__첫 줄\n둘째 줄__[^1]\n\n[^1]: 여러 줄 밑줄 댓글"
        lines, footnotes = MODULE._parse_markdown_document(source)

        self.assertEqual(lines[0][0], {"style": "underline", "text": "첫 줄"})
        self.assertEqual(lines[1][0], {"style": "underline", "text": "둘째 줄"})
        self.assertEqual(lines[1][1], {"style": "reference", "text": "1"})
        self.assertEqual(footnotes, {"1": "여러 줄 밑줄 댓글"})


if __name__ == "__main__":
    unittest.main()
