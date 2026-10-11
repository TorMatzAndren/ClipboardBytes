#!/usr/bin/env bash
set -euo pipefail

# Reproducible Debian archive and compressed members.
export SOURCE_DATE_EPOCH=0
export TZ=UTC
export LC_ALL=C
umask 022

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION=0.2.0
PACKAGE=clipboardbytes
ARCH=all

OUTPUT="${1:-$ROOT/dist}"
mkdir -p "$OUTPUT"
OUTPUT="$(cd "$OUTPUT" && pwd)"

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

PKGROOT="$STAGE/${PACKAGE}_${VERSION}_${ARCH}"

mkdir -p \
  "$PKGROOT/DEBIAN" \
  "$PKGROOT/opt/clipboardbytes" \
  "$PKGROOT/usr/bin" \
  "$PKGROOT/usr/share/applications" \
  "$PKGROOT/usr/share/doc/clipboardbytes"

cat > "$PKGROOT/DEBIAN/control" <<CONTROL
Package: clipboardbytes
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Maintainer: ClipboardBytes Project
Depends: python3 (>= 3.10), python3-pyqt6, libx11-6, libxres1, libxfixes3
Description: Desktop clipboard inspection and classification
 ClipboardBytes is a PyQt6 clipboard inspection application.
 It supports text and image inspection, code classification,
 clipboard exports, headless operation and X11 diagnostics.
CONTROL

SOURCES=(
  clipboardbytes.py
  clipboard_payload.py
  clipboard_signal.py
  clipboard_diagnostics.py
  clipboard_exporter.py
  code_detector.py
  config_store.py
  jarri_clipboard_register.py
  overlay_window.py
  window_manager.py
)

for source in "${SOURCES[@]}"; do
  test -f "$ROOT/$source"
  install -m 0644 "$ROOT/$source" \
    "$PKGROOT/opt/clipboardbytes/$source"
done

install -m 0755 \
  "$ROOT/packaging/debian/clipboardbytes" \
  "$PKGROOT/usr/bin/clipboardbytes"

install -m 0644 \
  "$ROOT/clipboard_xres_diagnostic.py" \
  "$PKGROOT/opt/clipboardbytes/clipboard_xres_diagnostic.py"

install -m 0644 \
  "$ROOT/packaging/debian/clipboardbytes.desktop" \
  "$PKGROOT/usr/share/applications/clipboardbytes.desktop"

install -m 0644 \
  "$ROOT/README.md" \
  "$PKGROOT/usr/share/doc/clipboardbytes/README.md"

find "$PKGROOT" -type d -exec chmod 0755 {} +
find "$PKGROOT" -exec touch -h -d '@0' {} +

dpkg-deb --root-owner-group --build \
  "$PKGROOT" \
  "$OUTPUT/${PACKAGE}_${VERSION}_${ARCH}.deb" >/dev/null

echo "$OUTPUT/${PACKAGE}_${VERSION}_${ARCH}.deb"
