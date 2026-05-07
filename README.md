# onco_run

A model-agnostic WSI inference runner that ships as a Docker image. The
runner does **only** the boring stuff: discover slide files, call your
predictor, write a CSV. Everything model-specific is yours.

```
                                 ┌─────────────────────┐
   you (model owner)             │  collaborator       │
   ─────────────────             │  ───────────────    │
   predictors/my_model.py ─┐     │   slides/           │
   models/*.pt           ──┤     │                     │
   recipes/my_recipe.yaml──┼──► build ─► onco_run.tar.gz ─► load + run
                           │     │                     │
                           └──►  one image             │   predictions.csv ──┐
                                 └─────────────────────┘                     │
                                  ◄──────────────── send back ───────────────┘
```

The shipping artifact is a single `.tar.gz` plus a one-line `run.sh` for
the recipient. They never read code, install Python, or download
weights. Their command is:

```bash
./run.sh /path/to/slides /path/to/output
```

---

## The contract (the whole framework)

You write a **predictor**: any object exposing two things.

```python
class MyPredictor:
    classes: list[str] = ["A", "B", "C"]

    def predict(self, slide_path: pathlib.Path):
        # whatever you want — tile, full-slide, multi-resolution,
        # foundation features, segmentation, anything.
        return probs   # length-N array, list, or {class: prob} dict
```

And a **factory** the runner calls once at startup:

```python
def build_predictor(*, weights, recipe_dir, **_):
    weights_path = (recipe_dir / weights).resolve()
    return MyPredictor(weights_path)
```

That's the entire surface. The runner imports your module, calls your
factory with the recipe's `config` (plus a `recipe_dir` kwarg for
resolving paths), and then calls `predict(slide_path)` once per slide.

See `predictors/README.md` for the full interface doc and
`predictors/example_predictor.py` for a copy-pasteable starting point.

---

## Repository layout

```
.
├── Dockerfile, docker-compose.yml, Makefile
├── pyproject.toml                # package definition (runner only)
├── recipes/
│   └── example.yaml              # recipe pointing at the example predictor
├── predictors/                   # your predictor code lives here
│   ├── README.md                 # interface documentation
│   ├── example_predictor.py      # minimal example
│   └── requirements.txt          # (optional) pip deps for predictors
├── models/                       # weights live here (gitignored)
├── src/onco_run/
│   ├── cli.py                    # `onco-run predict`
│   ├── pipeline.py               # iterate slides + call predictor
│   ├── predictor.py              # SlidePredictor protocol + dynamic loader
│   ├── recipe.py                 # tiny YAML schema
│   └── helpers/                  # opt-in slide_io + tiling utilities
├── scripts/
│   ├── build.sh                  # plain image build
│   ├── build_with_recipe.sh      # bake recipe + weights + predictors
│   └── package.sh                # docker save → sendable folder
├── deliverables/
│   ├── run.sh                    # what the recipient runs
│   └── README_FOR_RECIPIENT.md   # what the recipient reads
└── tests/                        # recipe / predictor / pipeline tests
```

---

## The recipe

A recipe says: which predictor module, what classes, what config. That's
it. See `recipes/example.yaml`:

```yaml
name: example_dummy
classes: ["A", "B", "C"]

predictor:
  module: predictors.example_predictor    # python import path
  factory: build_predictor                # default; can omit
  config:                                 # passed verbatim as kwargs
    classes: ["A", "B", "C"]
    thumbnail_max_dim: 1024

output:
  csv_name: predictions.csv

slide_extensions: [svs, tif, tiff, ndpi, mrxs, scn, bif, vms, vmu]
```

You can also point at a stand-alone file:

```yaml
predictor:
  path: ../predictors/my_one_off.py
  config: { weights: ../models/x.pt }
```

Paths under `predictor.config` are *not* auto-resolved — the runner
passes `recipe_dir: pathlib.Path` to your factory and you resolve them
yourself if you want them relative to the recipe file.

---

## What the image bundles

So that most predictors don't need a custom container, the image ships:

- `torch`, `torchvision`
- `numpy`, `pandas`, `Pillow`
- `openslide-python` + the `openslide` system library
- `scikit-image`, `scipy`, `h5py`, `pyyaml`, `tqdm`
- the `onco_run` runner itself
- the optional helpers `onco_run.helpers.slide_io` and
  `onco_run.helpers.tiling` (use them or don't)

Need more? Drop `predictors/requirements.txt` and the build will
`pip install -r` it on top.

---

## Building the image

Generic image (no recipe baked in):

```bash
make build                      # CUDA, tag onco-run:latest
make build-cpu                  # CPU base
```

Bake a specific recipe + predictor + weights into the image so the
deliverable is a single tarball with **everything** inside:

```bash
make bake \
    RECIPE=recipes/my_recipe.yaml \
    WEIGHTS_DIR=models \
    TAG=onco-run:my_model_v1
```

`scripts/build_with_recipe.sh` stages the recipe + weights into the
build context before `docker build`, so anything the recipe references
under `models/` and `predictors/` ends up inside the image.

---

## Running locally

```bash
make run \
    SLIDES_DIR=./slides \
    OUTPUT_DIR=./output \
    RECIPE=recipes/example.yaml \
    TAG=onco-run:latest
```

CPU equivalent: `make run-cpu`. Output: `./output/predictions.csv` plus
`run_summary.json` and `run.log`.

For interactive debugging:

```bash
make shell TAG=onco-run:latest
# inside:
onco-run predict --recipe /app/recipes/recipe.yaml \
                 --slides /data/slides \
                 --output /data/output
```

---

## Onboarding a collaborator on the same server

If your collaborators get accounts on the same box (no tarball shipping
needed), bake the image once and run the onboarding script per user:

```bash
# One-time, as admin:
make bake RECIPE=recipes/example.yaml TAG=onco-run:dummy_v1

# Per collaborator (alice emails you her ~/.ssh/id_ed25519.pub first):
sudo ./scripts/onboard_collaborator.sh alice \
    --image onco-run:dummy_v1 \
    --create-user \
    --ssh-key /tmp/alice.pub
```

The collaborator only sends you their **public** key — the matching
private key never leaves their machine. If they don't already have a
key, they generate one with `ssh-keygen -t ed25519` and email you
`~/.ssh/id_ed25519.pub` (a single line of text, safe to share).

This creates `/home/alice/onco_run/{slides,output}` with a self-contained
`run.sh`, adds `alice` to the `docker` group, and prints a one-paragraph
SSH instruction blob you can paste to her. Her workflow becomes:

```bash
ssh alice@host
newgrp docker            # one-time, picks up the docker group
cd ~/onco_run
cp /path/to/wsis/*.svs slides/
./run.sh
# then send back ~/onco_run/output/predictions.csv
```

Output files are owned by the user (the wrapper passes `-u $(id -u):$(id -g)`
so docker doesn't write root-owned files into their home).

## Shipping to a remote collaborator

If they're on a different machine, once the image is baked:

```bash
make package TAG=onco-run:my_model_v1
```

This creates `dist/onco_run_<timestamp>/` containing:

- `onco_run_image.tar.gz` (the image)
- `run.sh` (one-shot loader + runner; image tag pre-stamped)
- `README.md` (recipient instructions)

Send the entire folder. The recipient runs:

```bash
./run.sh /path/to/their/slides /path/to/output
```

…and emails you back `predictions.csv` and `run_summary.json`.

---

## Output format

`predictions.csv` columns:

| `slide_id` | `slide_path` | `status` | `predicted_class` | `prob_<class>` (one column per class) | `elapsed_s` | `error` |

`status` is `ok` or `error`. The runner emits a row per slide so you can
see exactly what happened.

---

## Tests

```bash
pip install -e ".[test]"
pytest -q
```

The test suite covers recipe parsing, dynamic predictor loading,
output normalization, and end-to-end pipeline behaviour (using a
synthetic predictor and synthetic slides — no WSIs needed for the
runner-level tests).
