"""Dummy predictor — opens the WSI, then returns random probabilities.

What it proves:
    * The image's openslide install actually reads the slide file.
    * The recipe -> factory -> predict round-trip works end-to-end.
    * The CSV writer renders one row per slide with all class columns.

What it does NOT do:
    * Anything model-related. Replace this body with your real model.

Determinism:
    The "random" output is seeded by the slide's filename, so re-running
    on the same folder produces the same CSV. That makes diffing easy
    while you're wiring the pipeline up.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import numpy as np

from onco_run.helpers.slide_io import Slide  # opt-in helper


log = logging.getLogger(__name__)


class DummyPredictor:
    def __init__(self, classes: list[str], thumbnail_max_dim: int = 1024) -> None:
        self.classes = classes
        self.thumbnail_max_dim = thumbnail_max_dim

    def predict(self, slide_path: Path) -> np.ndarray:
        # 1) Actually open the WSI to prove openslide works inside the container.
        with Slide(slide_path) as s:
            info = s.info()
            # Read a thumbnail too — exercises decode + level lookup.
            thumb = s.thumbnail(max_dim=self.thumbnail_max_dim)

        log.info(
            "slide=%s  dims=%dx%d  mpp=%s  levels=%d  thumb=%dx%d",
            slide_path.name,
            info.width, info.height,
            f"{info.mpp:.3f}" if info.mpp else "?",
            info.level_count,
            thumb.shape[1], thumb.shape[0],
        )

        # 2) Return deterministic-random probabilities seeded by the file name.
        #    Real predictors put their model output here.
        seed = int(hashlib.md5(slide_path.name.encode()).hexdigest()[:8], 16)
        rng = np.random.default_rng(seed)
        logits = rng.normal(size=len(self.classes))
        e = np.exp(logits - logits.max())
        return e / e.sum()


def build_predictor(*, classes, recipe_dir, thumbnail_max_dim: int = 1024, **_):
    """Factory called by onco_run with the recipe's `predictor.config`.

    `recipe_dir` is supplied automatically (a pathlib.Path to the folder
    containing the recipe). This dummy doesn't need it; real predictors
    typically use it to resolve relative weight paths.
    """
    return DummyPredictor(
        classes=list(classes),
        thumbnail_max_dim=int(thumbnail_max_dim),
    )
