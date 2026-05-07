"""onco-run CLI: a single command.

    onco-run predict --recipe RECIPE --slides DIR --output DIR

Defaults are tuned for the Docker image: when env vars `ONCO_RECIPE`,
`ONCO_SLIDES_DIR`, and `ONCO_OUTPUT_DIR` are set (which the entrypoint
script does), end users can run `onco-run predict` with no arguments.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer
from rich.console import Console

from .pipeline import run_pipeline
from .recipe import load_recipe
from .utils import setup_logging


app = typer.Typer(
    add_completion=False,
    no_args_is_help=True,
    help="Model-agnostic WSI inference runner.",
)
console = Console()


@app.callback()
def _main() -> None:
    """Model-agnostic WSI inference runner.

    The callback exists only to force Typer into multi-command mode so
    that ``onco-run predict ...`` resolves correctly even when there is
    only one command.
    """


def _env_path(name: str) -> Path | None:
    val = os.environ.get(name)
    return Path(val) if val else None


@app.command()
def predict(
    recipe: Path = typer.Option(
        None, "--recipe", "-r",
        help="Path to recipe YAML. Defaults to $ONCO_RECIPE.",
        exists=False, file_okay=True, dir_okay=False,
    ),
    slides: Path = typer.Option(
        None, "--slides", "-s",
        help="Folder of WSI files. Defaults to $ONCO_SLIDES_DIR.",
        exists=False, file_okay=False, dir_okay=True,
    ),
    output: Path = typer.Option(
        None, "--output", "-o",
        help="Output folder. Defaults to $ONCO_OUTPUT_DIR.",
        exists=False, file_okay=False, dir_okay=True,
    ),
    log_level: str = typer.Option(
        "INFO", "--log-level", help="DEBUG / INFO / WARNING / ERROR."
    ),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable tqdm."),
) -> None:
    """Run the user's predictor for every slide in --slides and write predictions.csv."""
    recipe = recipe or _env_path("ONCO_RECIPE")
    slides = slides or _env_path("ONCO_SLIDES_DIR")
    output = output or _env_path("ONCO_OUTPUT_DIR")

    missing = [n for n, v in [("--recipe", recipe), ("--slides", slides), ("--output", output)] if v is None]
    if missing:
        console.print(
            f"[red]Missing required argument(s): {', '.join(missing)}[/red]\n"
            "Pass them on the command line or set the corresponding "
            "ONCO_RECIPE / ONCO_SLIDES_DIR / ONCO_OUTPUT_DIR env vars."
        )
        raise typer.Exit(code=2)

    output.mkdir(parents=True, exist_ok=True)
    setup_logging(level=log_level, log_file=output / "run.log")

    rec = load_recipe(recipe)
    console.print(f"[bold]Recipe:[/bold] {rec.name}  (classes: {', '.join(rec.classes)})")
    console.print(f"[bold]Slides:[/bold] {slides}")
    console.print(f"[bold]Output:[/bold] {output}")

    preds = run_pipeline(
        recipe=rec,
        slides_dir=slides,
        output_dir=output,
        progress=not no_progress,
    )

    n_ok = sum(1 for p in preds if p.status == "ok")
    n_err = sum(1 for p in preds if p.status == "error")
    console.print(
        f"\n[bold green]Done.[/bold green] "
        f"{n_ok} ok, {n_err} errors. "
        f"Predictions: {output / rec.output.csv_name}"
    )
    if n_err and not n_ok:
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    app()
