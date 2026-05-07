"""Recipe schema.

A recipe is the single source of truth for a deployment. It names the
predictor module/file, declares the output classes, and forwards a
free-form `config` dict to the user's factory.

The framework is intentionally agnostic about everything else: tile
size, model architecture, preprocessing, batching — none of that lives
here. Whatever your factory wants, put it in `predictor.config`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


SLIDE_EXTENSIONS_DEFAULT: tuple[str, ...] = (
    "svs", "tif", "tiff", "ndpi", "mrxs", "scn", "vms", "vmu",
    "bif", "czi", "dcm", "qptiff", "isyntax", "svslide",
)


@dataclass
class PredictorConfig:
    module: str | None = None        # e.g. "predictors.my_model"
    path: str | None = None          # alt: path to a .py file (recipe-relative)
    factory: str = "build_predictor"
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class OutputConfig:
    csv_name: str = "predictions.csv"


@dataclass
class Recipe:
    name: str
    classes: list[str]
    predictor: PredictorConfig
    output: OutputConfig = field(default_factory=OutputConfig)
    slide_extensions: tuple[str, ...] = SLIDE_EXTENSIONS_DEFAULT
    description: str = ""
    base_dir: Path = field(default_factory=lambda: Path("."))


def load_recipe(path: str | Path) -> Recipe:
    """Load and validate a YAML recipe file."""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"Recipe not found: {p}")
    with p.open("r") as fh:
        raw = yaml.safe_load(fh) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Recipe must be a YAML mapping, got: {type(raw).__name__}")

    for required in ("predictor", "classes"):
        if required not in raw:
            raise ValueError(f"Recipe is missing required field: '{required}'")

    classes = list(raw["classes"])
    if not classes:
        raise ValueError("recipe.classes must be a non-empty list")

    pred_raw = raw["predictor"] or {}
    if not pred_raw.get("module") and not pred_raw.get("path"):
        raise ValueError(
            "recipe.predictor must set `module` (e.g. predictors.my_model) "
            "or `path` (e.g. ../predictors/my_model.py)"
        )
    predictor = PredictorConfig(
        module=pred_raw.get("module"),
        path=pred_raw.get("path"),
        factory=str(pred_raw.get("factory", "build_predictor")),
        config=dict(pred_raw.get("config") or {}),
    )

    out_raw = raw.get("output") or {}
    output = OutputConfig(csv_name=str(out_raw.get("csv_name", "predictions.csv")))

    extensions = raw.get("slide_extensions") or SLIDE_EXTENSIONS_DEFAULT
    extensions = tuple(str(e).lower().lstrip(".") for e in extensions)

    return Recipe(
        name=str(raw.get("name", p.stem)),
        classes=[str(c) for c in classes],
        predictor=predictor,
        output=output,
        slide_extensions=extensions,
        description=str(raw.get("description", "")),
        base_dir=p.parent,
    )
