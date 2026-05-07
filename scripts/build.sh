#!/usr/bin/env bash
# Build the onco_run image. Usage:
#   scripts/build.sh [--cpu] [--tag TAG]
#
# By default builds a CUDA image tagged onco-run:latest. With --cpu uses
# python:3.11-slim as the base — useful for laptops and CI.
set -euo pipefail

cd "$(dirname "$0")/.."

BASE="nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04"
TORCH_INDEX_URL=""
TAG="onco-run:latest"

while [ $# -gt 0 ]; do
    case "$1" in
        --cpu)
            BASE="python:3.11-slim"
            TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"
            shift
            ;;
        --tag)   TAG="$2"; shift 2 ;;
        --base)  BASE="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--cpu] [--tag TAG] [--base IMAGE]"
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

echo ">> Building $TAG  (base: $BASE)"
docker build \
    --build-arg "BASE=$BASE" \
    --build-arg "TORCH_INDEX_URL=$TORCH_INDEX_URL" \
    --tag "$TAG" \
    .
echo ">> Built $TAG"
