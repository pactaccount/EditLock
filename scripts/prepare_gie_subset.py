"""Prepare a fixed, product-relevant GIE-Bench subset for local evaluation.

Dataset files and images remain under data/, which is excluded from Git.
"""

import json
from io import BytesIO
from pathlib import Path

import ijson
import numpy as np
import requests
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/gie-bench/gie_bench.json"
DEST = ROOT / "data/gie_subset"
TYPES = (
    "Remove Object",
    "Add Object",
    "Object Replacement",
    "Color Change",
    "Attribute Change",
    "Size Change",
    "Layout Modification",
    "Textual Edit",
)
CATEGORIES = {
    "accessories", "cloth", "electronics", "food", "furniture",
    "home_appliance", "jewellery", "musical_instrument", "plants", "sign", "text",
}
PER_TYPE = 3


def target_size(image):
    width, height = image.size
    ratio = width / height
    if not 2 / 3 <= ratio <= 3 / 2:
        return None
    if ratio >= 1:
        return round(512 * ratio / 16) * 16, 512
    return 512, round(512 / ratio / 16) * 16


def main():
    (DEST / "images").mkdir(parents=True, exist_ok=True)
    (DEST / "masks").mkdir(parents=True, exist_ok=True)
    selected = []
    category_by_type = {kind: set() for kind in TYPES}
    used_images = set()
    with requests.Session() as session, SOURCE.open("rb") as stream:
        for index, entry in enumerate(ijson.items(stream, "item")):
            kind = entry["edit_type"]
            category = entry["image_content_type"]
            image_id = entry["image"]
            if kind not in TYPES or category not in CATEGORIES:
                continue
            if len(category_by_type[kind]) >= PER_TYPE or (
                category in category_by_type[kind] and kind != "Textual Edit"
            ):
                continue
            if image_id in used_images:
                continue
            mask = np.asarray(entry["object_mask"], dtype=np.uint8)
            coverage = float(mask.mean())
            if not 0.01 <= coverage <= 0.75:
                continue
            case_id = f"gie_{index:04d}"
            image_path = DEST / "images" / f"{case_id}.png"
            mask_path = DEST / "masks" / f"{case_id}.png"
            try:
                if image_path.exists():
                    image = Image.open(image_path).convert("RGB")
                    size = image.size
                else:
                    response = session.get(
                        entry["url"], params={"auto": "compress", "w": "900"}, timeout=30
                    )
                    response.raise_for_status()
                    image = Image.open(BytesIO(response.content)).convert("RGB")
                    size = target_size(image)
                    if size is None:
                        continue
                    image = image.resize(size, Image.Resampling.LANCZOS)
            except (requests.RequestException, OSError) as exc:
                print(f"Skipping {index}: {exc}")
                continue

            image.save(image_path)
            Image.fromarray(mask * 255, mode="L").resize(
                size, Image.Resampling.NEAREST
            ).save(mask_path)
            selected.append({
                "case_id": case_id,
                "source_index": index,
                "edit_type": kind,
                "category": category,
                "instruction": entry["edit_instruction"],
                "question": entry["evaluation_question"],
                "source_url": entry["url"],
                "source_image": str(image_path.relative_to(ROOT)),
                "edit_mask": str(mask_path.relative_to(ROOT)),
                "width": size[0],
                "height": size[1],
                "mask_fraction": round(coverage, 4),
            })
            category_by_type[kind].add(category if kind != "Textual Edit" else case_id)
            used_images.add(image_id)
            print(f"{case_id}: {kind} / {category}: {entry['edit_instruction']}", flush=True)
            if all(len(categories) == PER_TYPE for categories in category_by_type.values()):
                break

    (DEST / "manifest.json").write_text(json.dumps(selected, indent=2) + "\n")
    print(f"Prepared {len(selected)} cases. Counts: " + str({
        kind: len(category_by_type[kind]) for kind in TYPES
    }))


if __name__ == "__main__":
    main()
