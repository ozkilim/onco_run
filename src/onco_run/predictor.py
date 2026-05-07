"""The single contract this image cares about.

A *predictor* is any object that exposes:

    classes : list[str]
    predict(slide_path: pathlib.Path) -> np.ndarray | Sequence[float] | dict[str, float]

`predict` returns either:
    * a 1-D array of length `len(classes)` with class probabilities, or
    * a mapping {class_name: probability}.

How the predictor goes from a slide file to those probabilities is
entirely up to the model owner. Tile, don't tile, multi-resolution,
foundation features, segmentation-then-classify, end-to-end CNN — none
of it is the framework's business.

Predictors are produced by a *factory*: a top-level callable in a Python
module the recipe points at. The factory receives the recipe's `config`
dict as kwargs, plus a special `recipe_dir` kwarg (a `pathlib.Path` to
the directory containing the recipe) so it can resolve relative weight
paths if it wants to.

Example factory:

    def build_predictor(*, weights, recipe_dir, **_):
        weights_path = (recipe_dir / weights).resolve()
        return MyPredictor(weights_path)
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence, Union, runtime_checkable

import numpy as np

from .recipe import PredictorConfig


log = logging.getLogger(__name__)

ProbsLike = Union[np.ndarray, Sequence[float], Mapping[str, float]]


@runtime_checkable
class SlidePredictor(Protocol):
    classes: Sequence[str]

    def predict(self, slide_path: Path) -> ProbsLike: ...


def load_predictor(cfg: PredictorConfig, recipe_dir: Path) -> SlidePredictor:
    """Import the user's predictor module and call its factory.

    The factory may live in two places:
        * `predictor.module` — a regular Python import path. The image
          puts /app on PYTHONPATH so `predictors.foo` works for any file
          dropped into `predictors/`.
        * `predictor.path`   — a path to a `.py` file (resolved relative
          to the recipe). Useful for one-off scripts that aren't packaged.

    `predictor.factory` defaults to `build_predictor`.
    """
    module = _import_module(cfg, recipe_dir)
    factory_name = cfg.factory or "build_predictor"
    if not hasattr(module, factory_name):
        raise AttributeError(
            f"Predictor module '{module.__name__}' has no callable '{factory_name}'. "
            f"Define `def {factory_name}(...)` returning your predictor."
        )
    factory = getattr(module, factory_name)
    if not callable(factory):
        raise TypeError(f"{module.__name__}.{factory_name} is not callable.")

    kwargs: dict[str, Any] = dict(cfg.config or {})
    kwargs.setdefault("recipe_dir", recipe_dir)

    log.info(
        "Building predictor via %s.%s(%s)",
        module.__name__,
        factory_name,
        ", ".join(sorted(kwargs.keys())),
    )
    predictor = factory(**kwargs)
    _validate(predictor)
    return predictor


def _import_module(cfg: PredictorConfig, recipe_dir: Path):
    if cfg.path:
        p = Path(cfg.path)
        if not p.is_absolute():
            p = (recipe_dir / p).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Predictor file not found: {p}")
        # Use a stable, deterministic module name so `inspect`-style tools
        # don't get confused by repeated runs.
        module_name = f"onco_run_user_predictor_{p.stem}"
        spec = importlib.util.spec_from_file_location(module_name, p)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load predictor from {p}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module

    if cfg.module:
        return importlib.import_module(cfg.module)

    raise ValueError("recipe.predictor must set either `module` or `path`.")


def _validate(predictor: Any) -> None:
    if not hasattr(predictor, "classes"):
        raise TypeError("Predictor is missing required attribute `classes`.")
    if not hasattr(predictor, "predict") or not callable(predictor.predict):
        raise TypeError("Predictor is missing callable `predict(slide_path)`.")
    classes = list(predictor.classes)
    if not classes:
        raise ValueError("Predictor.classes must be a non-empty sequence.")


def normalize_probs(out: ProbsLike, classes: Sequence[str]) -> np.ndarray:
    """Coerce a predictor's output to a (len(classes),) float array.

    Accepts arrays, lists/tuples, or dicts keyed by class name. We do
    *not* implicitly softmax — predictors are expected to return
    probabilities. We do, however, normalize gentle drift (sum != 1) by
    a single division when the inputs are non-negative, and bail loudly
    otherwise so problems are visible early.
    """
    if isinstance(out, Mapping):
        missing = [c for c in classes if c not in out]
        if missing:
            raise ValueError(
                f"Predictor returned dict missing classes: {missing}. "
                f"Got keys: {list(out.keys())}"
            )
        arr = np.asarray([float(out[c]) for c in classes], dtype=np.float64)
    else:
        arr = np.asarray(list(out), dtype=np.float64)
        if arr.ndim != 1 or arr.shape[0] != len(classes):
            raise ValueError(
                f"Predictor returned shape {arr.shape}, expected ({len(classes)},) "
                f"matching classes={list(classes)}."
            )

    if np.any(arr < 0):
        raise ValueError(f"Predictor returned negative probability: {arr.tolist()}")

    s = float(arr.sum())
    if s <= 0:
        raise ValueError(f"Predictor returned all-zero probabilities: {arr.tolist()}")
    if not np.isclose(s, 1.0, atol=1e-3):
        log.warning("Probabilities sum to %.4f; renormalizing.", s)
        arr = arr / s
    return arr.astype(np.float32)
