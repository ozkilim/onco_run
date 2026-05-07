#!/usr/bin/env bash
# Entrypoint: prints a small banner, validates mounts, then exec's the CLI.
set -euo pipefail

BANNER="onco_run inference pipeline"
echo "================================================"
echo "  $BANNER"
echo "================================================"
echo "  recipe : ${ONCO_RECIPE:-(unset)}"
echo "  slides : ${ONCO_SLIDES_DIR:-(unset)}"
echo "  output : ${ONCO_OUTPUT_DIR:-(unset)}"

if command -v nvidia-smi >/dev/null 2>&1; then
    if nvidia-smi -L >/dev/null 2>&1; then
        echo "  device : GPU detected"
    else
        echo "  device : CPU (nvidia-smi present but no GPU visible)"
    fi
else
    echo "  device : CPU"
fi
echo "================================================"

# If the user passes a subcommand or extra args, hand them to the CLI verbatim.
# Otherwise default to `predict`, which picks up paths from the env vars.
if [ "$#" -eq 0 ]; then
    exec onco-run predict
fi

case "$1" in
    predict|info)
        exec onco-run "$@"
        ;;
    bash|sh)
        exec "$@"
        ;;
    *)
        # Pass-through: e.g. `python -c '...'` for debugging.
        exec "$@"
        ;;
esac
