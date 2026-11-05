# High-level build plan

## Goal

Given an original image, a short edit instruction, and a user-selected edit area, produce an edited image that follows the instruction without changing protected areas.

## 1. Start with one model

Use the pretrained FLUX.2 Klein 4B checkpoint through MFLUX on Apple Silicon. It accepts an image and edit instruction. First measure whether it runs on the 48 GB M5 Pro, then test its edit quality. It does not accept a hard edit mask through this path, so the protected-region behavior must be built and evaluated separately. No fine-tuning is needed for the first milestone.

## 2. Establish the baseline

Run FLUX.2 on a fixed set of image-conditioned edits. Include simple object and background changes and difficult boundaries. Record whether the requested change happened, whether other content changed, visible edge artifacts, time per image, and peak memory. Use a suitable subset of Apple's GIE-Bench for an outside reference, plus a separate small set of permitted product photos for the actual use case.

## 3. Add the EditLock workflow

The user imports a photo, paints the area that may change, and writes an instruction. FLUX.2 proposes an edit. EditLock places original pixels back outside the allowed area, checks the protected area and edit result, and shows the user options to accept, adjust the mask, or retry. Test seams and coherence at the mask boundary; pixel restoration alone does not make a convincing edit. The final export is a full-resolution image.

## 4. Compare against the baseline

On held-out images, compare FLUX.2's raw edit with EditLock's locked output. Evaluate edit success, preservation outside the mask, edge quality, and end-to-end speed. Keep a gallery of failures as well as successes. Select prompts and settings on development images; report final results only on held-out images.

## 5. Build the Mac app

Use a simple local app with import, mask painting, instruction entry, preview, and export. Connect it to the local MFLUX inference pipeline. Keep all processing on the Mac.

## First milestone

One photo + one mask + one instruction produces a saved edit, with unmasked pixels identical to the original and a before/after view. No fine-tuning is required for this milestone.
