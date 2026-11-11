#!/usr/bin/env bash
# Instala Auto HATS en el usuario actual (Linux).
#
# Uso:
#   curl -fsSL https://raw.githubusercontent.com/Llop-Estepari/auto-hats/main/install.sh | bash
#   curl -fsSL https://raw.githubusercontent.com/Llop-Estepari/auto-hats/main/install.sh | bash -s -- --uninstall
set -euo pipefail

REPO="Llop-Estepari/auto-hats"
APP_DIR="$HOME/.local/share/auto-hats"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/32x32/apps"
APPIMAGE="$APP_DIR/auto-hats.AppImage"
LINK="$BIN_DIR/auto-hats"
DESKTOP_FILE="$DESKTOP_DIR/auto-hats.desktop"
ICON_FILE="$ICON_DIR/auto-hats.png"

uninstall() {
    rm -f "$LINK" "$DESKTOP_FILE" "$ICON_FILE"
    rm -rf "$APP_DIR"
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
    fi
    echo "Auto HATS desinstalado."
    exit 0
}

if [ "${1:-}" = "--uninstall" ]; then
    uninstall
fi

mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR"

echo "==> Consultando la última release de $REPO"
api_json="$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest")"
asset_url="$(printf '%s' "$api_json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for asset in data.get("assets", []):
    if asset.get("name", "").endswith("x86_64.AppImage"):
        print(asset["browser_download_url"])
        break
')"
if [ -z "$asset_url" ]; then
    echo "No se encontró un AppImage en la última release." >&2
    exit 1
fi

echo "==> Descargando AppImage"
curl -fL --progress-bar -o "$APPIMAGE" "$asset_url"
chmod +x "$APPIMAGE"

ln -sfn "$APPIMAGE" "$LINK"

echo "==> Descargando icono"
curl -fsSL "https://raw.githubusercontent.com/$REPO/main/auto-hats.png" -o "$ICON_FILE" || true

echo "==> Creando lanzador"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Auto HATS
Comment=Formatea una unidad extraíble a FAT32 y copia los archivos de HATS
Exec=$LINK
Icon=auto-hats
Terminal=false
Categories=Utility;System;
StartupNotify=true
EOF

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" >/dev/null 2>&1 || true
fi

echo
echo "Auto HATS instalado correctamente."
echo "Ejecuta: auto-hats"
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) echo "Aviso: $BIN_DIR no está en tu PATH. Añádelo para usar el comando 'auto-hats'." ;;
esac
EOF