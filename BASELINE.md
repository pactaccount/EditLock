# EditLock baseline evaluation report

## Why we ran this evaluation

EditLock has two jobs: make the change a person asks for, and leave everything outside the selected area alone. We needed to find out how much of those jobs FLUX.2 can already do before building EditLock's own area-protection feature.

This report describes the **original FLUX.2 output**. It is the starting point we will compare the finished EditLock workflow against.

## Dataset: what we used

We used a fixed **24-example subset** of [Apple's GIE-Bench](https://github.com/apple-aiml-research/ml-gie-bench), a dataset for evaluating image edits. Each example provides:

- An original photograph.
- A written instruction, such as “Change the color of the white pot to blue.”
- A marked region associated with the requested change.
- A question about whether the change happened.

We took three examples from each of eight kinds of edit: remove an object, add an object, replace an object, change a color, change an attribute, change size, move something, and change text. We selected photos relevant to products and everyday objects. This is a small, deliberately selected pilot set, **not a score for the full GIE-Bench dataset**.

## What we did with each example

1. We gave FLUX.2 the original photo and the dataset's exact written instruction.
2. We saved the edited photo it produced. We used the same model settings for all 24 examples and did not train or fine-tune the model.
3. We placed the original and edited photos side by side to check whether the requested change happened.
4. We used the dataset's marked region to check what changed elsewhere in the photo. The marked region was **not given to FLUX.2**; it was used only for evaluation.
5. We recorded how long each edit took and the highest memory use reported by the image-model runtime.

In this report, **editable area** means the marked region where the requested change is expected. **Protected area** means everything outside it, which EditLock should keep intact.

## The two questions we checked

### 1. Did the requested edit happen?

I visually reviewed the before-and-after comparisons. An edit counted as successful when the requested change was clearly present. This check does **not** excuse unwanted changes elsewhere; those are captured by the second question.

FLUX.2 visibly completed **21 of 24 instructions (87.5%)**. The three misses were a brush-size change, a faucet-size change, and moving a metal pot. The color change to the blue pot is an example that worked.

### 2. Did the protected area stay the same?

We compared the original and edited photos outside the marked region, at the same pixel positions. This is the central question for EditLock's promise. FLUX.2 often made the requested edit but also changed other content. In one example, it added a solar light above a sign and changed the daylight scene to night. That example passes the first question and performs poorly on the second.

## Measurements and what each one means

The table gives the results. The explanations below it say exactly how to read each number.

| Measurement | Result across 24 examples |
| --- | ---: |
| Instructions visibly achieved | 21 of 24 (87.5%) |
| Average time per edit | 6.96 seconds |
| Highest reported peak MLX memory | 9.53 GB |
| Average color difference in protected area | 13.68 out of 255 |
| Average PSNR in protected area | 23.52 dB |
| Protected pixels changed by more than 10 color levels | 31.6% on average |
| Protected pixels exactly unchanged | 0.3% on average |

### Instructions visibly achieved — 21 of 24

This answers **“Did the edit happen?”** It is a manual yes/no judgment from the comparison images, not an automatic model score. A result can count as successful here even if the model also changed something it should have left alone. This is why we measure preservation separately.

### Average time per edit — 6.96 seconds

This is the average time from starting an edit to saving its result on the 48 GB M5 Pro. It includes starting the local model process, loading the already downloaded model, making the image, and writing the output file. It **does not include the first model download**. Individual examples took different amounts of time because the source photos had different dimensions.

### Highest reported peak MLX memory — 9.53 GB

This is the largest memory peak reported by the Apple Silicon image-model runtime during any of the 24 edits. It shows this model fit on this Mac for the tested image sizes. It is **not a measurement of all memory used by the computer or the entire app**.

### Average color difference in protected area — 13.68 out of 255

For the area that should stay untouched, we compared each color in the original and edited photos. A value of **0** would mean identical colors; larger values mean more change. The 13.68 result is averaged across protected pixels and then across the 24 examples. It gives us a simple number to compare against the future region-locking version of EditLock.

### Average PSNR in protected area — 23.52 dB

PSNR is another way to express how closely the protected part of the edited photo matches the original. **Higher is better**; it is not a percentage. We include it because image-editing evaluations commonly report it, but the number by itself is not a pass/fail grade. We will use the same measurement when comparing the protected EditLock output with this baseline.

### Protected pixels changed by more than 10 color levels — 31.6%

We counted a protected pixel when at least one of its red, green, or blue values changed by more than **10 on a 0–255 scale**. The 31.6% is the average share of such pixels per example. This threshold ignores the tiniest differences. It **does not mean that 31.6% of the picture looks ruined**; it means those pixels crossed a clear, consistent change threshold.

### Protected pixels exactly unchanged — 0.3%

This is the strictest check: all three color values must match the original pixel exactly. Only 0.3% of protected pixels did, on average. FLUX.2 produces a new version of the whole image, so even areas that look similar often have different pixel values. EditLock's own region-locking step should make this measure much higher outside the editable area.

## What the results tell us to build

FLUX.2 can make many of the requested edits and runs quickly on this Mac. Its raw output cannot serve as an EditLock export because it does not reliably preserve the protected area. The next build step is the **region-locking pipeline**: combine the generated edit with the original photo so pixels outside the editable region stay original, while the edge of the edit looks natural.

These results describe this 24-example pilot only. The instruction score is based on visual review, and the preservation numbers are our own product-focused measurements at fixed pixel positions. They are **not** Apple's full benchmark score or its automated question-answering result.

## Before-and-after comparisons and detailed results

The images and detailed results are stored locally and excluded from Git. After running the evaluation, open [comparison sheet 1](outputs/gie_baseline/gallery_01.jpg), [sheet 2](outputs/gie_baseline/gallery_02.jpg), [sheet 3](outputs/gie_baseline/gallery_03.jpg), [sheet 4](outputs/gie_baseline/gallery_04.jpg), [sheet 5](outputs/gie_baseline/gallery_05.jpg), and [sheet 6](outputs/gie_baseline/gallery_06.jpg). The [per-example measurements](outputs/gie_baseline/metrics.json) and [timing records](outputs/gie_baseline/run.json) are also available locally.

The reproducible preparation, run, scoring, and gallery scripts are in [scripts/](scripts/). The public dataset and source photos remain in data/; generated photos and results remain in outputs/.
