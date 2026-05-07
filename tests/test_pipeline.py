"""End-to-end pipeline test using a fake slide format and predictor.

We skip OpenSlide entirely by registering a fake extension and using a
predictor that ignores the slide contents — this exercises the whole
runner (recipe loading, dynamic import, CSV writing, error handling).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from onco_run.pipeline import run_pipeline
from onco_run.recipe import load_recipe


PREDICTOR_FILE = """
import numpy as np
import pathlib

class P:
    classes = ["A", "B"]
    def predict(self, slide_path):
        # "Fail" on filenames containing 'bad' to test error handling.
        if 'bad' in pathlib.Path(slide_path).name:
            raise RuntimeError('synthetic failure')
        return np.array([0.3, 0.7])

def build_predictor(*, recipe_dir, **_):
    return P()
"""


def test_pipeline_writes_csv_and_handles_errors(tmp_path: Path) -> None:
    # Synthetic predictor.
    pf = tmp_path / "p.py"
    pf.write_text(PREDICTOR_FILE)

    # Recipe.
    recipe_path = tmp_path / "r.yaml"
    recipe_path.write_text(yaml.safe_dump({
        "name": "synthetic",
        "classes": ["A", "B"],
        "predictor": {"path": "p.py"},
        "slide_extensions": ["fake"],
    }))

    # Synthetic "slides" (the predictor ignores their contents).
    slides_dir = tmp_path / "slides"
    slides_dir.mkdir()
    (slides_dir / "good_1.fake").write_bytes(b"x")
    (slides_dir / "good_2.fake").write_bytes(b"x")
    (slides_dir / "bad_3.fake").write_bytes(b"x")

    output_dir = tmp_path / "out"
    rec = load_recipe(recipe_path)
    results = run_pipeline(rec, slides_dir, output_dir, progress=False)

    assert len(results) == 3
    statuses = sorted([r.status for r in results])
    assert statuses == ["error", "ok", "ok"]

    csv_path = output_dir / "predictions.csv"
    assert csv_path.exists()
    lines = csv_path.read_text().strip().splitlines()
    # Header + 3 data rows.
    assert len(lines) == 4
    header = lines[0]
    assert "prob_A" in header and "prob_B" in header
    assert (output_dir / "run_summary.json").exists()
    assert (output_dir / "run.log").exists() is False  # logging is set up by CLI, not run_pipeline
