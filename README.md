# EditLock

EditLock is a local image editor for Apple Silicon Macs. Import a photo, describe a change, review the result, and export a PNG. Painting is optional: it can guide the model toward an area or explicitly lock everything outside that area. A result can become the input to a follow-up edit, with the original and earlier versions available for comparison and rollback.

The interface is a native SwiftUI Mac app or a localhost browser editor. Both use a Python engine with [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) through [MFLUX](https://github.com/mflux-community/mflux) and MLX. Image generation runs on the Mac; the browser editor connects only to 127.0.0.1. This project does not train or fine-tune the model.

**A shareable model-generated example:** “Change only the blue ceramic mug to a bright red ceramic mug. Keep the mug shape, handle, lighting, and white room unchanged.” These images are a smoke test, not part of the car or GIE-Bench scores.

| Input | Edited output |
| --- | --- |
| ![Blue mug input](assets/demo/blue-mug.png) | ![Red mug output](assets/demo/red-mug.png) |

## What the app does

| Mode | How it works | Promise |
| --- | --- | --- |
| Instruction only | Send the whole image and instruction to FLUX.2. | The result may change anywhere. |
| Painted guidance | Convert paint into an approximate location cue in the instruction. Erase removes part of the cue. | Paint guides the model but does not constrain it. |
| Outside locking | Generate a candidate, align it when reliable, composite within the paint, then compare every outside pixel with the normalized source. | All pixels outside the paint are identical in the exported PNG. |
| Follow-up edit | Use the current result as the next input with a new instruction. Keep the original and intermediate versions. | Helps break a difficult request into smaller edits; quality still needs visual review. |

The output PNG has the source image's pixel dimensions. The model generates from a resized input, usually with a maximum side of 768 pixels, so matching dimensions do **not** mean all original fine detail is preserved. Locked mode uses the full source image up to 1536 pixels, then crops around the paint for larger inputs.

## Run locally

The tested machine was a **48 GB MacBook Pro M5 Pro**. The native app targets macOS 14 or later and is built for Apple Silicon. Other Mac configurations have not been validated. Expect about 15 GB of local model files in addition to the Python environment. You need Python 3.13, uv, and a Swift toolchain to build the native app.

From the repository root:

~~~sh
UV_CACHE_DIR="$PWD/.cache/uv" uv venv --python 3.13 .venv
UV_CACHE_DIR="$PWD/.cache/uv" uv pip install --python .venv/bin/python -e '.[dev]'
mkdir -p models/cache outputs
HF_HOME="$PWD/models/cache" .venv/bin/mflux-generate-flux2 \
  --model flux2-klein-4b \
  --prompt 'A blue ceramic mug on a white table in a bright room' \
  --steps 4 --seed 42 --width 512 --height 512 \
  --output outputs/first-model-test.png
~~~

The last command downloads the model into the local cache on first use and generates a test image. Model weights, the Python environment, and session outputs are not stored in Git.

**Native Mac app:**

~~~sh
scripts/build_mac_app.sh
open dist/EditLock.app
~~~

**Local browser editor:**

~~~sh
.venv/bin/python -m editlock web --port 8765
~~~

Open the localhost URL printed by that command. In either editor, import an image, enter an instruction, and generate. To make a second change, select **Edit this result** and enter a new instruction. Paint and erase only when useful. Turn on outside locking only when exact preservation matters; include the object, any new location, shadows, and reflections in the painted area. Compare versions and export the PNG.

The Mac bundle in dist/ is currently a development app: it uses this repository's .venv/ and models/cache/. Copying the small app bundle to another computer without the engine and model will not work. A standalone signed and notarized distribution or Mac App Store release is a separate packaging task.

**Command-line edit:**

~~~sh
.venv/bin/python -m editlock edit \
  --image assets/demo/blue-mug.png \
  --instruction 'Change the blue mug to red while keeping the room unchanged' \
  --output outputs/my-edit.png
~~~

## How it is built

~~~mermaid
flowchart LR
    A[SwiftUI app or local browser] --> B[FastAPI service on 127.0.0.1]
    B --> C[Normalize and resize input]
    C --> D[FLUX.2 Klein 4B via MFLUX and MLX]
    D --> E{Mode}
    E -->|Instruction or guidance| F[Full-image result]
    E -->|Outside locking| G[Align, composite, verify outside pixels]
    F --> H[Preview, follow-up edit, PNG export]
    G --> H
~~~

The Python pipeline keeps the normalized original, prepares a model-sized image, and stores each edit in a local session. The service accepts one generation at a time to avoid competing GPU jobs. The SwiftUI app launches its local service and stops it when the app closes. The localhost editor uses a session token. The Python engine is also callable without either UI.

In locked mode, the mask is a hard *output* constraint imposed by EditLock's compositor; it is not passed to FLUX.2 as a native editing mask. The compositor feathers inward at the painted edge while leaving protected outside pixels untouched, then checks exact equality before export. This guarantees preservation outside the paint, not a convincing boundary or a successful requested edit.

## Evaluation

All measurements below were made on the 48 GB M5 Pro with pretrained FLUX.2 Klein 4B. They are separate evaluations with different inputs and purposes; their success rates must not be combined into one score.

### 24-case model baseline on Apple GIE-Bench

We selected three examples from each of eight edit types in [Apple's GIE-Bench](https://github.com/apple-aiml-research/ml-gie-bench): removal, addition, replacement, color, attribute, size, layout, and text. Each case supplied a source photo, written instruction, marked edit region, and evaluation question. The marked region was used **only for scoring**, never as model input. The 24 examples are a selected pilot, not an official score on the full dataset.

For each case, the unmodified FLUX.2 output was saved and visually compared with its source. One reviewer marked whether the instruction was visibly achieved. We separately compared pixels outside the dataset region at the same positions and recorded elapsed time and peak MLX memory.

| Model-baseline measure | Result | Meaning |
| --- | ---: | --- |
| Instructions visibly achieved | 21/24 (87.5%) | Manual judgment that the requested change appeared, even if something else drifted. |
| Mean wall time per edit | 6.96 s | Time through saved output with weights already downloaded; excludes the first download. |
| Highest reported peak MLX memory | 9.53 GB | Largest model-runtime memory report; not total Mac memory use. |
| Mean protected-area color difference | 13.68/255 | Average channel difference outside the marked region; zero is identical. |
| Mean protected-area PSNR | 23.52 dB | Image similarity outside the region; higher is better, not a pass/fail percentage. |
| Protected pixels changed by more than 10 color levels | 31.6% | Mean fraction where at least one RGB channel changed by more than 10/255. |
| Protected pixels exactly unchanged | 0.3% | Mean fraction where all RGB channels matched exactly. |

The three visible instruction misses were a brush-size change, a faucet-size change, and moving a metal pot. Raw FLUX.2 commonly regenerated content outside the requested region, which motivated the optional outside-locking mode.

### 24-case locked-workflow comparison

The same 24 photos, instructions, and dataset masks were sent through EditLock's locked path: preparation, generation, alignment, compositing, equality check, and PNG export. The input masks were supplied to EditLock for this test.

| Measure | Raw FLUX.2 | EditLock locked path |
| --- | ---: | ---: |
| Protected pixels exactly unchanged, mean | 0.3% | 100% |
| Cases with every protected pixel unchanged | Not counted | 24/24 |
| Mean wall time per edit | 6.96 s | 10.60 s |

The 100% number follows from replacing outside pixels with the normalized original and checking equality. It does **not** measure instruction success or boundary quality. Some dataset masks were too small for a complete edit: for example, a lamp-replacement mask covered about 1.6% of its photo and omitted part of the lamp. The 21/24 raw-model instruction count cannot be carried over to the locked output. The locked timing is from the first workflow run; a later full-image input change was not re-benchmarked across all 24 cases.

### 12-case car editing review

Twelve local car photos were edited in instruction-only mode with four model steps, seed 42, and a maximum 768-pixel model input side. The test covered car scale, night lighting, object removal, pavement, weather, body color, background replacement, rain, and headlights. The exact single-turn prompts and expected observations are in [the case manifest](eval/car_cases.json). No paint, fine-tuning, second model, or retry was used in the first pass.

| Measure | Single-turn result |
| --- | ---: |
| Completed edits | 12/12 |
| All requested parts visibly met | 7/12 |
| Partial: at least one missed part or preservation drift | 5/12 |
| No visible requested change | 0/12 |
| Mean wall time per edit | 9.56 s |
| Wall-time range | 6.93–17.00 s |
| Exported PNG dimensions equal source dimensions | 12/12 |

The five partial cases were retried as **sequential edits from the preceding result**, one change at a time. The same model, seed 42, and 768-pixel maximum were used; no training occurred.

| Case | Original request | Single turn | After follow-up | Observation |
| --- | --- | --- | --- | --- |
| C01 | Make the Koenigsegg smaller on the runway | Full | Full | Car became much smaller; scene remained recognizable. |
| C02 | Night racetrack, floodlights, reflections, gray Lamborghini | Partial | **Full**, 2 steps | Night and reflections appeared while gray finish was better retained. |
| C03 | Remove plaza columns behind yellow Lamborghini | Full | Full | Open plaza and yellow car remained clear. |
| C04 | Replace gravel and garden with paved street | Partial | **Full**, 2 steps | First replaced gravel, then the remaining garden strip. |
| C05 | Bright midday and paved shoulder instead of grass | Partial | **Full**, 2 steps | First changed lighting, then the grass. |
| C06 | Repaint Bentley emerald green | Full | Full | Color changed; shade was brighter than deep emerald. |
| C07 | Replace beach with city skyline at dusk | Full | Full | Skyline and dusk appeared; car stayed coherent. |
| C08 | Clear sunny seaside morning | Full | Full | Sky and water brightened while view remained recognizable. |
| C09 | Rain and wet road reflections while retaining car | Partial | **Full**, 2 steps | Wet pavement and rain appeared with better car-front retention. |
| C10 | Paved road, sunny sky, car 25% smaller | Partial | **Partial**, 3 steps | Road, sky, and color improved; car was still too large. |
| C11 | Repaint BMW M2 cobalt blue | Full | Full | Blue body, four lights, and dark studio remained. |
| C12 | Turn off four BMW headlights | Full | Full | Lamps went dark; car and studio remained. |

**Summary:** 7/12 full requests in one turn versus 11/12 after selectively using follow-up edits on the five partial cases. Four of those five improved to Full. These are one-reviewer judgments on a small, selected set, **not** a held-out benchmark or a claim of general 91.7% edit accuracy. The sequential run uses more model calls than the single-turn run. The original car photos and generated car outputs are local-only and are not included in this repository; the case manifest and runner remain here for transparency. Thus, the car visual ratings cannot be independently inspected from this Git checkout alone.

## Reproduce the evaluations

The GIE-Bench dataset and evaluation outputs are stored locally under ignored data/ and outputs/ directories. Obtain the public dataset from [Apple's GIE-Bench repository](https://github.com/apple-aiml-research/ml-gie-bench), place its gie_bench.json at data/gie-bench/gie_bench.json, then run:

~~~sh
.venv/bin/python scripts/prepare_gie_subset.py
.venv/bin/python scripts/run_gie_baseline.py
.venv/bin/python scripts/score_gie_baseline.py
.venv/bin/python scripts/run_editlock_comparison.py
.venv/bin/python scripts/make_gie_gallery.py
~~~

For the car review, place the same original photos at the paths listed in eval/car_cases.json under a local cars/ directory, then run:

~~~sh
.venv/bin/python scripts/run_car_eval.py
.venv/bin/python scripts/make_car_gallery.py
.venv/bin/python scripts/run_car_eval_retry.py
.venv/bin/python scripts/make_sequential_car_gallery.py
~~~

The car runner skips completed cases in its local run record. Use a fresh output location to re-run rather than silently comparing cached results. The five follow-up prompts are recorded in scripts/run_car_eval_retry.py.

## Limits and next release step

- Exact outside pixels in locked mode are an engineered constraint; an undersized paint area can clip a replacement, shadow, or reflection.
- Painted guidance is only an approximate location phrase. The model may ignore it or change other parts of the image.
- Full-image edits can redraw important details. Follow-up instructions improved four of five partial car examples but did not solve C10's size change.
- Visual ratings are subjective and based on small selected sets. There is no independent human study or held-out car accuracy score here.
- The current app bundle is tied to this repository. Distribution requires bundling the runtime and model, signing/notarizing, and testing a clean installation.

## Project layout

~~~text
EditLock/
├── README.md                 One project document
├── Package.swift             Swift package manifest
├── Sources/EditLockMac/      Native SwiftUI app
├── editlock/                 Python engine, local API, browser editor
├── eval/car_cases.json       Car review prompts and criteria
├── scripts/                  Build and evaluation tools
├── tests/                    Python pipeline and API tests
└── assets/demo/              Model-generated shareable example
~~~

Ignored local directories are .venv/, models/, data/, cars/, outputs/, .build/, and dist/. The FLUX.2 model and MFLUX are upstream works with their own licenses; this project's contribution is the local editing workflow, optional guidance and locking, follow-up editing, two interfaces, and evaluation.

Run the lightweight code checks with:

~~~sh
.venv/bin/python -m unittest discover -s tests -q
~~~
