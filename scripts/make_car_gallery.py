"""Create before/after sheets for the fixed car-edit evaluation."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/car_eval"


def thumb(path: Path) -> Image.Image:
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        return ImageOps.pad(image, (532, 218), color="#202827", method=Image.Resampling.LANCZOS)


def main() -> None:
    cases = json.loads((ROOT / "eval/car_cases.json").read_text())
    font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 17)
    bold = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf", 19)
    for start in range(0, len(cases), 3):
        sheet = Image.new("RGB", (1150, 1050), "#f4f3ef")
        draw = ImageDraw.Draw(sheet)
        draw.text((28, 18), f"EditLock car edits · sheet {start // 3 + 1}", font=bold, fill="#192323")
        draw.text((28, 52), "Original", font=font, fill="#53615f")
        draw.text((590, 52), "Result", font=font, fill="#53615f")
        for row, case in enumerate(cases[start:start + 3]):
            y = 82 + row * 320
            draw.text((28, y), f"{case['id']} · {case['category']}", font=bold, fill="#192323")
            for line_index, line in enumerate(textwrap.wrap(case["prompt"], width=115)[:2]):
                draw.text((28, y + 27 + line_index * 20), line, font=font, fill="#53615f")
            sheet.paste(thumb(ROOT / case["image"]), (28, y + 71))
            result = OUT / f"{case['id']}.png"
            if result.exists():
                sheet.paste(thumb(result), (590, y + 71))
            else:
                draw.text((590, y + 160), "Result missing", font=font, fill="#a23d3d")
        path = OUT / f"gallery_{start // 3 + 1:02d}.jpg"
        sheet.save(path, quality=90)
        print(path)


if __name__ == "__main__":
    main()
