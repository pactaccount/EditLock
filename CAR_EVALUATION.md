# Car image edit evaluation

November 4, 2026 · EditLock on a 48 GB MacBook Pro M5 Pro

## What was tested

I used the 12 images in the local `cars/` folder and wrote one fixed instruction for each. The instructions cover car scale, nighttime lighting, object removal, ground replacement, weather, body color, background replacement, rain, a three-part scene edit, and headlight state. All runs used **FLUX.2 Klein 4B**, EditLock's **instruction-only** mode, four inference steps, seed 42, and a maximum 768-pixel model input side. No paint, outside locking, fine-tuning, prompt retry, or second model was used. The exported PNGs match each source image's pixel dimensions; the model still generates at a smaller internal size, so this is not a claim of original-detail preservation.

The [case manifest](eval/car_cases.json) contains the exact prompts and expected observations. [Run records](outputs/car_eval/run.json) and all results are saved locally under `outputs/car_eval/`. The original car images and generated results are not committed to Git.

## Result at a glance

| Measure | Result |
| --- | ---: |
| Edits completed | 12 of 12 |
| All requested parts visibly met | 7 of 12 |
| At least one requested part missed or a preservation detail drifted | 5 of 12 |
| No visible requested change | 0 of 12 |
| Average wall time per edit | 9.56 s |
| Wall-time range | 6.93–17.00 s |
| Output pixel dimensions match source | 12 of 12 |

These are **one-reviewer visual judgments** of a small, selected set. A full result means the main requested changes and major preservation constraints are visibly satisfied. A partial result means at least one requested change happened but another clause was missed or a car detail drifted. The timing includes preparation, model generation, and PNG export for these runs. It is not a full dataset score or an independent human study.

## Cases and observations

| ID | Image and instruction | Result | What the result shows |
| --- | --- | --- | --- |
| **C01** | Silver Koenigsegg: move it farther down the runway so it appears about half-size; retain cloudy runway scene. | **Full** | Car is much smaller and farther away; runway and cloudy setting remain recognizable. |
| **C02** | Gray Lamborghini at racetrack: change daylight to night with floodlights and reflections; retain matte gray car and racing angle. | **Partial** | Night track, floodlights, and reflections appear. The car becomes noticeably lighter and some body details drift. |
| **C03** | Yellow Lamborghini at plaza: remove the tall columns and make an open plaza; retain car and sunny paving. | **Full** | Columns are removed; the open plaza, yellow car, and daylight read clearly. |
| **C04** | Dark green Aston Martin: replace gravel and garden strip with paved street; retain brick building and car. | **Partial** | Gravel becomes an asphalt street, and the car/building remain. Most of the garden strip is still present. |
| **C05** | White Koenigsegg on mountain runway: make bright midday, remove roadside grass, add paved shoulder, retain car position. | **Partial** | Midday lighting appears and the car remains near its position. Green grass still lines much of the road. |
| **C06** | Silver Bentley on a bend: repaint body emerald green; retain details, road, trees, and motion blur. | **Full** | Body becomes green; car form and moving-road context remain. Shade is brighter than a deep emerald. |
| **C07** | Blue Lamborghini by ocean: replace beach with modern city skyline at dusk; retain car, asphalt, and camera angle. | **Full** | Skyline and dusk appear, with car and foreground still coherent. |
| **C08** | Rear-view blue Lamborghini by ocean: make clear sunny morning and brighter water; retain car, fence, and view. | **Full** | Sky and sea brighten; car, fence, and viewpoint remain recognizable. |
| **C09** | Silver Koenigsegg on forest road: add rain, wet asphalt, and reflections; retain car view and winding road. | **Partial** | Rain and wet reflections are strong. The road and view remain, but the car's front details are redrawn. |
| **C10** | Front-view BMW in grass: add paved road, sunny afternoon, and make car 25% smaller. | **Partial** | Road and sunny weather appear. The car is not clearly smaller and its dark body becomes yellow-green. |
| **C11** | Silver BMW M2 in studio: repaint cobalt blue; retain four headlights, front view, and dark studio. | **Full** | Blue body, lit lamps, frontal composition, and studio setting are present. |
| **C12** | Silver BMW in studio: turn off all four circular headlights; retain body, front view, and dark studio. | **Full** | Lamps become dark while the silver car and studio composition remain. |

The [before-and-after sheets](outputs/car_eval/gallery_01.jpg) make the visual judgments reviewable: [sheet 2](outputs/car_eval/gallery_02.jpg), [sheet 3](outputs/car_eval/gallery_03.jpg), and [sheet 4](outputs/car_eval/gallery_04.jpg).

## What this reveals

EditLock's instruction-only path can produce convincing changes across color, weather, lighting, removal, and large background swaps on this set. The main weak spot is **satisfying every clause of a combined instruction while retaining exact car attributes**. C05 missed grass removal; C10 missed car shrinkage and changed body color; C02 and C09 changed car details while satisfying weather/lighting requests. This points to a product improvement: show the requested sub-changes as a short checklist during review, then let the user retry the missed clause as a follow-up edit. These results do not yet justify fine-tuning or adding a second model as a judge.

## Reproduce locally

With the same local `cars/` images and model cache:

```sh
.venv/bin/python scripts/run_car_eval.py
.venv/bin/python scripts/make_car_gallery.py
```

The runner resumes from completed cases in `outputs/car_eval/run.json`. To do a fresh run, use a separate output directory or remove the local run records and outputs first; the script intentionally does not overwrite completed cases.
