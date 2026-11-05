"""Run instruction-led edits, with optional painted focus or pixel locking."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
from PIL import Image, ImageOps


ROOT = Path(__file__).resolve().parents[1]
SESSION_ROOT = ROOT / "outputs" / "sessions"


class Generator(Protocol):
    def generate(self, image_path: Path, prompt: str, width: int, height: int, seed: int) -> Image.Image: ...


@dataclass(frozen=True)
class EditRequest:
    image_path: Path
    instruction: str
    mask_path: Path | None = None
    mode: str = "free"
    seed: int = 42
    feather_px: int = 10
    max_model_side: int = 768


@dataclass(frozen=True)
class EditResult:
    session_id: str
    mode: str
    source_path: Path
    mask_path: Path | None
    candidate_path: Path
    output_path: Path
    elapsed_seconds: float
    protected_pixels_identical: bool | None
    alignment_used: bool
    alignment_score: float | None


def load_inputs(image_path: Path, mask_path: Path | None) -> tuple[Image.Image, np.ndarray | None]:
    with Image.open(image_path) as image_file:
        source = ImageOps.exif_transpose(image_file).convert("RGB")
    if mask_path is None:
        return source, None
    with Image.open(mask_path) as mask_file:
        mask = np.asarray(ImageOps.exif_transpose(mask_file).convert("L")) >= 128
    if mask.shape != (source.height, source.width):
        raise ValueError("Mask dimensions must match the oriented source image exactly.")
    return source, mask


def focus_instruction(instruction: str, mask: np.ndarray) -> str:
    """Turn painted guidance into a rough location cue; do not constrain output pixels."""
    ys, xs = np.nonzero(mask)
    center_x = (xs.min() + xs.max()) / (2 * mask.shape[1])
    center_y = (ys.min() + ys.max()) / (2 * mask.shape[0])
    horizontal = "left" if center_x < 1 / 3 else "right" if center_x > 2 / 3 else "center"
    vertical = "upper" if center_y < 1 / 3 else "lower" if center_y > 2 / 3 else "middle"
    place = "center" if horizontal == "center" and vertical == "middle" else f"{vertical} {horizontal}"
    return (
        f"{instruction} Focus on the {place} part of the original image. "
        "Make any surrounding changes needed for a natural result."
    )


def crop_box(mask: np.ndarray) -> tuple[int, int, int, int]:
    height, width = mask.shape
    ys, xs = np.nonzero(mask)
    left, right = int(xs.min()), int(xs.max()) + 1
    top, bottom = int(ys.min()), int(ys.max()) + 1
    pad = max(96, round(0.5 * max(right - left, bottom - top)))
    left, top = max(0, left - pad), max(0, top - pad)
    right, bottom = min(width, right + pad), min(height, bottom + pad)

    # A generous crop gives the image model context, including for small marks.
    min_width, min_height = min(512, width), min(512, height)
    if right - left < min_width:
        center = (left + right) // 2
        left = max(0, min(width - min_width, center - min_width // 2))
        right = left + min_width
    if bottom - top < min_height:
        center = (top + bottom) // 2
        top = max(0, min(height - min_height, center - min_height // 2))
        bottom = top + min_height
    return left, top, right, bottom


def model_size(crop_width: int, crop_height: int, max_side: int) -> tuple[int, int]:
    if max_side < 512 or max_side % 16:
        raise ValueError("Maximum model side must be at least 512 and divisible by 16.")
    longest = max(crop_width, crop_height)
    target_longest = min(max_side, max(512, longest))
    scale = target_longest / longest
    width = max(256, round(crop_width * scale / 16) * 16)
    height = max(256, round(crop_height * scale / 16) * 16)
    return width, height


def align_candidate(
    source: Image.Image, candidate: Image.Image, editable_mask: np.ndarray
) -> tuple[Image.Image, bool, float | None]:
    """Accept only a small translation that improves agreement in protected context."""
    source_array = np.asarray(source.convert("RGB"))
    candidate_array = np.asarray(candidate.convert("RGB"))
    protected = ~editable_mask
    if protected.mean() < 0.15:
        return candidate, False, None
    source_gray = cv2.cvtColor(source_array, cv2.COLOR_RGB2GRAY)
    candidate_gray = cv2.cvtColor(candidate_array, cv2.COLOR_RGB2GRAY)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        score, warp = cv2.findTransformECC(
            source_gray, candidate_gray, warp, cv2.MOTION_TRANSLATION,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 35, 1e-4),
            protected.astype(np.uint8) * 255,
        )
    except cv2.error:
        return candidate, False, None
    if score < 0.65 or np.max(np.abs(warp[:, 2])) > 16:
        return candidate, False, float(score)
    aligned = cv2.warpAffine(
        candidate_array, warp, (source.width, source.height),
        flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
        borderMode=cv2.BORDER_REFLECT,
    )
    before = np.mean(np.abs(source_array[protected].astype(np.float32) - candidate_array[protected]))
    after = np.mean(np.abs(source_array[protected].astype(np.float32) - aligned[protected]))
    if after >= before * 0.95:
        return candidate, False, float(score)
    return Image.fromarray(aligned, "RGB"), True, float(score)


def composite(source: Image.Image, candidate: Image.Image, mask: np.ndarray, feather_px: int) -> Image.Image:
    if source.size != candidate.size or mask.shape != (source.height, source.width):
        raise ValueError("Source, candidate, and mask must have matching sizes.")
    if feather_px < 0:
        raise ValueError("Feather width cannot be negative.")
    original = np.asarray(source.convert("RGB"))
    proposed = np.asarray(candidate.convert("RGB"))
    if feather_px == 0 or np.all(mask):
        alpha = mask.astype(np.float32)
    else:
        distance = cv2.distanceTransform(mask.astype(np.uint8), cv2.DIST_L2, 3)
        alpha = np.minimum(distance / max(1, feather_px), 1.0)
        alpha[~mask] = 0.0
    result = np.rint(
        original.astype(np.float32) * (1.0 - alpha[..., None])
        + proposed.astype(np.float32) * alpha[..., None]
    ).astype(np.uint8)
    result[~mask] = original[~mask]
    return Image.fromarray(result, "RGB")


class EditPipeline:
    def __init__(self, generator: Generator, session_root: Path = SESSION_ROOT):
        self.generator = generator
        self.session_root = Path(session_root)

    def run(self, request: EditRequest) -> EditResult:
        instruction = request.instruction.strip()
        if not instruction:
            raise ValueError("Enter an edit instruction before generating.")
        if request.mode not in {"free", "guided", "locked"}:
            raise ValueError("Edit mode must be free, guided, or locked.")
        if request.mode == "locked" and request.mask_path is None:
            raise ValueError("Paint an area before enabling outside locking.")
        start = time.perf_counter()
        source, mask = load_inputs(
            Path(request.image_path), Path(request.mask_path) if request.mask_path else None
        )
        if request.mode == "locked" and (mask is None or not np.any(mask)):
            raise ValueError("Paint an area before enabling outside locking.")
        mode = "free" if request.mode == "guided" and (mask is None or not np.any(mask)) else request.mode
        session_id = uuid.uuid4().hex[:12]
        session = self.session_root / session_id
        session.mkdir(parents=True, exist_ok=False)

        source_path = session / "source.png"
        mask_path = session / "mask.png" if mask is not None else None
        candidate_path = session / "candidate.png"
        output_path = session / "result.png"
        source.save(source_path)
        if mask_path is not None:
            Image.fromarray(mask.astype(np.uint8) * 255, "L").save(mask_path)

        # Small and medium photos benefit from the full scene context that
        # produced the stronger unmasked baseline edits. Crop large imports.
        box = crop_box(mask) if mode == "locked" and max(source.size) > 1536 else (0, 0, source.width, source.height)
        left, top, right, bottom = box
        crop = source.crop(box)
        width, height = model_size(crop.width, crop.height, request.max_model_side)
        model_input = crop.resize((width, height), Image.Resampling.LANCZOS)
        model_input_path = session / "model_input.png"
        model_input.save(model_input_path)

        model_instruction = focus_instruction(instruction, mask) if mode == "guided" else instruction
        generated = self.generator.generate(model_input_path, model_instruction, width, height, request.seed)
        if generated.size != (width, height):
            raise RuntimeError(f"Model returned {generated.size}, expected {(width, height)}.")
        generated.convert("RGB").save(candidate_path)
        alignment_used, alignment_score = False, None
        identical: bool | None = None
        if mode == "locked":
            assert mask is not None
            crop_mask = mask[top:bottom, left:right]
            resized_mask = np.asarray(
                Image.fromarray(crop_mask.astype(np.uint8) * 255, "L").resize(
                    (width, height), Image.Resampling.NEAREST
                )
            ) >= 128
            aligned, alignment_used, alignment_score = align_candidate(model_input, generated, resized_mask)
            aligned = aligned.resize(crop.size, Image.Resampling.LANCZOS)
            composed_crop = composite(crop, aligned, crop_mask, request.feather_px)
            output = source.copy()
            output.paste(composed_crop, (left, top))
            identical = bool(np.array_equal(np.asarray(output)[~mask], np.asarray(source)[~mask]))
            if not identical:
                raise RuntimeError("Protected pixels changed; refusing to export the result.")
        else:
            output = generated.convert("RGB").resize(source.size, Image.Resampling.LANCZOS)
        output.save(output_path, format="PNG")
        elapsed = round(time.perf_counter() - start, 2)
        result = EditResult(
            session_id=session_id,
            mode=mode,
            source_path=source_path,
            mask_path=mask_path,
            candidate_path=candidate_path,
            output_path=output_path,
            elapsed_seconds=elapsed,
            protected_pixels_identical=identical,
            alignment_used=alignment_used,
            alignment_score=alignment_score,
        )
        metadata = {
            **{key: str(value) if isinstance(value, Path) else value for key, value in asdict(result).items()},
            "instruction": instruction,
            "model_instruction": model_instruction,
            "seed": request.seed,
            "feather_px": request.feather_px,
            "crop_box": box,
            "model_size": [width, height],
        }
        (session / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
        return result
