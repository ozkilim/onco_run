"""Optional OpenSlide wrapper. Use it or don't.

OpenSlide objects are not picklable; keep them inside the worker process
that opens them. This wrapper is a context manager so handles are
released deterministically.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import openslide


log = logging.getLogger(__name__)


@dataclass
class SlideInfo:
    path: Path
    width: int
    height: int
    mpp_x: float | None
    mpp_y: float | None
    level_count: int
    level_dims: list[tuple[int, int]]
    level_downsamples: list[float]

    @property
    def mpp(self) -> float | None:
        if self.mpp_x is None or self.mpp_y is None:
            return None
        return float((self.mpp_x + self.mpp_y) / 2.0)


class Slide:
    """Lazy OpenSlide wrapper."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._osr: openslide.OpenSlide | None = None

    def __enter__(self) -> "Slide":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def open(self) -> None:
        if self._osr is None:
            self._osr = openslide.OpenSlide(str(self.path))

    def close(self) -> None:
        if self._osr is not None:
            self._osr.close()
            self._osr = None

    @property
    def osr(self) -> openslide.OpenSlide:
        if self._osr is None:
            self.open()
        assert self._osr is not None
        return self._osr

    def info(self) -> SlideInfo:
        osr = self.osr
        props = osr.properties
        mpp_x = _safe_float(props.get(openslide.PROPERTY_NAME_MPP_X))
        mpp_y = _safe_float(props.get(openslide.PROPERTY_NAME_MPP_Y))
        if mpp_x is None:
            mpp_x = _safe_float(props.get("aperio.MPP"))
        if mpp_y is None:
            mpp_y = mpp_x
        return SlideInfo(
            path=self.path,
            width=osr.dimensions[0],
            height=osr.dimensions[1],
            mpp_x=mpp_x,
            mpp_y=mpp_y,
            level_count=osr.level_count,
            level_dims=list(osr.level_dimensions),
            level_downsamples=list(osr.level_downsamples),
        )

    def read_region_rgb(
        self,
        x: int,
        y: int,
        level: int,
        size: tuple[int, int],
    ) -> np.ndarray:
        """Read an RGB region. Coords are at level 0; size is in `level` pixels."""
        img = self.osr.read_region((x, y), level, size).convert("RGB")
        return np.asarray(img, dtype=np.uint8)

    def thumbnail(self, max_dim: int = 2048) -> np.ndarray:
        osr = self.osr
        w, h = osr.dimensions
        scale = max_dim / max(w, h)
        if scale >= 1.0:
            target = (w, h)
        else:
            target = (max(1, int(w * scale)), max(1, int(h * scale)))
        thumb = osr.get_thumbnail(target).convert("RGB")
        return np.asarray(thumb, dtype=np.uint8)

    def best_level_for_downsample(self, downsample: float) -> int:
        return int(self.osr.get_best_level_for_downsample(downsample))


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f <= 0:
        return None
    return f
