"""Predictor protocol + dynamic loading tests."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import yaml

from onco_run.predictor import load_predictor, normalize_probs
from onco_run.recipe import load_recipe


PREDICTOR_FILE = """
import numpy as np

class P:
    classes = ["A", "B", "C"]
    def __init__(self, weight):
        self.weight = weight
    def predict(self, slide_path):
        return np.array([0.1, 0.2, 0.7])

def build_predictor(*, weight=0.5, recipe_dir, **_):
    return P(weight)
"""


def test_load_predictor_via_path(tmp_path: Path) -> None:
    pf = tmp_path / "my_predictor.py"
    pf.write_text(PREDICTOR_FILE)
    recipe = tmp_path / "r.yaml"
    recipe.write_text(yaml.safe_dump({
        "classes": ["A", "B", "C"],
        "predictor": {
            "path": "my_predictor.py",
            "config": {"weight": 0.9},
        },
    }))
    rec = load_recipe(recipe)
    p = load_predictor(rec.predictor, rec.base_dir)
    assert list(p.classes) == ["A", "B", "C"]
    out = p.predict(Path("/dev/null"))
    assert np.allclose(out, [0.1, 0.2, 0.7])


def test_normalize_probs_array() -> None:
    out = normalize_probs([0.1, 0.2, 0.7], ["A", "B", "C"])
    assert out.shape == (3,)
    assert np.isclose(out.sum(), 1.0)


def test_normalize_probs_dict() -> None:
    out = normalize_probs({"A": 0.5, "B": 0.5}, ["A", "B"])
    assert np.allclose(out, [0.5, 0.5])


def test_normalize_probs_renormalizes() -> None:
    out = normalize_probs([1.0, 1.0], ["A", "B"])
    assert np.isclose(out.sum(), 1.0)


def test_normalize_probs_rejects_negative() -> None:
    with pytest.raises(ValueError):
        normalize_probs([-0.1, 1.1], ["A", "B"])


def test_normalize_probs_rejects_wrong_shape() -> None:
    with pytest.raises(ValueError):
        normalize_probs([0.5, 0.5, 0.5], ["A", "B"])


def test_normalize_probs_rejects_missing_dict_key() -> None:
    with pytest.raises(ValueError):
        normalize_probs({"A": 1.0}, ["A", "B"])
