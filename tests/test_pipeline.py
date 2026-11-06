import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from editlock.pipeline import EditPipeline, EditRequest, composite


class GlobalChangeGenerator:
    """Simulate an editor that changes every pixel, including protected ones."""

    def generate(self, image_path: Path, prompt: str, width: int, height: int, seed: int) -> Image.Image:
        self.last_prompt = prompt
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
                EditRequest(image_path, "Make the object red", mask_path=mask_path, mode="locked", feather_px=8)
            )
            output = np.asarray(Image.open(result.output_path).convert("RGB"))
            self.assertEqual(output.shape, original.shape)
            self.assertTrue(result.protected_pixels_identical)
            self.assertTrue(np.array_equal(output[mask == 0], original[mask == 0]))
            self.assertFalse(np.array_equal(output[mask == 255], original[mask == 255]))

    def test_instruction_only_edit_needs_no_mask_and_keeps_full_model_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path = root / "source.png"
            Image.new("RGB", (480, 320), (20, 40, 60)).save(image_path)
            generator = GlobalChangeGenerator()
            result = EditPipeline(generator, root / "sessions").run(
                EditRequest(image_path, "Make the whole scene red")
            )
            output = np.asarray(Image.open(result.output_path))
            self.assertEqual(result.mode, "free")
            self.assertIsNone(result.mask_path)
            self.assertIsNone(result.protected_pixels_identical)
            self.assertTrue(np.all(output == [220, 20, 20]))
            self.assertEqual(generator.last_prompt, "Make the whole scene red")

    def test_paint_guides_model_without_locking_other_pixels(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            image_path, mask_path = root / "source.png", root / "mask.png"
            Image.new("RGB", (480, 320), (20, 40, 60)).save(image_path)
            mask = np.zeros((320, 480), dtype=np.uint8)
            mask[20:90, 30:100] = 255
            Image.fromarray(mask).save(mask_path)
            generator = GlobalChangeGenerator()
            result = EditPipeline(generator, root / "sessions").run(
                EditRequest(image_path, "Make the object red", mask_path=mask_path, mode="guided")
            )
            output = np.asarray(Image.open(result.output_path))
            self.assertEqual(result.mode, "guided")
            self.assertIsNone(result.protected_pixels_identical)
            self.assertTrue(np.all(output[mask == 0] == [220, 20, 20]))
            self.assertIn("upper left", generator.last_prompt)

    def test_chained_editing_uses_result_as_next_input_preserving_both_versions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original_path = root / "original.png"
            Image.new("RGB", (480, 320), (10, 20, 30)).save(original_path)

            class SequenceGenerator:
                def __init__(self):
                    self.prompts = []

                def generate(self, image_path: Path, prompt: str, width: int, height: int, seed: int) -> Image.Image:
                    self.prompts.append(prompt)
                    color = (255, 0, 0) if "first" in prompt else (0, 0, 255)
                    return Image.new("RGB", (width, height), color)

            pipeline = EditPipeline(SequenceGenerator(), root / "sessions")
            step1 = pipeline.run(EditRequest(original_path, "first change: make red"))
            self.assertTrue(step1.output_path.is_file())
            step1_pixels = np.asarray(Image.open(step1.output_path))
            self.assertTrue(np.all(step1_pixels == [255, 0, 0]))

            # Continue editing from the result of step 1:
            step2 = pipeline.run(EditRequest(step1.output_path, "second change: make blue"))
            self.assertTrue(step2.output_path.is_file())
            step2_pixels = np.asarray(Image.open(step2.output_path))
            self.assertTrue(np.all(step2_pixels == [0, 0, 255]))

            # The original and intermediate result are both still intact on disk:
            orig_pixels = np.asarray(Image.open(original_path))
            self.assertTrue(np.all(orig_pixels == [10, 20, 30]))
            step1_reloaded = np.asarray(Image.open(step1.output_path))
            self.assertTrue(np.all(step1_reloaded == [255, 0, 0]))

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
