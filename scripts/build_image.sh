#!/usr/bin/env bash
# Build Docker images via docker compose / docker-compose.
# Usage: ./scripts/build_image.sh [--no-cache] [--tag <tag>] [--service <service>]
#
# Options:
#   --no-cache     Pass --no-cache to docker compose build
#   --tag <tag>    Re-tag images after build (e.g. v1.2.3)
#   --service <s>  Build only the specified service (e.g. markitdown-api)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/../deploy" && pwd)"

NO_CACHE=""
IMAGE_TAG=""
SERVICE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-cache) NO_CACHE="--no-cache"; shift ;;
    --tag)      IMAGE_TAG="$2"; shift 2 ;;
    --service)  SERVICE="$2"; shift 2 ;;
    *)
      echo "Usage: $0 [--no-cache] [--tag <tag>] [--service <service>]"
      exit 1
      ;;
  esac
done

if ! command -v docker &>/dev/null; then
  echo "[error] docker not found."
  exit 1
fi

# Support both 'docker compose' (plugin, v20.10+) and 'docker-compose' (standalone)
if docker compose version &>/dev/null 2>&1; then
  COMPOSE="docker compose"
elif command -v docker-compose &>/dev/null; then
  COMPOSE="docker-compose"
else
  echo "[error] Neither 'docker compose' nor 'docker-compose' found."
  exit 1
fi

echo "[build-image] Using: $COMPOSE"
echo "[build-image] Building from $DEPLOY_DIR ..."
cd "$DEPLOY_DIR"

# shellcheck disable=SC2086
$COMPOSE build $NO_CACHE ${SERVICE:-}

if [[ -n "$IMAGE_TAG" ]]; then
  echo "[build-image] Tagging images with :$IMAGE_TAG ..."
  for img in markitdown-ollama markitdown-api; do
    if docker image inspect "${img}:latest" &>/dev/null; then
      docker tag "${img}:latest" "${img}:${IMAGE_TAG}"
      echo "  Tagged ${img}:latest -> ${img}:${IMAGE_TAG}"
    fi
  done
fi

echo "[build-image] Done."
$COMPOSE images
