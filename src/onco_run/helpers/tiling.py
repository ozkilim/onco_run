"""Optional tissue mask + tile coordinate utility.

Pure helpers — the runner does not call any of this. Import only if it
saves you the boilerplate of doing tissue detection yourself.

Conventions:
    * `coords_l0` are level-0 pixel coordinates (top-left corner).
    * `read_size` is the size to pass to `read_region` at `read_level`.
    * `out_size` is the size you should resample tiles to before model.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from PIL import Image
from skimage import color, filters, morphology

from .slide_io import Slide, SlideInfo


log = logging.getLogger(__name__)


@dataclass
class TileGrid:
    coords_l0: np.ndarray  # (N, 2) int
    read_level: int
    read_size: int
    out_size: int
    effective_mpp: float


def build_tissue_mask(thumb_rgb: np.ndarray, bg_intensity: int = 220) -> np.ndarray:
    """Otsu-on-saturation + brightness gate. Catches faint stains and
    very white/transparent backgrounds. Returns boolean mask same H×W.
    """
    if thumb_rgb.ndim != 3 or thumb_rgb.shape[2] != 3:
        raise ValueError("thumb_rgb must be HxWx3")
    hsv = color.rgb2hsv(thumb_rgb)
    saturation = hsv[..., 1]
    try:
        thresh = filters.threshold_otsu(saturation)
    except ValueError:
        return np.zeros(thumb_rgb.shape[:2], dtype=bool)
    sat_mask = saturation > max(thresh, 0.04)
    intensity = thumb_rgb.mean(axis=-1)
    bright_mask = intensity < bg_intensity
    mask = sat_mask & bright_mask
    mask = morphology.remove_small_holes(mask, area_threshold=64)
    mask = morphology.remove_small_objects(mask, min_size=64)
    return mask


def _pick_level_for_mpp(info: SlideInfo, target_mpp: float) -> tuple[int, float]:
    base_mpp = info.mpp if info.mpp is not None else target_mpp
    if info.mpp is None:
        log.warning(
            "%s: no mpp metadata; assuming %.3f um/px at level 0.",
            info.path.name, base_mpp,
        )
    best_level = 0
    best_diff = float("inf")
    for lvl, ds in enumerate(info.level_downsamples):
        lvl_mpp = base_mpp * float(ds)
        if lvl_mpp <= target_mpp + 1e-6:
            diff = target_mpp - lvl_mpp
            if diff < best_diff:
                best_diff = diff
                best_level = lvl
    return best_level, base_mpp * float(info.level_downsamples[best_level])


def plan_tiles(
    slide: Slide,
    tile_size: int = 256,
    mpp: float = 0.5,
    tissue_threshold: float = 0.05,
    overlap: int = 0,
    max_tiles: int | None = None,
    background_intensity_threshold: int = 220,
) -> TileGrid:
    """Compute the tile coordinate grid for a slide. Slide must be opened.

    Returns an empty TileGrid (N=0) when no tissue is detected.
    """
    info = slide.info()
    read_level, level_mpp = _pick_level_for_mpp(info, mpp)
    scale_to_target = level_mpp / mpp  # <= 1.0
    read_size = max(1, int(round(tile_size / scale_to_target)))

    thumb = slide.thumbnail(max_dim=2048)
    mask = build_tissue_mask(thumb, bg_intensity=background_intensity_threshold)
    if not mask.any():
        return TileGrid(
            coords_l0=np.empty((0, 2), dtype=np.int64),
            read_level=read_level,
            read_size=read_size,
            out_size=tile_size,
            effective_mpp=level_mpp,
        )

    base_mpp = info.mpp if info.mpp is not None else mpp
    tile_size_l0 = int(round(tile_size * (mpp / base_mpp)))
    stride_l0 = max(1, tile_size_l0 - int(round(overlap * (mpp / base_mpp))))

    W, H = info.width, info.height
    mh, mw = mask.shape
    sx = mw / W
    sy = mh / H

    coords: list[tuple[int, int]] = []
    for y0 in range(0, H - tile_size_l0 + 1, stride_l0):
        for x0 in range(0, W - tile_size_l0 + 1, stride_l0):
            mx0 = int(x0 * sx)
            my0 = int(y0 * sy)
            mx1 = max(mx0 + 1, int((x0 + tile_size_l0) * sx))
            my1 = max(my0 + 1, int((y0 + tile_size_l0) * sy))
            patch = mask[my0:my1, mx0:mx1]
            if patch.size == 0:
                continue
            if patch.mean() >= tissue_threshold:
                coords.append((x0, y0))

    if max_tiles is not None and len(coords) > max_tiles:
        rng = np.random.default_rng(0)
        idx = rng.choice(len(coords), size=max_tiles, replace=False)
        coords = [coords[i] for i in sorted(idx.tolist())]

    arr = np.asarray(coords, dtype=np.int64).reshape(-1, 2)
    return TileGrid(
        coords_l0=arr,
        read_level=read_level,
        read_size=read_size,
        out_size=tile_size,
        effective_mpp=level_mpp,
    )


def read_tile(slide: Slide, grid: TileGrid, idx: int) -> np.ndarray:
    """Read tile `idx` at the planned level/size and resize to out_size."""
    x, y = grid.coords_l0[idx].tolist()
    arr = slide.read_region_rgb(x, y, grid.read_level, (grid.read_size, grid.read_size))
    if grid.read_size != grid.out_size:
        img = Image.fromarray(arr)
        img = img.resize((grid.out_size, grid.out_size), Image.BILINEAR)
        arr = np.asarray(img, dtype=np.uint8)
    return arr
