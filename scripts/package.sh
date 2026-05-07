#!/usr/bin/env bash
# Produce a self-contained zip you can email/send to a recipient. Contains:
#   - onco_run_image.tar.gz   (docker save | gzip)
#   - run.sh                  (one-shot loader + runner for the recipient)
#   - README.md               (recipient-facing instructions)
#
# Usage:
#   scripts/package.sh [--tag onco-run:bundled] [--out dist/lung_v1]
set -euo pipefail

cd "$(dirname "$0")/.."

TAG="onco-run:bundled"
OUT="dist/onco_run_$(date +%Y%m%d_%H%M%S)"

while [ $# -gt 0 ]; do
    case "$1" in
        --tag) TAG="$2"; shift 2 ;;
        --out) OUT="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--tag IMAGE_TAG] [--out OUT_DIR]"
            exit 0
            ;;
        *) echo "Unknown arg: $1" >&2; exit 2 ;;
    esac
done

if ! docker image inspect "$TAG" >/dev/null 2>&1; then
    echo "ERROR: image '$TAG' not found locally. Build it first with scripts/build_with_recipe.sh" >&2
    exit 1
fi

mkdir -p "$OUT"

echo ">> Saving $TAG to $OUT/onco_run_image.tar.gz (this may take a few minutes)"
docker save "$TAG" | gzip > "$OUT/onco_run_image.tar.gz"

cp deliverables/run.sh "$OUT/run.sh"
chmod +x "$OUT/run.sh"
cp deliverables/README_FOR_RECIPIENT.md "$OUT/README.md"

# Stamp the tag into run.sh so the recipient doesn't have to type it.
sed -i.bak "s|__IMAGE_TAG__|$TAG|g" "$OUT/run.sh" && rm -f "$OUT/run.sh.bak"

SIZE=$(du -sh "$OUT/onco_run_image.tar.gz" | cut -f1)
echo ">> Package ready in $OUT (image: $SIZE)"
echo "   Send the entire folder. The recipient runs: ./run.sh /path/to/slides /path/to/output"
