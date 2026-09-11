# Golden reference renders

Committed reference images for the look regression suite
(`../blender/test_golden.py`). One EXR per look case per turntable view.

## Why these exist

Structural tests confirm a shader graph was *built*. They cannot tell you the
look *changed*. Swap two constants in `_warm_shadow` and every existing
assertion still passes — the graph builds, nodes are tagged, the terminator is
still a hard step, the shadow is still warmer than the base — while every cel
material in the project shifts hue.

That was verified, not assumed. Injecting exactly that swap fails **8 of 12**
case-views here.

## Running

```bash
# check for drift
.venv313/bin/python -m pytest marionette/tests/blender/test_golden.py

# approve an intentional change
.venv313/bin/python -m pytest marionette/tests/blender/test_golden.py --update-golden
```

`--update-golden` overwrites the references in place. **Look at the new images
before committing them** — the whole point is that the diff is reviewable. If
you cannot explain why a reference changed, the change is a bug.

A case with no reference yet writes one and fails once, telling you to inspect
and commit it. That way a new look can never silently establish a wrong
baseline.

## The metric

Comparison reports `changed_fraction`: the share of pixels where any RGB
channel moved by more than 0.01. The budget is 0.2% per case-view.

Mean absolute error is deliberately *not* the pass/fail metric. It is badly
insensitive to localized changes — the injected hue swap above scores a mean of
0.0016, which is indistinguishable from noise, while changing 13% of pixels.
Mean and max are still reported in failure messages for context.

Alpha is excluded. It is coverage rather than look, and any change to it
surfaces in RGB through the premultiplied result.

## Render settings

Three Blender defaults are wrong for measuring a quantized image, and all three
were found the hard way:

| setting | default | here | why |
|---|---|---|---|
| `use_denoising` | on | **off** | smooths flat regions — turned 2 exact colors into 350 |
| `filter_width` | 1.5px | **0.01** | blends neighbours across the terminator |
| format | PNG (8-bit) | **EXR float** | 8-bit splits each flat band across adjacent codes |

Plus `seed = 0` and adaptive sampling off, so repeat runs are identical. A
harness test asserts that two renders of the same scene match exactly.

## Scope

Cases cover looks that build *materials*. `PBRLook` and `StudioLook` only
configure render settings, which direct assertions already cover, and a
sampled area-light render is a poor golden: at 64 samples the references came
out 6–8 MB each of incompressible noise, versus 2–14 KB for the deterministic
cel renders.

`test_every_material_building_look_has_a_case` enforces this — add a look that
overrides `build_materials` without a golden case and the suite fails.

## Cross-machine note

References were captured on Apple Silicon with Cycles CPU. Rendering on a
different platform may shift edge antialiasing slightly. The 0.2% budget
absorbs a little of that, but if CI runs on different hardware, expect to
either regenerate there or widen `max_changed` for that environment.
