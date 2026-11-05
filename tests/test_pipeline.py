import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from editlock.pipeline import EditPipeline, EditRequest, composite


class GlobalChangeGenerator:
    """Simulate an editor that changes every pixel, including protected ones."""

    def generate(self, image_path: Path, prompt: str, width: int, height: int, seed: int) -> Image.Image:
        return Image.new("RGB", (width, height), (220, 20, 20))


class EditPipelineTests(unittest.TestCase):
    def test_full_pipeline_preserves_protected_pixels_even_when_model_changes_everything(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = np.zeros((320, 480, 3), dtype=np.uint8)
            original[:, :, 0] = np.arange(480, dtype=np.uint8)
            original[:, :, 1] = 110
            original[:, :, 2] = 185
            mask = np.zeros((320, 480), dtype=np.uint8)
            mask[100:220, 170:310] = 255
            image_path, mask_path = root / "source.png", root / "mask.png"
            Image.fromarray(original).save(image_path)
            Image.fromarray(mask).save(mask_path)

            result = EditPipeline(GlobalChangeGenerator(), root / "sessions").run(
                EditRequest(image_path, mask_path, "Make the object red", feather_px=8)
            )
            output = np.asarray(Image.open(result.output_path).convert("RGB"))
            self.assertEqual(output.shape, original.shape)
            self.assertTrue(result.protected_pixels_identical)
            self.assertTrue(np.array_equal(output[mask == 0], original[mask == 0]))
            self.assertFalse(np.array_equal(output[mask == 255], original[mask == 255]))

    def test_feather_never_changes_pixels_outside_mask(self):
        source = Image.new("RGB", (80, 80), (25, 50, 75))
        candidate = Image.new("RGB", (80, 80), (220, 0, 0))
        mask = np.zeros((80, 80), dtype=bool)
        mask[20:60, 20:60] = True
        result = np.asarray(composite(source, candidate, mask, feather_px=12))
        self.assertTrue(np.all(result[~mask] == [25, 50, 75]))
        self.assertTrue(np.all(result[40, 40] == [220, 0, 0]))
        self.assertNotEqual(tuple(result[20, 40]), (220, 0, 0))


if __name__ == "__main__":
    unittest.main()
