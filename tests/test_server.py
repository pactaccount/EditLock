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

    def test_edit_endpoint_can_continue_editing_from_previous_result(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "source.png"
            Image.new("RGB", (480, 320), (25, 50, 75)).save(source)
            app = create_app("local-test-token", EditPipeline(SolidGenerator(), root / "sessions"))
            with TestClient(app) as client:
                resp1 = client.post(
                    "/edit",
                    headers={"X-EditLock-Token": "local-test-token"},
                    json={"image_path": str(source), "instruction": "Step 1 change"},
                )
                self.assertEqual(resp1.status_code, 200)
                out1_path = resp1.json()["output_path"]

                # Use out1_path as next input:
                resp2 = client.post(
                    "/edit",
                    headers={"X-EditLock-Token": "local-test-token"},
                    json={"image_path": out1_path, "instruction": "Step 2 change"},
                )
                self.assertEqual(resp2.status_code, 200)
                out2_path = resp2.json()["output_path"]
                self.assertNotEqual(out1_path, out2_path)
                self.assertTrue(Path(out1_path).is_file())
                self.assertTrue(Path(out2_path).is_file())

    def test_web_editor_includes_edit_result_and_history_elements(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            app = create_app("local-test-token", EditPipeline(SolidGenerator(), root / "sessions"))
            with TestClient(app) as client:
                response = client.get("/?token=local-test-token")
            self.assertEqual(response.status_code, 200)
            self.assertIn("editResultButton", response.text)
            self.assertIn("undoVersionButton", response.text)
            self.assertIn("Edit this result", response.text)


if __name__ == "__main__":
    unittest.main()
