#!/usr/bin/env bash
# Construye un AppImage de Auto HATS.
# Pensado para ejecutarse en Arch Linux (o en el contenedor archlinux del CI).
#
# Dependencias:
#   sudo pacman -S --needed python tk pyinstaller squashfs-tools zstd file desktop-file-utils curl
#
# Uso:
#   ./packaging/build-appimage.sh            # usa la versión de git describe
#   VERSION=1.0.0 ./packaging/build-appimage.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="${VERSION:-$(git describe --tags --always 2>/dev/null || echo 1.0.0)}"
ARCH="${ARCH:-x86_64}"
APPDIR="$ROOT/build/appimage/Auto-HATS.AppDir"
OUTDIR="$ROOT/dist"

echo "==> Compilando con PyInstaller (versión $VERSION, $ARCH)"
rm -rf "$APPDIR" "$ROOT/build/auto-hats" "$ROOT/dist/auto-hats"
python -m PyInstaller \
    --noconfirm --clean --onedir --windowed \
    --name auto-hats \
    --icon icon.ico \
    --add-data "icon.ico:." \
    --add-data "auto-hats.png:." \
    auto-hats.py

echo "==> Ensamblando AppDir"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -a "$ROOT/dist/auto-hats/." "$APPDIR/usr/bin/"
chmod +x "$APPDIR/usr/bin/auto-hats"

cp "$ROOT/packaging/auto-hats.desktop" "$APPDIR/auto-hats.desktop"
cp "$ROOT/packaging/auto-hats.desktop" "$APPDIR/usr/share/applications/auto-hats.desktop"
cp "$ROOT/auto-hats.png" "$APPDIR/auto-hats.png"
cp "$ROOT/auto-hats.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/auto-hats.png"
cp "$ROOT/packaging/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"
ln -sf auto-hats.png "$APPDIR/.DirIcon"

echo "==> Obteniendo appimagetool"
TOOL="$ROOT/build/appimage/appimagetool-$ARCH.AppImage"
if [ ! -x "$TOOL" ]; then
    mkdir -p "$(dirname "$TOOL")"
    curl -fsSL -o "$TOOL" \
        "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$ARCH.AppImage"
    chmod +x "$TOOL"
fi

echo "==> Generando AppImage"
mkdir -p "$OUTDIR"
OUT="$OUTDIR/Auto-HATS-$VERSION-$ARCH.AppImage"
rm -f "$OUT"
if ! ARCH="$ARCH" VERSION="$VERSION" "$TOOL" --no-appstream "$APPDIR" "$OUT"; then
    echo "==> Reintentando sin FUSE (--appimage-extract-and-run)"
    rm -f "$OUT"
    ARCH="$ARCH" VERSION="$VERSION" "$TOOL" --appimage-extract-and-run --no-appstream "$APPDIR" "$OUT"
fi

echo "==> Listo: $OUT"
ls -lh "$OUT"
