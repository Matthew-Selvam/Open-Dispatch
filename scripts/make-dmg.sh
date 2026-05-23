#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────────────────
# scripts/make-dmg.sh — build Open-Dispatch.dmg for macOS
#
# Produces:
#   dist/Open-Dispatch-<version>.dmg  — drag-to-Applications installer
#
# Prerequisites:
#   xcode-select --install        (Command Line Tools)
#   brew install create-dmg       (optional — prettier DMG)
#
# Usage:
#   bash scripts/make-dmg.sh [--version 0.4.0] [--sign "Developer ID Application: …"]
# ──────────────────────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION="0.4.0"
SIGN_ID=""
NOTARIZE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)   VERSION="$2";   shift 2 ;;
    --sign)      SIGN_ID="$2";   shift 2 ;;
    --notarize)  NOTARIZE=true;  shift ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

APP_NAME="Open-Dispatch"
APP_DIR="macos-app/OpenDispatch"
BUILD_DIR="dist/build"
STAGING_DIR="dist/staging"
DMG_PATH="dist/${APP_NAME}-${VERSION}.dmg"

mkdir -p dist "$BUILD_DIR" "$STAGING_DIR"

echo "▶ Building macOS app bundle (Swift, macOS 13+)…"

# ── compile via swift build ────────────────────────────────────────────────────
# A universal (arm64 + x86_64) build requires Xcode's xcbuild. With only the
# Command Line Tools installed, that step fails — so fall back to a native
# single-arch build, which uses SwiftPM's own build system and works under CLT.
DEV_DIR="$(xcode-select -p 2>/dev/null || true)"
if [[ "$DEV_DIR" == *Xcode*.app* ]]; then
  echo "  Xcode detected — building universal (arm64 + x86_64)…"
  ( cd "$APP_DIR" && swift build -c release --arch arm64 --arch x86_64 2>&1 )
  BINARY="${APP_DIR}/.build/apple/Products/Release/OpenDispatch"
else
  echo "  Command Line Tools only — building native $(uname -m) (install Xcode for a universal binary)…"
  ( cd "$APP_DIR" && swift build -c release 2>&1 )
  BINARY="$(cd "$APP_DIR" && swift build -c release --show-bin-path)/OpenDispatch"
fi
[ -f "$BINARY" ] || { echo "Build output not found at $BINARY"; exit 1; }

# ── assemble .app bundle ──────────────────────────────────────────────────────
APP_BUNDLE="${BUILD_DIR}/${APP_NAME}.app"
MACOS_DIR="${APP_BUNDLE}/Contents/MacOS"
RES_DIR="${APP_BUNDLE}/Contents/Resources"

rm -rf "$APP_BUNDLE"
mkdir -p "$MACOS_DIR" "$RES_DIR"

cp "$BINARY" "${MACOS_DIR}/${APP_NAME}"
cp "${APP_DIR}/Sources/OpenDispatch/Resources/Info.plist" "${APP_BUNDLE}/Contents/Info.plist"

# Bundle the Python binaries inside Resources/bin so the app is self-contained
# when users drag it to /Applications (they don't need a separate pip install).
# This step runs install.sh into a temp prefix and copies the result in.
echo "▶ Bundling open-dispatch server into app Resources…"
BUNDLE_PREFIX="${BUILD_DIR}/bundle-prefix"
rm -rf "$BUNDLE_PREFIX"
bash install.sh \
  --prefix    "$BUNDLE_PREFIX" \
  --version   "v${VERSION}" \
  --data-dir  "${HOME}/.open-dispatch" \
  --no-service
cp -r "${BUNDLE_PREFIX}/bin"             "${RES_DIR}/bin"
cp -r "${BUNDLE_PREFIX}/opt/open-dispatch" "${RES_DIR}/server"

echo "✓ App bundle assembled: ${APP_BUNDLE}"

# ── optional code-sign ────────────────────────────────────────────────────────
if [[ -n "$SIGN_ID" ]]; then
  echo "▶ Code-signing with: ${SIGN_ID}…"
  codesign --deep --force --options runtime \
    --sign "$SIGN_ID" "$APP_BUNDLE"
  echo "✓ Signed"
fi

# ── optional notarization ─────────────────────────────────────────────────────
if [[ "$NOTARIZE" == true && -n "$SIGN_ID" ]]; then
  echo "▶ Notarizing (requires Apple ID + app-specific password in keychain)…"
  xcrun notarytool submit "$APP_BUNDLE" \
    --keychain-profile "notarytool-profile" \
    --wait
  xcrun stapler staple "$APP_BUNDLE"
  echo "✓ Notarized and stapled"
fi

# ── create DMG ────────────────────────────────────────────────────────────────
rm -f "$DMG_PATH"

if command -v create-dmg &>/dev/null; then
  echo "▶ Building DMG with create-dmg…"
  create-dmg \
    --volname "${APP_NAME} ${VERSION}" \
    --background "macos-app/dmg-background.png" \
    --window-size 540 380 \
    --icon-size 120 \
    --icon "${APP_NAME}.app" 140 190 \
    --app-drop-link 400 190 \
    --hide-extension "${APP_NAME}.app" \
    "$DMG_PATH" \
    "$BUILD_DIR"
else
  echo "▶ Building plain DMG (install create-dmg for a prettier window)…"
  cp -r "$APP_BUNDLE" "${STAGING_DIR}/${APP_NAME}.app"
  # Applications symlink
  ln -sf /Applications "${STAGING_DIR}/Applications"

  hdiutil create \
    -volname "${APP_NAME} ${VERSION}" \
    -srcfolder "$STAGING_DIR" \
    -ov \
    -format UDZO \
    "$DMG_PATH"
fi

echo ""
echo "✓ DMG ready: ${DMG_PATH}"
echo "  Size: $(du -sh "$DMG_PATH" | cut -f1)"
echo ""
echo "  To distribute:"
echo "    1. Sign with: bash scripts/make-dmg.sh --sign \"Developer ID Application: Your Name (TEAMID)\""
echo "    2. Notarize:  add --notarize flag (requires Xcode + Apple ID)"
echo "    3. Upload $DMG_PATH to the GitHub release"
