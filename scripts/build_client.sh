#!/usr/bin/env bash
# Build the Electron desktop client.
# Usage: ./scripts/build_client.sh [linux|win|mac]  (default: current platform)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ELECTRON_DIR="$PROJECT_ROOT/electron"

PLATFORM="${1:-}"

# Resolve build target flag
case "$PLATFORM" in
  linux) BUILD_FLAG="--linux" ;;
  win)   BUILD_FLAG="--win"   ;;
  mac)   BUILD_FLAG="--mac"   ;;
  "")    BUILD_FLAG=""        ;;
  *)
    echo "Usage: $0 [linux|win|mac]"
    exit 1
    ;;
esac

# Check pnpm
if ! command -v pnpm &>/dev/null; then
  echo "[error] pnpm not found. Install via: npm install -g pnpm"
  exit 1
fi

cd "$ELECTRON_DIR"
echo "[build-client] Installing dependencies..."
# 使用 --no-frozen-lockfile：当 package.json 变更后（如移除依赖）自动更新锁文件，
# 避免锁文件与 package.json 不同步导致的 ERR_PNPM_OUTDATED_LOCKFILE。
pnpm install --no-frozen-lockfile
echo "[build-client] Building Electron client${PLATFORM:+ for $PLATFORM}..."
# shellcheck disable=SC2086
pnpm run build $BUILD_FLAG

DIST_DIR="$ELECTRON_DIR/dist"
echo "[build-client] Done. Artifacts:"
ls "$DIST_DIR" 2>/dev/null || echo "  (dist directory not found)"
