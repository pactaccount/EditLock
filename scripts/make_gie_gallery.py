"""Create original/edit comparison sheets for manual GIE-Bench review."""

import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/gie_baseline"
FONT = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)


def main():
    cases = json.loads((ROOT / "data/gie_subset/manifest.json").read_text())
    for page, offset in enumerate(range(0, len(cases), 4), 1):
        sheet = Image.new("RGB", (800, 1420), "white")
        draw = ImageDraw.Draw(sheet)
        for row, case in enumerate(cases[offset:offset + 4]):
            top = row * 355
            label = f"{case['case_id']} — {case['edit_type']}: {case['instruction']}"
            draw.text((8, top + 4), textwrap.shorten(label, width=88, placeholder="…"), font=FONT, fill="black")
            for column, path in enumerate((ROOT / case["source_image"], OUT / f"{case['case_id']}.png")):
                image = Image.open(path).convert("RGB")
                image.thumbnail((390, 315), Image.Resampling.LANCZOS)
                x = column * 400 + (400 - image.width) // 2
                y = top + 35 + (315 - image.height) // 2
                sheet.paste(image, (x, y))
        sheet.save(OUT / f"gallery_{page:02d}.jpg", quality=90)
        print(OUT / f"gallery_{page:02d}.jpg")


if __name__ == "__main__":
    main()
