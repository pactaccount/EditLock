# EditLock first workflow comparison

## What this run checks

The [baseline](BASELINE.md) sent each of 24 Apple GIE-Bench pilot photos and instructions directly to FLUX.2. This comparison sends the same photos, instructions, and dataset masks through EditLock's preparation, generation, alignment, compositing, and PNG export path. It asks whether the protected region stays exact after an edit. The run used one fixed seed per case on the 48 GB M5 Pro. It preceded a later change that gives the model the whole photo for inputs up to 1536 pixels; one case was rerun after that change and still preserved every protected pixel.

| Measurement | Raw FLUX.2 baseline | First EditLock workflow |
| --- | ---: | ---: |
| Cases | 24 | 24 |
| Protected pixels exactly unchanged, average | 0.3% | 100% |
| Cases with every protected pixel unchanged | Not measured as a case count | 24 of 24 |
| Average wall time per edit | 6.96 seconds | 10.60 seconds |

"Protected" means every pixel outside the provided mask. The comparison uses the decoded, orientation-corrected source photo as its reference. The exact-pixel result follows from the final composite and a strict equality check before PNG export. The 10.60-second average includes local model generation and the rest of EditLock's workflow under the preparation settings used for this run; it is not an isolated model speed benchmark or a timing estimate for the revised full-image path.

## Visual review

Several color and text edits remain recognizable after compositing, including the blue pot, red coffee machine, blue bowl, and note text. Some replacement, addition, removal, and movement edits are clipped or incomplete. The GIE-Bench region can cover only part of the object or omit the space a replacement needs. For example, the bedside lamp replacement mask covers about 1.6% of the photo, leaving part of the lamp protected; EditLock cannot remove those protected pixels. A full-image model input still cannot fix an undersized allowed area.

This run **does not establish a new instruction-success score** for EditLock. The baseline's 21/24 visual instruction result cannot be carried over after strict compositing. Product quality needs user-painted masks that cover the old object, new content, shadows, and reflections, followed by visual review. Both editors now provide a Margin control to enlarge the allowed area before generation or retry.

## Evidence and next quality check

The [24-case run records](outputs/gie_editlock/run.json) and [comparison sheets](outputs/gie_editlock/gallery_01.jpg) are local generated files. Sheets 2–6 are in the same folder. One browser edit was also completed end to end using the local web editor, with an unchanged protected region and a downloadable PNG.

The next product-quality review should use a small set of carefully painted masks, judge instruction success and boundary quality separately, and retain the exact-pixel check. These 24 dataset masks are useful for a hard preservation test, but too inconsistent for a definitive quality score of the interactive product.
