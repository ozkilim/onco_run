"""Recipe loader tests (no torch dependency)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from onco_run.recipe import load_recipe


def _write(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data))
    return path


def test_load_minimal_recipe(tmp_path: Path) -> None:
    p = _write(tmp_path / "r.yaml", {
        "name": "unit",
        "classes": ["A", "B"],
        "predictor": {
            "module": "predictors.example_predictor",
            "config": {"thumbnail_max_dim": 256},
        },
    })
    rec = load_recipe(p)
    assert rec.name == "unit"
    assert rec.classes == ["A", "B"]
    assert rec.predictor.module == "predictors.example_predictor"
    assert rec.predictor.factory == "build_predictor"
    assert rec.predictor.config["thumbnail_max_dim"] == 256
    assert rec.base_dir == p.parent


def test_predictor_path_alternative(tmp_path: Path) -> None:
    p = _write(tmp_path / "r.yaml", {
        "classes": ["X"],
        "predictor": {"path": "../predictors/foo.py", "factory": "make"},
    })
    rec = load_recipe(p)
    assert rec.predictor.path == "../predictors/foo.py"
    assert rec.predictor.factory == "make"


def test_missing_classes(tmp_path: Path) -> None:
    p = _write(tmp_path / "bad.yaml", {"predictor": {"module": "x"}})
    with pytest.raises(ValueError):
        load_recipe(p)


def test_missing_predictor_module_and_path(tmp_path: Path) -> None:
    p = _write(tmp_path / "bad.yaml", {"classes": ["A"], "predictor": {}})
    with pytest.raises(ValueError):
        load_recipe(p)


def test_default_extensions(tmp_path: Path) -> None:
    p = _write(tmp_path / "r.yaml", {
        "classes": ["A"],
        "predictor": {"module": "predictors.x"},
    })
    rec = load_recipe(p)
    assert "svs" in rec.slide_extensions
    assert "tiff" in rec.slide_extensions
