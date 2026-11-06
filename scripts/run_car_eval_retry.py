"""Retry the five partial car edit cases one change at a time using EditLock's chained editing."""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from editlock.model import FluxGenerator
from editlock.pipeline import EditPipeline, EditRequest

OUT = ROOT / "outputs" / "car_eval_sequential"

RETRY_CASES = [
    {
        "id": "C02",
        "category": "Night lighting",
        "image": "cars/2016-Lamborghini-Aventador-LP750-4-SV-017-2000-scaled.jpg",
        "checks": ["nighttime track", "floodlights and reflections", "recognizable gray car and view"],
        "steps": [
            {
                "step": 1,
                "goal": "Change racetrack from daylight to nighttime scene with track floodlights",
                "prompt": "Turn this daylight racetrack into a nighttime race scene with a dark night sky and bright track floodlights. Retain the matte gray Lamborghini, its front three-quarter view, and sense of speed."
            },
            {
                "step": 2,
                "goal": "Add realistic floodlight reflections while restoring matte gray car finish",
                "prompt": "Add realistic ground reflections from the track floodlights onto the asphalt under the matte gray Lamborghini. Keep the car's matte gray paint finish, body lines, and front three-quarter view."
            }
        ]
    },
    {
        "id": "C04",
        "category": "Ground replacement",
        "image": "cars/2020-Aston-Martin-Victor-005-2160-scaled.jpg",
        "checks": ["gravel and garden replaced by pavement", "brick building retained", "car shape and position retained"],
        "steps": [
            {
                "step": 1,
                "goal": "Replace gravel ground with clean paved asphalt street",
                "prompt": "Replace the loose gravel ground with a clean paved asphalt street. Keep the dark green Aston Martin, garden strip, and brick building unchanged."
            },
            {
                "step": 2,
                "goal": "Replace remaining garden strip with paved street and sidewalk",
                "prompt": "Replace the green garden strip and plants with paved asphalt street and concrete curb. Keep the dark green Aston Martin and brick building exactly in place."
            }
        ]
    },
    {
        "id": "C05",
        "category": "Weather and ground",
        "image": "cars/2020-Koenigsegg-Jesko-009-2160-scaled.jpg",
        "checks": ["bright midday scene", "grass replaced by paved shoulder", "white car and position retained"],
        "steps": [
            {
                "step": 1,
                "goal": "Change mountain runway sunset to bright midday scene",
                "prompt": "Change the mountain runway at sunset into a bright clear midday sunny scene with blue sky. Keep the runway, roadside grass, and white Koenigsegg in the same position."
            },
            {
                "step": 2,
                "goal": "Remove grass beside runway and replace with paved shoulder",
                "prompt": "Remove the roadside grass beside the runway and replace it with a clean paved asphalt shoulder. Keep the white Koenigsegg in the same position and midday lighting."
            }
        ]
    },
    {
        "id": "C09",
        "category": "Rain and reflections",
        "image": "cars/3f70f9e26b4bb6a64a9c7bab6dd9125d.jpeg",
        "checks": ["rain visible", "wet reflective road", "car and winding road retained"],
        "steps": [
            {
                "step": 1,
                "goal": "Make asphalt wet with realistic reflections while preserving car details",
                "prompt": "Make the asphalt road wet with dark damp pavement and realistic water puddle reflections under the silver Koenigsegg. Retain the car's exact front view, headlights, body shape, and winding road."
            },
            {
                "step": 2,
                "goal": "Add light rainstorm and atmospheric mist to the wet forest road",
                "prompt": "Add a light rainstorm with visible falling rain streaks and mist over the wet forest road. Retain the exact silver Koenigsegg front view and wet reflective road."
            }
        ]
    },
    {
        "id": "C10",
        "category": "Multi-step scene edit",
        "image": "cars/802c9c8a47057cd5d212e13204f97acf.jpg",
        "checks": ["grass replaced by paved road", "sunny afternoon", "car about 25% smaller", "front view retained"],
        "steps": [
            {
                "step": 1,
                "goal": "Replace grass with paved road",
                "prompt": "Replace the grass under the BMW with a clean paved asphalt road. Keep the dark BMW car and front-on view."
            },
            {
                "step": 2,
                "goal": "Turn stormy sunset into sunny clear afternoon",
                "prompt": "Turn the stormy sunset into a bright clear sunny afternoon with blue sky. Keep the dark BMW car and paved road."
            },
            {
                "step": 3,
                "goal": "Scale car about 25% smaller while retaining dark color and front view",
                "prompt": "Make the dark charcoal BMW car about 25% smaller in the frame centered on the paved road. Retain its dark charcoal gray color and front-on view."
            }
        ]
    }
]


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records_path = OUT / "run.json"
    records = json.loads(records_path.read_text()) if records_path.exists() else []
    completed = {record["id"] for record in records if record.get("status") == "completed"}

    engine = EditPipeline(FluxGenerator())

    for case_idx, case in enumerate(RETRY_CASES, 1):
        case_id = case["id"]
        if case_id in completed:
            print(f"[{case_idx}/{len(RETRY_CASES)}] {case_id}: already completed, skipping", flush=True)
            continue

        print(f"\n==========================================", flush=True)
        print(f"[{case_idx}/{len(RETRY_CASES)}] Starting {case_id} ({case['category']}) with {len(case['steps'])} sequential steps", flush=True)
        print(f"==========================================", flush=True)

        current_input = ROOT / case["image"]
        step_records = []
        total_time = 0.0

        try:
            for step_info in case["steps"]:
                step_num = step_info["step"]
                prompt = step_info["prompt"]
                print(f"  Step {step_num}: {step_info['goal']}", flush=True)
                print(f"    Prompt: {prompt}", flush=True)
                print(f"    Input:  {current_input.name}", flush=True)

                t0 = time.perf_counter()
                result = engine.run(EditRequest(
                    image_path=current_input,
                    instruction=prompt,
                    mode="free",
                    seed=42,
                    max_model_side=768,
                ))
                elapsed = round(time.perf_counter() - t0, 2)
                total_time += elapsed

                step_output = OUT / f"{case_id}_step{step_num}.png"
                shutil.copyfile(result.output_path, step_output)

                step_records.append({
                    "step": step_num,
                    "prompt": prompt,
                    "input": str(current_input.relative_to(ROOT) if current_input.is_relative_to(ROOT) else current_input),
                    "output": str(step_output.relative_to(ROOT)),
                    "session_id": result.session_id,
                    "seconds": elapsed
                })
                print(f"    Done in {elapsed:.2f}s -> {step_output.name}", flush=True)

                # Chain: next step takes this result as input!
                current_input = step_output

            # Copy final step as case output
            final_output = OUT / f"{case_id}.png"
            shutil.copyfile(current_input, final_output)

            record = {
                "id": case_id,
                "status": "completed",
                "category": case["category"],
                "input": case["image"],
                "output": str(final_output.relative_to(ROOT)),
                "num_steps": len(case["steps"]),
                "steps": step_records,
                "total_seconds": round(total_time, 2),
                "checks": case["checks"],
            }
        except Exception as exc:
            print(f"  ERROR on {case_id}: {exc}", flush=True)
            record = {
                "id": case_id,
                "status": "failed",
                "error": str(exc),
                "steps": step_records,
            }

        records = [r for r in records if r["id"] != case_id]
        records.append(record)
        records_path.write_text(json.dumps(records, indent=2) + "\n")
        print(f"Completed {case_id}: total {record.get('total_seconds', 'N/A')}s", flush=True)


if __name__ == "__main__":
    main()
