"""Measure raw FLUX.2 changes inside and outside GIE-Bench edit masks.

These are EditLock pilot metrics, not the official GIE-Bench aggregate score.
No image registration is applied because EditLock must preserve protected pixels
at their original coordinates.
"""

import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data/gie_subset/manifest.json"
OUT = ROOT / "outputs/gie_baseline"


def mean(values):
    return round(float(np.mean(values)), 3) if values else None


def main():
    cases = json.loads(MANIFEST.read_text())
    rows = []
    for case in cases:
        edited_path = OUT / f"{case['case_id']}.png"
        if not edited_path.exists():
            continue
        original = np.asarray(Image.open(ROOT / case["source_image"]).convert("RGB"), dtype=np.float32)
        edited = np.asarray(Image.open(edited_path).convert("RGB"), dtype=np.float32)
        allowed = np.asarray(Image.open(ROOT / case["edit_mask"]).convert("L")) >= 128
        if original.shape != edited.shape or original.shape[:2] != allowed.shape:
            raise ValueError(f"Image or mask size mismatch: {case['case_id']}")
        delta = np.abs(edited - original)
        protected = ~allowed
        protected_delta = delta[protected]
        allowed_delta = delta[allowed]
        mse = float(np.mean(protected_delta ** 2))
        psnr = float("inf") if mse == 0 else 10 * np.log10(255 ** 2 / mse)
        rows.append({
            "case_id": case["case_id"],
            "edit_type": case["edit_type"],
            "instruction": case["instruction"],
            "protected_mae": round(float(np.mean(protected_delta)), 3),
            "protected_psnr_db": round(float(psnr), 3),
            "protected_pixels_changed_gt10_fraction": round(float(np.mean(np.max(protected_delta, axis=1) > 10)), 4),
            "protected_pixels_exact_fraction": round(float(np.mean(np.max(protected_delta, axis=1) == 0)), 4),
            "allowed_mae": round(float(np.mean(allowed_delta)), 3),
        })
    groups = defaultdict(list)
    for row in rows:
        groups[row["edit_type"]].append(row)
    summary = {
        "cases_scored": len(rows),
        "protected_mae_mean": mean([r["protected_mae"] for r in rows]),
        "protected_psnr_db_mean": mean([r["protected_psnr_db"] for r in rows]),
        "protected_pixels_changed_gt10_fraction_mean": mean([r["protected_pixels_changed_gt10_fraction"] for r in rows]),
        "protected_pixels_exact_fraction_mean": mean([r["protected_pixels_exact_fraction"] for r in rows]),
        "by_type": {
            kind: {
                "count": len(items),
                "protected_mae_mean": mean([r["protected_mae"] for r in items]),
                "protected_pixels_changed_gt10_fraction_mean": mean([r["protected_pixels_changed_gt10_fraction"] for r in items]),
            }
            for kind, items in groups.items()
        },
    }
    (OUT / "metrics.json").write_text(json.dumps({"summary": summary, "cases": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
