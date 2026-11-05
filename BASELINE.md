# FLUX.2 editing baseline

## What ran

- Model: [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), official checkpoint revision `e7b7dc27f91deacad38e78976d1f2b499d76a294`.
- Runtime: MFLUX 0.24.0 / MLX 0.32.4 on the 48 GB M5 Pro; four inference steps, seed 42, no quantization or fine-tuning.
- Dataset: a fixed **24-case subset** of Apple's [GIE-Bench](https://github.com/apple-aiml-research/ml-gie-bench): three cases each for object removal, addition, replacement, color change, attribute change, size change, layout modification, and text editing. The selection uses product-relevant image categories, unique source photos, masks covering 1–75% of the image, and aspect ratios between 2:3 and 3:2. Source images were resized with their aspect ratios preserved to 512–768 pixels. This is a pilot subset, not a full GIE-Bench result.

The model received each original image and the benchmark's exact edit instruction. It did **not** receive the region mask. The mask was used only for scoring. All 24 cases completed.

## Results

| Measure | 24-case result |
| --- | ---: |
| Instruction visibly achieved | 21 / 24 (87.5%) |
| Mean wall time per edit | 6.96 seconds |
| Maximum reported peak MLX memory | 9.53 GB |
| Mean absolute RGB error outside edit mask | 13.68 / 255 |
| Mean PSNR outside edit mask | 23.52 dB |
| Mean fraction of protected pixels changed by over 10 in any RGB channel | 31.6% |
| Mean fraction of protected pixels exactly unchanged | 0.3% |

The instruction score is a manual yes/no review of side-by-side images. A case counts as successful if the requested edit visibly happened, even when it also made unwanted changes. The three failures were: brushes did not become smaller (`gie_0001`); the faucet did not change size (`gie_0006`); the metal pot did not move (`gie_0026`). For example, `gie_0023` added a solar light but also changed a daylight scene to night, so it counts as instruction success and preservation failure.

Preservation values are means of per-case scores at the original pixel coordinates. The edit mask is treated as binary **0 = protected, 1 = editable**. No image alignment or registration is applied because EditLock's promise is to keep protected pixels at those coordinates. These are EditLock pilot measures, not Apple's official GIE-Bench aggregate or its GPT-based correctness score.

## Build decision

FLUX.2 is fast enough and handles many requested edits, so keep it as the generator. Its raw output changes too much protected content to be an EditLock export. **Next build step:** implement the region-locking pipeline: take an image, instruction, and editable mask; generate with FLUX.2; place generated pixels only inside the editable area; preserve original pixels outside it; and handle visible seams at the boundary. Then connect that pipeline to the Mac app.

## Reproduce

The dataset, source images, generated images, per-case logs, metrics JSON, and review galleries stay local under `data/` and `outputs/` and are excluded from Git. From this repository after installing MFLUX and `ijson` in `.venv`:

```sh
git clone --depth 1 https://github.com/apple-aiml-research/ml-gie-bench.git data/gie-bench
unzip -oq data/gie-bench/gie_bench_json.zip -d data/gie-bench
.venv/bin/python scripts/prepare_gie_subset.py
.venv/bin/python scripts/run_gie_baseline.py
.venv/bin/python scripts/score_gie_baseline.py
.venv/bin/python scripts/make_gie_gallery.py
```

Detailed scores are in `outputs/gie_baseline/metrics.json`; runtime measurements are in `outputs/gie_baseline/run.json`; visual comparisons are in `outputs/gie_baseline/gallery_01.jpg` through `gallery_06.jpg`.
