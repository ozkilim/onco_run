"""onco_run: model-agnostic WSI inference runner.

The framework is just a thin runner around a *predictor* that you write.
Everything model-specific (architecture, tiling, preprocessing, GPU
placement, batching) lives in your predictor; this package handles
slide discovery, calling your predictor, and writing a standard CSV.

Public surface:
    - Recipe / load_recipe       -> recipe schema + loader
    - SlidePredictor             -> the protocol your predictor implements
    - load_predictor             -> import a predictor from a recipe
    - run_pipeline               -> end-to-end runner for a folder of slides

Optional helpers (not required to use the framework) live under
`onco_run.helpers`.
"""

from .recipe import Recipe, load_recipe
from .predictor import SlidePredictor, load_predictor, normalize_probs
from .pipeline import run_pipeline, SlidePrediction

__all__ = [
    "Recipe",
    "load_recipe",
    "SlidePredictor",
    "load_predictor",
    "normalize_probs",
    "run_pipeline",
    "SlidePrediction",
]

__version__ = "0.1.0"
