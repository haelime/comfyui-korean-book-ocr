import importlib.util
import pathlib
import unittest

import numpy as np
from PIL import Image, ImageDraw


MODULE_PATH = pathlib.Path(__file__).parents[1] / "comfyui_korean_ocr_to_image.py"
SPEC = importlib.util.spec_from_file_location("korean_ocr_nodes_pencil", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PencilTextureTests(unittest.TestCase):
    def draw_sample(self, seed_text):
        canvas = Image.new("RGBA", (260, 40), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas, "RGBA")
        MODULE._draw_colored_pencil_underline(
            draw, 10, 20, 230, (198, 59, 59), 48, seed_text
        )
        return np.asarray(canvas)

    def test_texture_is_deterministic_for_the_same_phrase(self):
        np.testing.assert_array_equal(self.draw_sample("0:같은 문장"), self.draw_sample("0:같은 문장"))

    def test_texture_contains_varied_pressure_and_pigment_grain(self):
        image = self.draw_sample("0:색연필 밑줄")
        alpha = image[:, :, 3]
        visible_alpha = np.unique(alpha[alpha > 0])

        self.assertGreater(len(visible_alpha), 12)
        self.assertGreater(np.count_nonzero(alpha), 150)
        self.assertTrue(np.any((alpha > 0) & (np.indices(alpha.shape)[0] < 18)))

    def test_different_phrases_get_different_but_stable_texture(self):
        self.assertFalse(np.array_equal(self.draw_sample("첫 문장"), self.draw_sample("둘째 문장")))


if __name__ == "__main__":
    unittest.main()
