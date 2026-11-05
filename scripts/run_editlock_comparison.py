"""Run the built EditLock pipeline on the same 24 GIE-Bench pilot cases."""

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from editlock.model import FluxGenerator
from editlock.pipeline import EditPipeline, EditRequest

OUT = ROOT / "outputs/gie_editlock"


def main():
    cases = json.loads((ROOT / "data/gie_subset/manifest.json").read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    engine = EditPipeline(FluxGenerator())
    records = []
    for index, case in enumerate(cases, 1):
        output = OUT / f"{case['case_id']}.png"
        if output.exists():
            print(f"{index}/{len(cases)} {case['case_id']}: existing", flush=True)
            continue
        result = engine.run(EditRequest(
            image_path=ROOT / case["source_image"],
            mask_path=ROOT / case["edit_mask"],
            instruction=case["instruction"],
            seed=42,
        ))
        shutil.copyfile(result.output_path, output)
        records.append({
            "case_id": case["case_id"],
            "output": str(output.relative_to(ROOT)),
            "elapsed_seconds": result.elapsed_seconds,
            "protected_pixels_identical": result.protected_pixels_identical,
            "alignment_used": result.alignment_used,
            "session_id": result.session_id,
        })
        (OUT / "run.json").write_text(json.dumps(records, indent=2) + "\n")
        print(
            f"{index}/{len(cases)} {case['case_id']}: {result.elapsed_seconds}s, "
            f"protected={result.protected_pixels_identical}", flush=True
        )


if __name__ == "__main__":
    main()
