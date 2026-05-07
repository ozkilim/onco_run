"""End-to-end runner.

The framework's only job:
    1. Load the user's predictor (one time, up front).
    2. Walk the slides folder.
    3. Call `predictor.predict(slide_path)` for each slide.
    4. Append a row to a single CSV with the returned probabilities.

Per-slide failures are caught and recorded so a long batch never dies
on a single bad file.
"""

from __future__ import annotations

import csv
import json
import logging
import time
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator

import numpy as np

from .predictor import SlidePredictor, load_predictor, normalize_probs
from .recipe import Recipe
from .utils import list_slides, slide_id_from_path


log = logging.getLogger(__name__)


@dataclass
class SlidePrediction:
    slide_id: str
    slide_path: str
    status: str  # "ok" | "error"
    probs: list[float]
    predicted_class: str
    error: str = ""
    elapsed_s: float = 0.0


def _open_csv_writer(csv_path: Path, classes: list[str]):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fh = csv_path.open("w", newline="")
    fieldnames = [
        "slide_id",
        "slide_path",
        "status",
        "predicted_class",
        *[f"prob_{c}" for c in classes],
        "elapsed_s",
        "error",
    ]
    writer = csv.DictWriter(fh, fieldnames=fieldnames)
    writer.writeheader()
    fh.flush()
    return fh, writer


def _row_for(pred: SlidePrediction, classes: list[str]) -> dict:
    row = {
        "slide_id": pred.slide_id,
        "slide_path": pred.slide_path,
        "status": pred.status,
        "predicted_class": pred.predicted_class,
        "elapsed_s": f"{pred.elapsed_s:.2f}",
        "error": pred.error,
    }
    if pred.probs and len(pred.probs) == len(classes):
        for c, p in zip(classes, pred.probs):
            row[f"prob_{c}"] = f"{p:.6f}"
    else:
        for c in classes:
            row[f"prob_{c}"] = ""
    return row


def run_pipeline(
    recipe: Recipe,
    slides_dir: Path,
    output_dir: Path,
    progress: bool = True,
) -> list[SlidePrediction]:
    """Run the full pipeline. Returns one prediction per slide (incl. failures)."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Loading predictor for recipe '%s'", recipe.name)
    predictor: SlidePredictor = load_predictor(recipe.predictor, recipe.base_dir)

    pred_classes = list(predictor.classes)
    if pred_classes != recipe.classes:
        log.warning(
            "recipe.classes %s differs from predictor.classes %s; using predictor's order.",
            recipe.classes, pred_classes,
        )
    classes = pred_classes

    slides = list_slides(slides_dir, recipe.slide_extensions)
    if not slides:
        log.warning("No slides found in %s with extensions %s",
                    slides_dir, recipe.slide_extensions)
        # Still write an empty CSV with headers so downstream tooling
        # always has a file to read.
        fh, _ = _open_csv_writer(output_dir / recipe.output.csv_name, classes)
        fh.close()
        (output_dir / "run_summary.json").write_text(
            json.dumps({"recipe": recipe.name, "n_slides": 0}, indent=2)
        )
        return []
    log.info("Found %d slide(s) in %s", len(slides), slides_dir)

    predictions_csv = output_dir / recipe.output.csv_name
    fh, writer = _open_csv_writer(predictions_csv, classes)

    iterator: Iterator[Path] = iter(slides)
    if progress:
        try:
            from tqdm import tqdm
            iterator = tqdm(slides, desc="slides", unit="slide")
        except ImportError:
            iterator = iter(slides)

    results: list[SlidePrediction] = []
    try:
        for slide_path in iterator:
            pred = _process_one_slide(slide_path, predictor, classes)
            results.append(pred)
            writer.writerow(_row_for(pred, classes))
            fh.flush()
    finally:
        fh.close()

    summary = {
        "recipe": recipe.name,
        "classes": classes,
        "n_slides": len(results),
        "n_ok": sum(1 for r in results if r.status == "ok"),
        "n_error": sum(1 for r in results if r.status == "error"),
        "predictions_csv": str(predictions_csv),
    }
    (output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))
    log.info("Done. %s", summary)
    return results


def _process_one_slide(
    slide_path: Path,
    predictor: SlidePredictor,
    classes: list[str],
) -> SlidePrediction:
    sid = slide_id_from_path(slide_path)
    t0 = time.time()
    try:
        raw = predictor.predict(slide_path)
        probs = normalize_probs(raw, classes)
        pred_idx = int(np.argmax(probs))
        return SlidePrediction(
            slide_id=sid,
            slide_path=str(slide_path),
            status="ok",
            probs=probs.tolist(),
            predicted_class=classes[pred_idx],
            elapsed_s=time.time() - t0,
        )
    except Exception as exc:
        log.exception("Failed on slide %s", slide_path)
        return SlidePrediction(
            slide_id=sid,
            slide_path=str(slide_path),
            status="error",
            probs=[],
            predicted_class="",
            error=f"{type(exc).__name__}: {exc}",
            elapsed_s=time.time() - t0,
        )


def predictions_to_records(preds: list[SlidePrediction]) -> list[dict]:
    """Helper for tests / programmatic callers."""
    return [asdict(p) for p in preds]
