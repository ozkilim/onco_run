# Predictors

Drop your model code here. The framework imports whatever module the
recipe points at and calls a factory — that's the entire contract.

## The contract

A predictor is any object exposing two things:

```python
class MyPredictor:
    classes: list[str] = ["A", "B", "C"]

    def predict(self, slide_path: pathlib.Path):
        # do whatever — tile, foundation features, full-slide CNN,
        # multi-resolution, segmentation-then-classify, anything.
        return probs  # length-N array, list, or {class: prob} dict
```

Probabilities can be returned as:
- a 1-D `numpy.ndarray` of length `len(classes)`,
- a list/tuple of floats of the same length, or
- a `dict` keyed by class name.

They must be non-negative; if they don't sum to 1 we'll renormalize and
log a warning.

## The factory

The recipe points at a callable named (by default) `build_predictor`.
It receives the recipe's `predictor.config` as kwargs, plus a
`recipe_dir: pathlib.Path` kwarg you can use to resolve relative paths:

```python
def build_predictor(*, weights, recipe_dir, **_):
    weights_path = (recipe_dir / weights).resolve()
    return MyPredictor(weights_path)
```

Use `**_` (or accept everything you don't care about) so that adding
new keys to the recipe never breaks old factories.

## Where to put files

Two equivalent options:

1. **As an importable module under `predictors/`.** The image puts
   `/app` on `PYTHONPATH`, so `predictors/my_model.py` is importable
   as `predictors.my_model` and the recipe says:

   ```yaml
   predictor:
     module: predictors.my_model
     factory: build_predictor
     config:
       weights: ../models/my_weights.pt
   ```

2. **As a free-standing `.py` file.** Point the recipe at it:

   ```yaml
   predictor:
     path: ../predictors/my_model.py
     config: { weights: ../models/my_weights.pt }
   ```

   The path is resolved relative to the recipe file.

## What's in the runtime

The Docker image ships with sensible defaults so most predictors don't
need a custom container:

- `torch`, `torchvision`
- `numpy`, `pandas`, `Pillow`
- `openslide-python` (and the `openslide` system library)
- `scikit-image`, `scipy`
- `h5py`, `pyyaml`, `tqdm`

Need more? Drop a `predictors/requirements.txt` (or
`predictors/<your_model>/requirements.txt`) and the build will
`pip install -r` it on top.

## Optional helpers

If WSI IO and tissue-aware tiling are useful to you (they often are),
import the helpers — they don't impose any opinion on your model:

```python
from onco_run.helpers.slide_io import Slide
from onco_run.helpers.tiling import plan_tiles, read_tile

with Slide(slide_path) as s:
    grid = plan_tiles(s, tile_size=256, mpp=0.5)
    for i in range(len(grid.coords_l0)):
        tile = read_tile(s, grid, i)   # uint8 HxWx3
        ...
```

You are free to ignore them entirely.

## Example

See `example_predictor.py` in this folder for a minimal, runnable
example you can copy.
