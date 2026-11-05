# EditLock

EditLock is a local image editor that follows a written instruction. Painting is optional: it can suggest where to focus, or enable exact outside-pixel locking when needed.

**Example:** Change the color of a product from a written instruction. Paint the product if the model needs a location cue. Turn on outside locking only when unchanged pixels elsewhere are essential.

This is a new, independent project. Model weights and generated images stay local and are excluded from Git.

See [BUILD_PLAN.md](BUILD_PLAN.md) for the high-level plan and success criteria.
See [BASELINE.md](BASELINE.md) for the completed 24-case FLUX.2 evaluation and the build decision it supports.
See [ARCHITECTURE.md](ARCHITECTURE.md) for the engineering design and build order.
See [COMPARISON.md](COMPARISON.md) for the first full-workflow comparison and its limitations.
See [CAR_EVALUATION.md](CAR_EVALUATION.md) for 12 creative car-image instructions and their completed results.

## Use EditLock

From this directory, create the local Python environment and install the app dependencies if needed:

```sh
UV_CACHE_DIR="$PWD/.cache/uv" uv venv --python 3.13 .venv
UV_CACHE_DIR="$PWD/.cache/uv" uv pip install --python .venv/bin/python -e .
```

The FLUX.2 model files must already be in `models/cache/`. To use the browser editor, run:

```sh
.venv/bin/python -m editlock web --port 8765
```

Open the localhost URL printed by that command. Import a photo, enter an instruction, and choose **Generate edit**. You can also paint an optional focus area and erase parts of it. The model may still change areas outside that paint. Turn on **Keep everything outside the paint unchanged** only when you need exact outside pixels; then cover the entire intended change, including shadows or a new object's footprint. Use **Original / Result** to compare, then download the PNG. The browser only talks to a service on this Mac.

The native Mac demo uses the same engine:

```sh
scripts/build_mac_app.sh
open dist/EditLock.app
```

The Mac app currently uses this repository's `.venv` and local model cache. The browser editor is the simplest way to try the finished workflow. Outputs and edit sessions are saved under `outputs/` and are excluded from Git.

## Starting points

- First product model: [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), for image-conditioned editing
- Local Apple Silicon inference: [MFLUX](https://github.com/mflux-community/mflux) through MLX
- External evaluation: Apple's [GIE-Bench](https://github.com/apple-aiml-research/ml-gie-bench)

FLUX.2's image-conditioned editing does not directly enforce a painted mask. In the default mode, EditLock exports the model's full-image result. Optional paint becomes an approximate location cue in the instruction; Erase removes painted guidance. With outside locking enabled, a local compositor restores original pixels outside the paint and checks exact equality. Locking can clip an edit when the painted area is too small.

The upstream projects and model are separate works with their own licenses. EditLock's contribution is the local editing workflow, optional focus and locking modes, evaluation, and application.

## Model check on the 48 GB M5 Pro

FLUX.2 Klein 4B runs locally through MFLUX 0.24.0 and MLX 0.32.4. The model files are stored locally in `models/cache/` (about 15 GB). A 512 × 512, four-step image generation and an image-conditioned edit both completed successfully. The edit changed a blue mug to red; the room remained visually similar. This is a hardware and workflow smoke test, not proof of exact protected-region preservation.

| Run | Wall time | Peak MLX memory | Output |
| --- | ---: | ---: | --- |
| First generation, including model download | 221.88 s | 8.73 GB | `outputs/flux2-smoke.png` |
| Image-conditioned edit, with weights cached | 6.01 s | 9.06 GB | `outputs/flux2-edit-smoke.png` |

To repeat from this directory, use Python 3.13 and `uv`:

```sh
UV_CACHE_DIR="$PWD/.cache/uv" uv venv --python 3.13 .venv
UV_CACHE_DIR="$PWD/.cache/uv" uv pip install --python .venv/bin/python -e .
HF_HOME="$PWD/models/cache" .venv/bin/mflux-generate-flux2-edit \
  --model flux2-klein-4b \
  --image-paths outputs/flux2-smoke.png \
  --prompt 'Change only the blue ceramic mug to a bright red ceramic mug. Keep the mug shape, handle, lighting, and white room unchanged.' \
  --steps 4 --seed 42 --width 512 --height 512 \
  --output outputs/flux2-edit-smoke.png
```

The virtual environment, model files, and outputs are excluded from Git.
