# Fitting the model to the sheet

## What a fit is
For each sheet view, `camfit` solves the camera (and any pose extras) that make the model's class map
best match the sheet's: silhouette IoU (model dilated by the drawing's ink line) plus the mean IoU of
each colour class. Cameras land in `cams/<set>/<view>.json`; `out/fit/<set>_<view>.png` shows sheet |
model | overlay | difference. The Blender renders and `compose` give the final IoU per view.

## Order of work
1. Rough generator from measurements, then `fit all --grid` once. Look at every difference panel.
2. Fix whole-part errors in the generator by hand (a tube in the wrong place, a head too small). The
   difference panel tells you where: red is model without drawing, blue is drawing without model.
3. `fit all` again (starts from saved cameras), then `refine` the few parameters that are genuinely
   uncertain, a handful at a time with sensible steps (1-2 cm, a few degrees).
4. Fold accepted refine values into `gen.py`; re-fit; build; check.

## Poses
Sheets draw iso, top and bottom views in a different pose (crouching, arms out). Give those views pose
extras with joint limits (`fit_extra`): left and right limbs independent when the drawings require it. Moving parts also vary between views.

## Reading the scores
- Scores depend on the drawing, camera, geometry and segmentation; no universal expected score is claimed.
- Several views preferring different values of one parameter (the bike's top views each wanted a
  different width) means the drawings disagree. Pick the views that matter most to the game (usually
  the side and front) and report the rest.
- A spec that overrides the sheet (wheelbase, saddle height) lowers the fit of the delivered file on
  purpose; fit a sheet-proportioned variant to prove the design, deliver the spec variant.
- Stop when the remaining error is explained (sheet inconsistency, outline style, spec override).
  Chasing a perfect score with a rigid low-poly model wastes hours and distorts the shape.

## Practical notes
- Sheet backgrounds: PNG sheets are clean (`sheet_bg_tol` 13); generated JPEG sheets need 24 and
  `sheet_denoise`.
- A camera solve gets stuck when the start is far off: use `--grid`, or set `init` closer (az/el by
  eye, px/m from a known length, cx/cy at the drawing's centre).
- `nominal` keeps front/back/side cameras honest; without it the solver may rotate a front view 30
  degrees to hide a width error.
- Fits can run one process per view; measure runtime on the actual asset and hardware.
