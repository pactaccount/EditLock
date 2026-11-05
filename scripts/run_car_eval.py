"""Run the fixed, instruction-only car edit cases through EditLock."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from editlock.model import FluxGenerator
from editlock.pipeline import EditPipeline, EditRequest

CASES = ROOT / "eval/car_cases.json"
OUT = ROOT / "outputs/car_eval"


def main() -> None:
    cases = json.loads(CASES.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    records_path = OUT / "run.json"
    records = json.loads(records_path.read_text()) if records_path.exists() else []
    completed = {record["id"] for record in records if record.get("status") == "completed"}
    engine = EditPipeline(FluxGenerator())

    for index, case in enumerate(cases, 1):
        if case["id"] in completed:
            print(f"{index}/{len(cases)} {case['id']}: existing", flush=True)
            continue
        print(f"{index}/{len(cases)} {case['id']}: generating", flush=True)
        try:
            result = engine.run(EditRequest(
                image_path=ROOT / case["image"],
                instruction=case["prompt"],
                mode="free",
                seed=42,
                max_model_side=768,
            ))
            output = OUT / f"{case['id']}.png"
            shutil.copyfile(result.output_path, output)
            record = {
                "id": case["id"],
                "status": "completed",
                "input": case["image"],
                "output": str(output.relative_to(ROOT)),
                "mode": result.mode,
                "seed": 42,
                "seconds": result.elapsed_seconds,
                "session_id": result.session_id,
            }
        except Exception as exc:
            record = {"id": case["id"], "status": "failed", "error": str(exc)}
        records = [existing for existing in records if existing["id"] != case["id"]]
        records.append(record)
        records_path.write_text(json.dumps(records, indent=2) + "\n")
        print(f"{case['id']}: {record['status']}, {record.get('seconds', record.get('error'))}", flush=True)


if __name__ == "__main__":
    main()
