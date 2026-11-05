# EditLock

EditLock is a local image-editing app for making a requested change while keeping user-selected parts of the original image intact.

**Example:** Change the background of a product photo while preserving the product and its logo.

This is a new, independent project. Model weights and generated images stay local and are excluded from Git.

See [BUILD_PLAN.md](BUILD_PLAN.md) for the high-level plan and success criteria.

## Starting points

- First product model: [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B), for image-conditioned editing
- Local Apple Silicon inference: [MFLUX](https://github.com/mflux-community/mflux) through MLX
- External evaluation: Apple's [GIE-Bench](https://github.com/apple-aiml-research/ml-gie-bench)

FLUX.2's image-conditioned editing does not directly enforce a painted mask. EditLock will need its own region-preserving workflow and must test whether edits stay within the allowed area before claiming that behavior.

The upstream projects and model are separate works with their own licenses. EditLock's contribution is the protected-region workflow, evaluation, and application.

## Model check on the 48 GB M5 Pro

FLUX.2 Klein 4B runs locally through MFLUX 0.24.0 and MLX 0.32.4. The official checkpoint is cached in `models/cache/` (about 15 GB). A 512 × 512, four-step image generation and an image-conditioned edit both completed successfully. The edit changed a blue mug to red; the room remained visually similar. This is a hardware and workflow smoke test, not proof of exact protected-region preservation.

| Run | Wall time | Peak MLX memory | Output |
| --- | ---: | ---: | --- |
| First generation, including model download | 221.88 s | 8.73 GB | `outputs/flux2-smoke.png` |
| Image-conditioned edit, with weights cached | 6.01 s | 9.06 GB | `outputs/flux2-edit-smoke.png` |

To repeat from this directory, use Python 3.13 and `uv`:

```sh
UV_CACHE_DIR="$PWD/.cache/uv" uv venv --python 3.13 .venv
UV_CACHE_DIR="$PWD/.cache/uv" uv pip install --python .venv/bin/python mflux==0.24.0
HF_HOME="$PWD/models/cache" .venv/bin/mflux-generate-flux2-edit \
  --model flux2-klein-4b \
  --image-paths outputs/flux2-smoke.png \
  --prompt 'Change only the blue ceramic mug to a bright red ceramic mug. Keep the mug shape, handle, lighting, and white room unchanged.' \
  --steps 4 --seed 42 --width 512 --height 512 \
  --output outputs/flux2-edit-smoke.png
```

The checkpoint downloaded for this test has Hugging Face snapshot revision `e7b7dc27f91deacad38e78976d1f2b499d76a294`. The virtual environment, cache, and outputs are excluded from Git.
