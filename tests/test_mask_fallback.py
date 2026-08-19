import importlib.util
import pathlib
import unittest

import numpy as np
import torch


MODULE_PATH = pathlib.Path(__file__).parents[1] / "comfyui_korean_ocr_to_image.py"
SPEC = importlib.util.spec_from_file_location("korean_ocr_nodes_mask", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EmptyMaskFallbackTests(unittest.TestCase):
    def test_empty_mask_uses_the_entire_image(self):
        rgb = np.arange(5 * 7 * 3, dtype=np.uint8).reshape(5, 7, 3)
        mask = torch.zeros((1, 5, 7), dtype=torch.float32)

        cropped = MODULE._masked_crop(rgb, mask, invert=False, margin=16)

        np.testing.assert_array_equal(cropped, rgb)


if __name__ == "__main__":
    unittest.main()
