"""Lazily load the local FLUX.2 Klein 4B editing model through MFLUX."""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "models" / "cache"
MODEL_DIR = CACHE / "hub" / "models--black-forest-labs--FLUX.2-klein-4B"


class FluxGenerator:
    def __init__(self):
        self._model = None

    def generate(self, image_path: Path, prompt: str, width: int, height: int, seed: int) -> Image.Image:
        if self._model is None:
            if not MODEL_DIR.exists():
                raise FileNotFoundError("FLUX.2 model files are missing. Download the model before editing.")
            os.environ["HF_HOME"] = str(CACHE)
            from mflux.models.common.config import ModelConfig
            from mflux.models.flux2.variants import Flux2KleinEdit

            self._model = Flux2KleinEdit(model_config=ModelConfig.flux2_klein_4b())
        generated = self._model.generate_image(
            seed=seed,
            prompt=prompt,
            num_inference_steps=4,
            width=width,
            height=height,
            image_paths=[image_path],
        )
        return generated.image.convert("RGB")
