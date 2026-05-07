#!/usr/bin/env bash
# Onboard a collaborator on a server that already has the onco_run image
# loaded in docker. The collaborator only needs an SSH account; this
# script provisions the kit folder and grants docker access.
#
# Usage (run as root or with sudo):
#   ./scripts/onboard_collaborator.sh USERNAME [--image TAG] [--create-user] [--load TARBALL]
#
# What this does:
#   1. (optional) Creates the Linux user.
#   2. (optional) docker-loads the image from a tar.gz if not already present.
#   3. Adds the user to the `docker` group (so they don't need sudo).
#   4. Creates ~USERNAME/onco_run/{slides,output} with a one-line run.sh
#      and a tiny README. Both are owned by USERNAME.
#   5. Prints the email/handoff blurb the admin can paste to the user.

set -euo pipefail

if [ "${EUID:-$(id -u)}" -ne 0 ]; then
    echo "ERROR: must run as root (try: sudo $0 ...)" >&2
    exit 1
fi

USER_NAME=""
IMAGE_TAG="onco-run:dummy_v1"
CREATE_USER=0
LOAD_TARBALL=""

while [ $# -gt 0 ]; do
    case "$1" in
        --image)        IMAGE_TAG="$2"; shift 2 ;;
        --create-user)  CREATE_USER=1; shift ;;
        --load)         LOAD_TARBALL="$2"; shift 2 ;;
        -h|--help)
            sed -n '2,18p' "$0"
            exit 0
            ;;
        -*)             echo "Unknown flag: $1" >&2; exit 2 ;;
        *)
            if [ -z "$USER_NAME" ]; then USER_NAME="$1"; shift
            else echo "Unexpected positional: $1" >&2; exit 2; fi
            ;;
    esac
done

if [ -z "$USER_NAME" ]; then
    echo "usage: $0 USERNAME [--image TAG] [--create-user] [--load TARBALL]" >&2
    exit 2
fi

# 1. Ensure docker is installed and running.
if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is not installed on this server." >&2
    exit 1
fi
if ! docker info >/dev/null 2>&1; then
    echo "ERROR: docker daemon is not running. Try: sudo systemctl start docker" >&2
    exit 1
fi

# 2. Ensure the image is available.
if ! docker image inspect "$IMAGE_TAG" >/dev/null 2>&1; then
    if [ -n "$LOAD_TARBALL" ]; then
        echo ">> Loading $IMAGE_TAG from $LOAD_TARBALL ..."
        if [[ "$LOAD_TARBALL" == *.gz ]]; then
            gunzip -c "$LOAD_TARBALL" | docker load
        else
            docker load -i "$LOAD_TARBALL"
        fi
    else
        echo "ERROR: image '$IMAGE_TAG' not loaded. Either:" >&2
        echo "         docker load -i path/to/onco_run_image.tar.gz" >&2
        echo "       or pass --load path/to/onco_run_image.tar.gz" >&2
        exit 1
    fi
fi

# 3. Ensure the user exists.
if ! id "$USER_NAME" >/dev/null 2>&1; then
    if [ "$CREATE_USER" -eq 1 ]; then
        echo ">> Creating user $USER_NAME"
        useradd -m -s /bin/bash "$USER_NAME"
    else
        echo "ERROR: user '$USER_NAME' does not exist. Re-run with --create-user, or:" >&2
        echo "         sudo useradd -m -s /bin/bash $USER_NAME" >&2
        echo "         sudo passwd $USER_NAME            # or set up SSH key" >&2
        exit 1
    fi
fi

# 4. Grant docker access.
if ! getent group docker >/dev/null; then
    groupadd docker
fi
usermod -aG docker "$USER_NAME"
echo ">> Added $USER_NAME to docker group"

# 5. Provision the kit folder.
HOME_DIR=$(getent passwd "$USER_NAME" | cut -d: -f6)
KIT_DIR="$HOME_DIR/onco_run"
mkdir -p "$KIT_DIR/slides" "$KIT_DIR/output"

cat > "$KIT_DIR/run.sh" <<RUNEOF
#!/usr/bin/env bash
# onco_run wrapper: drops slides through the docker image and writes
# predictions.csv next to it. Edit nothing — just put WSIs in ./slides/.
set -euo pipefail
HERE="\$(cd "\$(dirname "\$0")" && pwd)"

IMAGE_TAG="${IMAGE_TAG}"

if [ ! -d "\$HERE/slides" ] || [ -z "\$(ls -A "\$HERE/slides" 2>/dev/null)" ]; then
    echo "ERROR: put your WSI files into \$HERE/slides/ first." >&2
    exit 1
fi
mkdir -p "\$HERE/output"

GPU_ARGS=()
if docker info 2>/dev/null | grep -qi 'nvidia'; then
    GPU_ARGS+=(--gpus all)
    echo ">> Using GPU."
else
    echo ">> Running on CPU."
fi

NSLIDES=\$(find "\$HERE/slides" -type f | wc -l)
echo ">> Running predictions on \$NSLIDES slide(s)..."

# Run as the calling user so output files are owned by you, not root.
docker run --rm \\
    -u "\$(id -u):\$(id -g)" \\
    -e HOME=/tmp \\
    "\${GPU_ARGS[@]}" \\
    -v "\$HERE/slides:/data/slides:ro" \\
    -v "\$HERE/output:/data/output" \\
    "\$IMAGE_TAG"

echo ""
echo "Done. Predictions: \$HERE/output/predictions.csv"
echo "Send that file back to your collaborator."
RUNEOF

cat > "$KIT_DIR/README.md" <<READMEEOF
# onco_run quick start

You're set up. Three steps:

1. Put your WSI files into \`./slides/\` in this folder.
   Subfolders are fine. Supported: .svs, .tif, .tiff, .ndpi, .mrxs, .scn, etc.

2. Run:

       ./run.sh

3. When it finishes, send back:
   - \`./output/predictions.csv\`
   - \`./output/run_summary.json\`

That's it. No installs, no Python, no GPU configuration.

If \`./run.sh\` says "permission denied" on docker, log out and back in
(group membership only takes effect on a new shell), or run once with:

       newgrp docker
       ./run.sh
READMEEOF

chmod +x "$KIT_DIR/run.sh"
chown -R "$USER_NAME:$USER_NAME" "$KIT_DIR"

# 6. Print the handoff blurb.
HOST=$(hostname -f 2>/dev/null || hostname)
cat <<HANDOFF

============================================================
 Onboarded: $USER_NAME
 Image:     $IMAGE_TAG
 Kit dir:   $KIT_DIR
============================================================

Email/Slack to $USER_NAME:
------------------------------------------------------------
You've got an account on $HOST. Steps:

  ssh $USER_NAME@$HOST

  # First time only: pick up docker group membership
  newgrp docker

  # Then any time you have new slides:
  cd ~/onco_run
  cp /path/to/your/slides/*.svs slides/
  ./run.sh

  # Email me back ~/onco_run/output/predictions.csv
------------------------------------------------------------
HANDOFF
