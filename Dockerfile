# syntax=docker/dockerfile:1.6
#
# onco_run: a generic runtime for any WSI predictor. Two build modes:
#
#   GPU (default): build --build-arg BASE=nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04
#   CPU:           build --build-arg BASE=python:3.11-slim
#
# What's inside:
#   * openslide system libs (so openslide-python works out of the box)
#   * a sensible Python runtime (torch, numpy, pillow, scikit-image, ...)
#   * the onco_run runner (orchestration + helpers)
#   * /app/predictors on PYTHONPATH, so any module dropped in
#     `predictors/` is importable from a recipe.
#
# Anything model-specific lives in `predictors/` and `models/` and is
# COPYed in below; the framework code stays the same across deployments.

ARG BASE=nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04
FROM ${BASE} AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    LC_ALL=C.UTF-8 \
    LANG=C.UTF-8

# Image libraries (libjpeg, libtiff, libopenjp2, ...) are intentionally
# not listed explicitly: their package names changed between Debian
# trixie and Ubuntu 22.04, and `openslide-tools` already pulls in the
# correct versions transitively. Keep this list to things that are
# stable across both bases.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        openslide-tools \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN if ! command -v python >/dev/null 2>&1; then ln -s /usr/bin/python3 /usr/local/bin/python; fi \
 && python -m pip install --upgrade pip wheel

WORKDIR /app

# Install the runner first so source edits don't bust the layer cache.
# `TORCH_INDEX_URL` lets CPU builds pull torch from the CPU-only wheel
# index (~1.5 GB smaller than the default CUDA wheel). The build script
# sets this automatically for `--cpu`.
ARG TORCH_INDEX_URL=""
COPY pyproject.toml /app/pyproject.toml
COPY src /app/src
RUN if [ -n "$TORCH_INDEX_URL" ]; then \
        pip install --index-url "$TORCH_INDEX_URL" torch torchvision ; \
    fi && \
    pip install "/app[runtime]"

# Default mount points and import paths.
ENV ONCO_SLIDES_DIR=/data/slides \
    ONCO_OUTPUT_DIR=/data/output \
    ONCO_RECIPE=/app/recipes/recipe.yaml \
    PYTHONPATH=/app:${PYTHONPATH}

RUN mkdir -p /app/recipes /app/models /app/predictors /data/slides /data/output

# Copy any predictor code, recipes, and weights from the build context.
# These COPYs are no-ops when the dirs are empty in the build context;
# they let `scripts/build_with_recipe.sh` produce a turn-key image.
COPY predictors/ /app/predictors/
COPY recipes/    /app/recipes/
COPY models/     /app/models/

# If the predictors folder ships a requirements.txt, install it now.
# This lets each model declare its own pinned extras without forcing
# every other deployment to carry them.
RUN if [ -f /app/predictors/requirements.txt ]; then \
        pip install -r /app/predictors/requirements.txt ; \
    fi

COPY docker/entrypoint.sh /usr/local/bin/onco-entrypoint
RUN chmod +x /usr/local/bin/onco-entrypoint

ENTRYPOINT ["/usr/local/bin/onco-entrypoint"]
CMD ["predict"]
