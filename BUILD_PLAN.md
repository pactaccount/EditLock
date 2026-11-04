# High-level build plan

## Goal

Given an original image, a short edit instruction, and a user-selected edit area, produce an edited image that follows the instruction without changing protected areas.

## 1. Start with one model

Use the pretrained Stable Diffusion v1.5 Inpainting checkpoint through Diffusers on the Mac's MPS backend. Begin with 512 px images and one image at a time. Do not train or fine-tune until the baseline has been measured.

## 2. Establish the baseline

Run the model on a fixed set of masked edits. Include simple object and background changes and some difficult boundaries. Record whether the requested change happened, whether other content changed, visible edge artifacts, time per image, and peak memory. Use a suitable subset of Apple's GIE-Bench for an outside reference, plus a separate small set of permitted product photos for the actual use case.

## 3. Add the EditLock workflow

The user imports a photo, paints the area that may change, and writes an instruction. The inpainting model proposes an edit. EditLock places original pixels back outside the allowed area, checks the protected area and edit result, and shows the user options to accept, adjust the mask, or retry. The final export is a full-resolution image.

## 4. Compare against the baseline

On held-out images, compare ordinary inpainting with EditLock's locked output. Evaluate edit success, preservation outside the mask, edge quality, and end-to-end speed. Keep a gallery of failures as well as successes. Select prompts and settings on development images; report final results only on held-out images.

## 5. Build the Mac app

Use a simple local app with import, mask painting, instruction entry, preview, and export. Connect it to the local inference pipeline. Keep all processing on the Mac. Investigate Core ML conversion only after the MPS version works and a compatible inpainting path is verified.

## First milestone

One photo + one mask + one instruction produces a saved edit, with unmasked pixels identical to the original and a before/after view. No fine-tuning is required for this milestone.
