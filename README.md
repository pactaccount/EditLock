# EditLock

EditLock is a local image-editing app for making a requested change while keeping user-selected parts of the original image intact.

**Example:** Change the background of a product photo while preserving the product and its logo.

This is a new, independent project. No model weights or benchmark images are stored in this repository.

See [BUILD_PLAN.md](BUILD_PLAN.md) for the high-level plan and success criteria.

## Starting points

- First product model: [SDXL Inpainting 0.1](https://huggingface.co/diffusers/stable-diffusion-xl-1.0-inpainting-0.1)
- Lightweight comparison baseline: [Stable Diffusion v1.5 Inpainting](https://huggingface.co/stable-diffusion-v1-5/stable-diffusion-inpainting)
- Later modern editing comparison: [FLUX.2 Klein 4B](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B)
- Local inference: [Hugging Face Diffusers](https://github.com/huggingface/diffusers) on Apple Silicon through PyTorch MPS
- External evaluation: Apple's [GIE-Bench](https://github.com/apple-aiml-research/ml-gie-bench)
- Later native deployment investigation: Apple's [Core ML Stable Diffusion](https://github.com/apple-aiml-research/ml-stable-diffusion). This is conversion and Swift deployment code, not the inpainting model selected above. Compatibility with that checkpoint must be checked before using it.

The upstream projects and model are separate works with their own licenses. EditLock's contribution is the protected-region workflow, evaluation, and application.
