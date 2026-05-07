"""Small, dependency-light utilities."""

from __future__ import annotations

import logging
import sys
from pathlib import Path


_LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Configure root logger once with a sensible format. Idempotent."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, mode="w"))

    formatter = logging.Formatter(_LOG_FORMAT)
    for h in handlers:
        h.setFormatter(formatter)
        root.addHandler(h)
    root.setLevel(level.upper())


def list_slides(folder: Path, extensions: tuple[str, ...]) -> list[Path]:
    """Recursively list slide files matching `extensions` (case-insensitive)."""
    folder = Path(folder)
    if not folder.exists():
        raise FileNotFoundError(f"Slides folder does not exist: {folder}")
    exts = {e.lower().lstrip(".") for e in extensions}
    out: list[Path] = []
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower().lstrip(".") in exts:
            out.append(p)
    return sorted(out)


def slide_id_from_path(path: Path) -> str:
    """Stable slide id from filename (no extension)."""
    return Path(path).stem
