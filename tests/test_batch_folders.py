import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image


MODULE_PATH = pathlib.Path(__file__).parents[1] / "comfyui_korean_ocr_to_image.py"
SPEC = importlib.util.spec_from_file_location("korean_ocr_nodes_batch", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class BatchFolderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = pathlib.Path(self.temporary.name)
        self.input_root = self.root / "input"
        self.output_root = self.root / "output"
        self.input_root.mkdir()
        self.output_root.mkdir()
        self.directory_patch = patch.object(
            MODULE,
            "_comfy_directory",
            side_effect=lambda kind: self.input_root if kind == "input" else self.output_root,
        )
        self.directory_patch.start()

    def tearDown(self):
        self.directory_patch.stop()
        self.temporary.cleanup()

    def test_photos_create_one_corrected_text_file_each_and_protect_edits(self):
        photo_folder = self.input_root / "대량_OCR_사진"
        (photo_folder / "둘째").mkdir(parents=True)
        Image.new("RGB", (32, 24), "white").save(photo_folder / "첫째.jpg")
        Image.new("RGB", (32, 24), "white").save(photo_folder / "둘째" / "페이지.png")

        with patch.object(MODULE.KoreanOCR, "recognize", return_value=("오씨알 원문",)), patch.object(
            MODULE.KoreanOCRAutoCorrect, "교정", return_value=("교정된 문장", "오씨알 원문")
        ):
            result = MODULE.KoreanBatchImagesToText().process_folder(
                True, "대량_OCR_사진", "korean_book_ocr/text", True, False, True,
            )

        text_root = self.output_root / "korean_book_ocr" / "text"
        self.assertEqual((text_root / "첫째.txt").read_text(encoding="utf-8"), "교정된 문장\n")
        self.assertEqual((text_root / "둘째" / "페이지.txt").read_text(encoding="utf-8"), "교정된 문장\n")
        self.assertIn("텍스트 2개 생성", result["result"][0])

        (text_root / "첫째.txt").write_text("사람이 수정한 문장\n", encoding="utf-8")
        with patch.object(MODULE.KoreanOCR, "recognize", side_effect=AssertionError("OCR 재실행 금지")):
            result = MODULE.KoreanBatchImagesToText().process_folder(
                True, "대량_OCR_사진", "korean_book_ocr/text", True, False, False,
            )
        self.assertEqual((text_root / "첫째.txt").read_text(encoding="utf-8"), "사람이 수정한 문장\n")
        self.assertIn("기존 파일 2개 보호", result["result"][0])

    def test_each_text_file_creates_one_png(self):
        text_root = self.output_root / "korean_book_ocr" / "text"
        (text_root / "아래").mkdir(parents=True)
        (text_root / "첫째.txt").write_text("__첫 문장__", encoding="utf-8")
        (text_root / "아래" / "둘째.txt").write_text("~~둘째 문장~~", encoding="utf-8")
        style = {
            "width": 512,
            "font_size": 28,
            "comment_font_size": 20,
            "padding": 32,
            "line_spacing": 12,
            "font_path": "AUTO",
            "comment_font_path": "AUTO",
            "text_color": "#202020",
            "pencil_color": "#C63B3B",
            "highlight_color": "#FFF176",
            "background_color": "#FFFDF7",
        }

        result = MODULE.KoreanBatchTextToImages().render_folder(
            style, True, "korean_book_ocr/text", "korean_book_ocr/images", True,
        )

        image_root = self.output_root / "korean_book_ocr" / "images"
        self.assertTrue((image_root / "첫째.png").is_file())
        self.assertTrue((image_root / "아래" / "둘째.png").is_file())
        self.assertIn("이미지 2개 생성", result["result"][0])
        self.assertEqual(tuple(result["result"][1].shape[:1]), (1,))

    def test_ocr_text_is_saved_when_local_ai_is_unavailable(self):
        photo_folder = self.input_root / "사진"
        photo_folder.mkdir()
        Image.new("RGB", (32, 24), "white").save(photo_folder / "페이지.jpg")

        with patch.object(MODULE.KoreanOCR, "recognize", return_value=("OCR 원문",)), patch.object(
            MODULE.KoreanOCRAutoCorrect, "교정", side_effect=RuntimeError("Ollama 연결 실패")
        ):
            result = MODULE.KoreanBatchImagesToText().process_folder(
                True, "사진", "텍스트", True, False, True,
            )

        self.assertEqual((self.output_root / "텍스트" / "페이지.txt").read_text(encoding="utf-8"), "OCR 원문\n")
        self.assertIn("AI 교정 경고 1개", result["result"][0])


if __name__ == "__main__":
    unittest.main()
