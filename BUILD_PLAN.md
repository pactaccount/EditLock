# High-level build plan

## Goal

Given an original image and a short edit instruction, produce an edited image locally. Optional paint helps indicate where to focus. Exact preservation outside the paint is an explicit choice.

## 1. Start with one model

Use the pretrained FLUX.2 Klein 4B checkpoint through MFLUX on Apple Silicon. It accepts an image and edit instruction. First measure whether it runs on the 48 GB M5 Pro, then test its edit quality. It does not accept a hard edit mask through this path, so the protected-region behavior must be built and evaluated separately. No fine-tuning is needed for the first milestone.

## 2. Establish the baseline

Run FLUX.2 on a fixed set of image-conditioned edits. Include simple object and background changes and difficult boundaries. Record whether the requested change happened, whether other content changed, visible edge artifacts, time per image, and peak memory. Use a suitable subset of Apple's GIE-Bench for an outside reference, plus a separate small set of permitted product photos for the actual use case.

## 3. Add the EditLock workflow

The user imports a photo and writes an instruction. FLUX.2 proposes a full-image edit. If the user paints, EditLock adds an approximate location cue to the model instruction without restricting the result. If the user explicitly turns on outside locking, EditLock places original pixels back outside the painted area and checks them. The user can compare results, adjust paint, or retry. Test seams and coherence when locking is on; pixel restoration alone does not make a convincing edit. The final export is a full-resolution image.

## 4. Compare against the baseline

On held-out images, compare instruction-only, guided, and locked edits. Evaluate instruction success, preservation when locking is enabled, edge quality, and end-to-end speed. Keep a gallery of failures as well as successes. Select prompts and settings on development images; report final results only on held-out images.

## 5. Build the Mac app

Use a simple local app with import, instruction entry, optional painting and erasing, preview, and export. Connect it to the local MFLUX inference pipeline. Keep all processing on the Mac.

## First milestone

One photo + one instruction produces a saved edit and before/after view without paint. Painted guidance and outside locking are additional paths. No fine-tuning is required for this milestone.
