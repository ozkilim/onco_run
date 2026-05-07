#!/usr/bin/env bash
# Bake a specific recipe + weights into a single, turn-key image.
#
# Usage:
#   scripts/build_with_recipe.sh \
#       --recipe path/to/recipe.yaml \
#       --weights path/to/weights_dir \
#       [--tag onco-run:lung_v1] [--cpu]
#
# What this does:
#   1. Stages the recipe into ./recipes/recipe.yaml (the path the image's
#      default ONCO_RECIPE points at).
#   2. Stages weights into ./models/ so the recipe's relative paths resolve.
#   3. Builds the image, then restores any previous staged files.
#
# After this, end users can run the image with no -v mounts for recipe
# or weights — only their slides folder needs to be mounted.
set -euo pipefail

cd "$(dirname "$0")/.."

RECIPE=""
WEIGHTS_DIR=""
PREDICTORS_DIR=""
TAG="onco-run:bundled"
BASE="nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04"
TORCH_INDEX_URL=""

while [ $# -gt 0 ]; do
    case "$1" in
        --recipe)     RECIPE="$2"; shift 2 ;;
        --weights)    WEIGHTS_DIR="$2"; shift 2 ;;
        --predictors) PREDICTORS_DIR="$2"; shift 2 ;;
        --tag)        TAG="$2"; shift 2 ;;
        --base)       BASE="$2"; shift 2 ;;
        --cpu)
            BASE="python:3.11-slim"
            TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"
            shift
            ;;
        -h|--help)
            cat <<EOF
Usage: $0 --recipe PATH [--weights DIR] [--predictors DIR] [--tag TAG] [--cpu]

  --recipe      YAML recipe to bake into the image (becomes /app/recipes/recipe.yaml)
  --weights     Folder whose contents will be COPYed into /app/models
  --predictors  Folder whose contents will be COPYed into /app/predictors
                (defaults to ./predictors if present)
  --tag         Output image tag (default: onco-run:bundled)
  --cpu         Build CPU-only image
EOF
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

if [ -z "$RECIPE" ]; then
    echo "ERROR: --recipe is required" >&2
    exit 2
fi
if [ ! -f "$RECIPE" ]; then
    echo "ERROR: recipe not found: $RECIPE" >&2
    exit 2
fi

mkdir -p recipes models predictors
STAGE_DIR="$(mktemp -d)"
trap 'rm -rf "$STAGE_DIR"' EXIT

if [ -f recipes/recipe.yaml ]; then
    cp recipes/recipe.yaml "$STAGE_DIR/recipe.yaml.bak"
fi
cp "$RECIPE" recipes/recipe.yaml

if [ -n "$WEIGHTS_DIR" ]; then
    if [ ! -d "$WEIGHTS_DIR" ]; then
        echo "ERROR: weights dir not found: $WEIGHTS_DIR" >&2
        exit 2
    fi
    rsync -a --delete "$WEIGHTS_DIR"/ models/
fi

if [ -n "$PREDICTORS_DIR" ]; then
    if [ ! -d "$PREDICTORS_DIR" ]; then
        echo "ERROR: predictors dir not found: $PREDICTORS_DIR" >&2
        exit 2
    fi
    rsync -a --delete "$PREDICTORS_DIR"/ predictors/
fi

echo ">> Building $TAG with recipe=$RECIPE weights=$WEIGHTS_DIR predictors=${PREDICTORS_DIR:-./predictors} base=$BASE"
docker build \
    --build-arg "BASE=$BASE" \
    --build-arg "TORCH_INDEX_URL=$TORCH_INDEX_URL" \
    --tag "$TAG" .

if [ -f "$STAGE_DIR/recipe.yaml.bak" ]; then
    cp "$STAGE_DIR/recipe.yaml.bak" recipes/recipe.yaml
fi

echo ">> Built $TAG"
