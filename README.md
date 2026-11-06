# EditLock

EditLock is a general-purpose, on-device image editor for Apple Silicon Macs. Import an image, describe a change, compare the result, and export a PNG. You can optionally paint a focus area, lock everything outside that area, or continue editing a result with a follow-up instruction.

The native interface is built with SwiftUI. The editing engine uses [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) through [MFLUX](https://github.com/mflux-community/mflux) and MLX. The model runs locally; no hosted inference service is required. A localhost browser interface is also included for development.

**Example instruction:** “Change only the blue ceramic mug to a bright red ceramic mug. Keep the shape, lighting, and room unchanged.”

| Input | Output |
| --- | --- |
| ![Blue mug](assets/demo/blue-mug.png) | ![Edited red mug](assets/demo/red-mug.png) |

## Editing modes

| Mode | Behavior |
| --- | --- |
| **Instruction only** | FLUX.2 edits the image from the written instruction. Other parts of the image may change. |
| **Painted guidance** | Paint and erase indicate an approximate focus area. This guides the prompt but does not restrict the output. |
| **Outside locking** | Paint defines where pixels may change. EditLock composites the result and verifies that all outside pixels match the normalized original exactly. |
| **Follow-up edit** | Use a result as the next input. Compare with the original or previous version, and undo a step. |

An outside lock can clip an edit if the paint does not include the whole change, including shadows, reflections, or an object's new location. PNG output matches the source image dimensions, but the model works on a resized input, so fine detail is not guaranteed to be preserved in edited areas.

## Run on a Mac

Tested on a **48 GB MacBook Pro M5 Pro**. This development build targets macOS 14+ on Apple Silicon. Other Mac configurations are untested. Install Python 3.13 and uv, and use a Swift toolchain to build the native app.

From the repository root:

~~~sh
UV_CACHE_DIR="$PWD/.cache/uv" uv venv --python 3.13 .venv
UV_CACHE_DIR="$PWD/.cache/uv" uv pip install --python .venv/bin/python -e '.[dev]'
mkdir -p models/cache outputs
HF_HOME="$PWD/models/cache" .venv/bin/mflux-generate-flux2 \
  --model flux2-klein-4b \
  --prompt 'A blue ceramic mug on a white table' \
  --steps 4 --seed 42 --width 512 --height 512 \
  --output outputs/first-model-test.png
~~~

The last command downloads the model on first use. The local model cache is about 15 GB.

**Native Mac app:**

~~~sh
scripts/build_mac_app.sh
open dist/EditLock.app
~~~

**Local browser interface:**

~~~sh
.venv/bin/python -m editlock web --port 8765
~~~

Open the localhost URL printed by that command. The browser talks only to a service on this Mac. The native app starts the same local engine itself. Both interfaces support instructions, optional painting, comparison, follow-up edits, and PNG export.

**Command-line edit:**

~~~sh
.venv/bin/python -m editlock edit \
  --image assets/demo/blue-mug.png \
  --instruction 'Change the blue mug to red' \
  --output outputs/my-edit.png
~~~

The app in dist/ currently depends on this checkout's Python environment and model cache. It is a development build, not a standalone installer.

## How it works

The SwiftUI app or browser sends a photo and instruction to a FastAPI service bound to 127.0.0.1. The Python engine normalizes the photo, prepares a model-sized input, runs FLUX.2 locally, and saves the candidate. Instruction-only and guided modes export the full model output. Locked mode aligns and composites the candidate inside the painted area, then checks outside pixels before export. The service runs one generation at a time.

The model does **not** receive a hard mask in this implementation; exact outside preservation is provided by EditLock's compositor. Follow-up editing passes the previous output into the same pipeline as a new input. The original and intermediate outputs remain in local sessions.

## Evaluation

These are small local tests on the 48 GB M5 Pro, not published benchmark scores or a claim of general accuracy.

| Test | Result | What it means |
| --- | --- | --- |
| 24 selected [Apple GIE-Bench](https://github.com/apple-aiml-research/ml-gie-bench) cases, raw model | 21/24 requested changes visibly appeared | One-reviewer visual judgment; the model sometimes changed other content. |
| Same 24 cases, protected pixels | 0.3% exactly unchanged with raw model; **100%** with EditLock locked mode | The locked result copies outside pixels from the source and verifies equality. This does not measure edit quality. |
| Same 24 cases, mean edit time | 6.96 s raw; 10.60 s locked workflow | Local run times with cached model weights; the locked run predates a later full-image input change. |
| Separate 12-photo exploratory review | 7/12 full requests in one edit; 11/12 after selectively using follow-up edits | The set used car photos to exercise varied instructions. One reviewer scored it; original photos and outputs are not published here, so this number is not independently verifiable from this checkout. |

The 24-case pilot used three examples each of removal, addition, replacement, color, attribute, size, layout, and text edits. The dataset region was used to measure preservation, not passed to the raw model. The locked workflow used that region as its paint mask. Some dataset masks were too small for visually complete edits, so the 21/24 raw-model instruction result cannot be transferred to locked mode.

To run a new evaluation on your own images, use the single generic tool:

~~~sh
.venv/bin/python scripts/evaluate.py \
  --image assets/demo/blue-mug.png \
  --instruction 'Change the blue mug to red'
~~~

It saves the output, timing record, and an original/output comparison sheet under outputs/evaluation/. For multiple images or follow-up steps, pass a JSON list with --manifest. Each item has an id, image path, and either an instruction or a list of instructions; optional mode and mask fields enable painted or locked evaluations. Visual success still needs human review.

## Project structure

~~~text
EditLock/
├── README.md                  Project documentation
├── Package.swift              Swift package
├── pyproject.toml             Python dependencies
├── Sources/EditLockMac/
│   └── EditLockApp.swift      Complete native Mac interface
├── editlock/
│   ├── __init__.py            Model, pipeline, local API, CLI
│   ├── __main__.py            Python module entry point
│   └── web/index.html         Local browser interface
├── scripts/
│   ├── build_mac_app.sh       Native build
│   └── evaluate.py            Generic image-edit evaluation
├── tests/test_editlock.py     Engine and API checks
└── assets/demo/              Shareable model-generated example
~~~

Local photos, model weights, evaluation data, generated outputs, the Python environment, and built apps are excluded from Git. FLUX.2 and MFLUX are upstream projects with their own licenses.

Run the code checks with:

~~~sh
.venv/bin/python -m unittest discover -s tests -q
~~~
