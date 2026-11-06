"""Run any image-edit case list and save results with a comparison sheet."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from editlock import EditPipeline, EditRequest, FluxGenerator


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def make_gallery(records: list[dict], output_dir: Path) -> None:
    width, row_height = 960, 335
    sheet = Image.new("RGB", (width, row_height * len(records)), "white")
    draw = ImageDraw.Draw(sheet)
    for index, record in enumerate(records):
        top = index * row_height
        draw.text((16, top + 10), f"{record['id']}: {record['instructions'][-1][:100]}", fill="black")
        for column, path in enumerate((record["image"], record["output"])):
            with Image.open(path) as image_file:
                image = image_file.convert("RGB")
                image.thumbnail((450, 285), Image.Resampling.LANCZOS)
                left = column * 480 + (480 - image.width) // 2
                sheet.paste(image, (left, top + 35))
    sheet.save(output_dir / "comparison.jpg", quality=90)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", type=Path, help="JSON list of edit cases")
    source.add_argument("--image", help="One image to edit")
    parser.add_argument("--instruction", help="Instruction for --image")
    parser.add_argument("--output", type=Path, default=ROOT / "outputs" / "evaluation")
    args = parser.parse_args()

    if args.manifest:
        cases = json.loads(resolve_path(str(args.manifest)).read_text())
    else:
        if not args.instruction:
            parser.error("--instruction is required with --image")
        cases = [{"id": "example", "image": args.image, "instructions": [args.instruction]}]
    if not isinstance(cases, list) or not cases:
        parser.error("The manifest must be a nonempty JSON list.")

    output_dir = resolve_path(str(args.output))
    output_dir.mkdir(parents=True, exist_ok=True)
    pipeline = EditPipeline(FluxGenerator())
    records = []
    for index, case in enumerate(cases, 1):
        case_id = case.get("id", f"case_{index:03d}")
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", case_id):
            parser.error("Case IDs may contain only letters, digits, underscores, and hyphens.")
        instructions = case.get("instructions") or [case.get("instruction")]
        if not isinstance(instructions, list) or not instructions or any(not isinstance(item, str) or not item.strip() for item in instructions):
            parser.error(f"{case_id}: provide an instruction or a list of instructions.")
        original = resolve_path(case["image"])
        current = original
        steps = []
        for step_number, instruction in enumerate(instructions, 1):
            result = pipeline.run(EditRequest(
                image_path=current,
                instruction=instruction,
                mask_path=resolve_path(case["mask"]) if case.get("mask") else None,
                mode=case.get("mode", "free"),
                seed=case.get("seed", 42),
            ))
            current = output_dir / f"{case_id}_step{step_number}.png"
            shutil.copyfile(result.output_path, current)
            steps.append({
                "instruction": instruction,
                "output": str(current),
                "seconds": result.elapsed_seconds,
                "protected_pixels_identical": result.protected_pixels_identical,
            })
        records.append({
            "id": case_id,
            "image": str(original),
            "output": str(current),
            "instructions": instructions,
            "steps": steps,
        })
        print(f"{case_id}: {len(steps)} step(s) -> {current}", flush=True)
    (output_dir / "results.json").write_text(json.dumps(records, indent=2) + "\n")
    make_gallery(records, output_dir)
    print(f"Comparison sheet: {output_dir / 'comparison.jpg'}")


if __name__ == "__main__":
    main()
