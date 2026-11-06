"""Create comparison gallery sheets for the retried sequential car edits.

Compares:
1. Original photo
2. Single-turn baseline edit (which was Partial)
3. Step-by-step chained result (taking intermediate result and applying next instruction)
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
BASELINE_OUT = ROOT / "outputs/car_eval"
SEQ_OUT = ROOT / "outputs/car_eval_sequential"


def thumb(path: Path, size: tuple[int, int] = (360, 200)) -> Image.Image:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        return ImageOps.pad(image, size, color="#202827", method=Image.Resampling.LANCZOS)


def main() -> None:
    records_path = SEQ_OUT / "run.json"
    if not records_path.exists():
        print("No sequential records found.")
        return
    records = json.loads(records_path.read_text())

    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 15)
    bold = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 17)
    title_bold = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 20)

    # 1200 width, 320px per case
    sheet_height = 80 + len(records) * 310
    sheet = Image.new("RGB", (1200, sheet_height), "#f4f3ef")
    draw = ImageDraw.Draw(sheet)

    draw.text((28, 18), "EditLock: Chained Multi-Step Retries (Partial Cases)", font=title_bold, fill="#192323")
    draw.text((28, 48), "Column 1: Original Image", font=bold, fill="#53615f")
    draw.text((410, 48), "Column 2: Single-Turn Baseline (Partial)", font=bold, fill="#53615f")
    draw.text((800, 48), "Column 3: Chained Multi-Step Result", font=bold, fill="#155e54")

    for idx, rec in enumerate(records):
        y = 80 + idx * 310
        case_id = rec["id"]
        category = rec.get("category", "")
        steps_summary = f"{rec.get('num_steps', 2)} steps · {rec.get('total_seconds', 0)}s"

        draw.text((28, y), f"{case_id} · {category} ({steps_summary})", font=bold, fill="#192323")

        step_prompts = "; ".join(f"Step {s['step']}: {s['prompt']}" for s in rec.get("steps", []))
        wrapped = textwrap.wrap(step_prompts, width=130)[:2]
        for l_idx, line in enumerate(wrapped):
            draw.text((28, y + 24 + l_idx * 18), line, font=font, fill="#53615f")

        # 1. Original
        orig_path = ROOT / rec["input"]
        if orig_path.exists():
            sheet.paste(thumb(orig_path), (28, y + 68))

        # 2. Baseline single-turn
        base_path = BASELINE_OUT / f"{case_id}.png"
        if base_path.exists():
            sheet.paste(thumb(base_path), (410, y + 68))
        else:
            draw.text((410, y + 150), "No baseline", font=font, fill="#888")

        # 3. Final sequential
        final_path = SEQ_OUT / f"{case_id}.png"
        if final_path.exists():
            sheet.paste(thumb(final_path), (800, y + 68))
        else:
            draw.text((800, y + 150), "In progress...", font=font, fill="#888")

    out_gallery = SEQ_OUT / "sequential_comparison_gallery.jpg"
    sheet.save(out_gallery, quality=90)
    print(f"Saved gallery to {out_gallery}")


if __name__ == "__main__":
    main()
