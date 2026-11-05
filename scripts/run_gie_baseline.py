"""Run the unchanged FLUX.2 Klein 4B edit baseline on the fixed GIE subset."""

import json
import os
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/gie_subset/manifest.json"
OUT = ROOT / "outputs/gie_baseline"
COMMAND = ROOT / ".venv/bin/mflux-generate-flux2-edit"


def main():
    cases = json.loads(MANIFEST.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HF_HOME"] = str(ROOT / "models/cache")
    results = []
    for number, case in enumerate(cases, 1):
        output = OUT / f"{case['case_id']}.png"
        log = OUT / f"{case['case_id']}.log"
        if output.exists():
            print(f"{number}/{len(cases)} {case['case_id']}: already complete", flush=True)
            results.append({"case_id": case["case_id"], "output": str(output.relative_to(ROOT)), "status": "cached"})
            continue
        args = [
            str(COMMAND), "--model", "flux2-klein-4b",
            "--image-paths", str(ROOT / case["source_image"]),
            "--prompt", case["instruction"],
            "--steps", "4", "--seed", "42",
            "--width", str(case["width"]), "--height", str(case["height"]),
            "--output", str(output),
        ]
        start = time.perf_counter()
        process = subprocess.run(args, env=env, capture_output=True, text=True)
        seconds = round(time.perf_counter() - start, 2)
        combined = process.stdout + "\n" + process.stderr
        log.write_text(combined)
        match = re.search(r"Peak MLX memory:\s*([\d.]+)\s*GB", combined)
        row = {
            "case_id": case["case_id"],
            "output": str(output.relative_to(ROOT)),
            "status": "ok" if process.returncode == 0 and output.exists() else "failed",
            "wall_seconds": seconds,
            "peak_mlx_gb": float(match.group(1)) if match else None,
        }
        results.append(row)
        (OUT / "run.json").write_text(json.dumps(results, indent=2) + "\n")
        print(f"{number}/{len(cases)} {case['case_id']}: {row['status']}, {seconds}s, {row['peak_mlx_gb']} GB", flush=True)
    (OUT / "run.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    main()
