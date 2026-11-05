import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image

from editlock.pipeline import EditPipeline
from editlock.server import create_app


class SolidGenerator:
    def generate(self, image_path: Path, prompt: str, width: int, height: int, seed: int) -> Image.Image:
        return Image.new("RGB", (width, height), (100, 150, 200))


class ServerTests(unittest.TestCase):
    def test_edit_endpoint_accepts_instruction_without_mask(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.png"
            Image.new("RGB", (480, 320), (25, 50, 75)).save(source)
            app = create_app("local-test-token", EditPipeline(SolidGenerator(), root / "sessions"))
            with TestClient(app) as client:
                response = client.post(
                    "/edit",
                    headers={"X-EditLock-Token": "local-test-token"},
                    json={"image_path": str(source), "instruction": "Change the scene"},
                )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["mode"], "free")
            self.assertIsNone(response.json()["mask_path"])
            self.assertIsNone(response.json()["protected_pixels_identical"])
            self.assertTrue(Path(response.json()["output_path"]).is_file())


if __name__ == "__main__":
    unittest.main()
