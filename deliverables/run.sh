#!/usr/bin/env bash
# Recipient-side entrypoint. This file is intentionally self-contained: it
# only depends on `docker` being installed and a folder of slides.
#
# Usage:
#   ./run.sh /path/to/slides_folder /path/to/output_folder
#
# Behaviour:
#   1. Loads the docker image from onco_run_image.tar.gz the first time.
#   2. Detects whether NVIDIA GPUs are usable from docker; uses --gpus all
#      if so, otherwise falls back to CPU.
#   3. Mounts the two folders read-only (slides) / read-write (output)
#      and runs the inference. Predictions land at OUTPUT/predictions.csv.
set -euo pipefail

IMAGE_TAG="__IMAGE_TAG__"

usage() {
    cat <<EOF
Usage: $0 SLIDES_DIR OUTPUT_DIR

  SLIDES_DIR   Folder containing the WSI files (.svs, .tif, .tiff, .ndpi, ...)
  OUTPUT_DIR   Folder to write predictions.csv (will be created if missing)

Optional env:
  IMAGE_TAR    Path to onco_run_image.tar.gz (default: alongside this script)
  IMAGE_TAG    Override image tag (default: $IMAGE_TAG)
EOF
}

if [ "$#" -ne 2 ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
    usage
    exit 0
fi

SLIDES_DIR="$1"
OUTPUT_DIR="$2"

if [ ! -d "$SLIDES_DIR" ]; then
    echo "ERROR: slides folder not found: $SLIDES_DIR" >&2
    exit 1
fi
mkdir -p "$OUTPUT_DIR"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_TAR="${IMAGE_TAR:-$SCRIPT_DIR/onco_run_image.tar.gz}"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is not installed. Install Docker Desktop (Mac/Windows) or docker-engine (Linux)." >&2
    exit 1
fi

if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
    if [ ! -f "$IMAGE_TAR" ]; then
        echo "ERROR: image '$IMAGE_TAG' not loaded and tarball missing: $IMAGE_TAR" >&2
        exit 1
    fi
    echo ">> Loading docker image (one-time, this can take a few minutes)..."
    if [[ "$IMAGE_TAR" == *.gz ]]; then
        gunzip -c "$IMAGE_TAR" | docker load
    else
        docker load -i "$IMAGE_TAR"
    fi
fi

GPU_ARGS=()
if docker info 2>/dev/null | grep -qi 'nvidia'; then
    GPU_ARGS+=(--gpus all)
    echo ">> Detected NVIDIA runtime; using GPUs."
else
    if command -v nvidia-smi >/dev/null 2>&1; then
        echo ">> NVIDIA GPU detected on host but docker doesn't expose it; running on CPU."
        echo "   (Install nvidia-container-toolkit to enable GPU.)"
    else
        echo ">> No GPU detected; running on CPU."
    fi
fi

ABS_SLIDES="$(cd "$SLIDES_DIR" && pwd)"
ABS_OUTPUT="$(cd "$OUTPUT_DIR" && pwd)"

echo ">> Running onco_run..."
# Run as the calling user so output files are owned by you, not root.
docker run --rm \
    -u "$(id -u):$(id -g)" \
    -e HOME=/tmp \
    "${GPU_ARGS[@]}" \
    -v "$ABS_SLIDES:/data/slides:ro" \
    -v "$ABS_OUTPUT:/data/output" \
    "$IMAGE_TAG"

echo ""
echo "Done. Predictions: $ABS_OUTPUT/predictions.csv"
echo "Send that CSV (and run_summary.json) back."
