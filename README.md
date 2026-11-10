# Auto HATS

Utilidad de escritorio con interfaz gráfica (Tkinter) que descarga la última
versión de **HATS** desde un release de GitHub, formatea una unidad extraíble a
**FAT32** y copia los archivos descargados en ella.

> ⚠️ **Advertencia:** la aplicación borra **todos** los datos de la unidad
> seleccionada. Verifica dos veces la letra de la unidad antes de continuar.

## Características

- Detecta automáticamente las unidades disponibles (con su etiqueta de volumen).
- Permite editar y guardar la URL del ZIP del release (se persiste en `config.json`).
- Descarga y descomprime el ZIP en una carpeta temporal.
- Formatea la unidad destino a FAT32 (`format` en Windows, `mkfs.vfat` en Linux/macOS).
- Copia el contenido descargado a la unidad formateada.

## Requisitos

- Python 3.8 o superior (Tkinter incluido en la instalación oficial).
- Windows (recomendado) o Linux con `mkfs.vfat`, `findmnt`, `udisksctl` y `pkexec`.

### Arch Linux

```bash
sudo pacman -S --needed python tk dosfstools udisks2 polkit util-linux
```

## Uso

```bash
python auto-hats.py
```

1. Selecciona la unidad de disco destino.
2. Revisa o edita la URL del ZIP del release.
3. Pulsa **Guardar URL, Formatear a FAT32 y Copiar** y confirma la advertencia.

En Linux la unidad se desmonta, se formatea con `mkfs.vfat` (pidiendo permisos
con `pkexec` si hace falta) y se vuelve a montar con `udisksctl`.

## AppImage para Linux (Arch)

El AppImage se compila automáticamente en un contenedor **Arch Linux** mediante
GitHub Actions (`.github/workflows/build-appimage.yml`). El resultado queda como
artefacto de la ejecución y, si se sube un tag `v*`, se publica como release.

Para compilarlo localmente en Arch:

```bash
sudo pacman -S --needed python tk pyinstaller squashfs-tools zstd file desktop-file-utils curl
./packaging/build-appimage.sh
```

El archivo se genera en `dist/Auto-HATS-<versión>-x86_64.AppImage`.

```bash
chmod +x dist/Auto-HATS-*.AppImage
./dist/Auto-HATS-*.AppImage
```

## Compilar el ejecutable de Windows

```bash
pip install pyinstaller
pyinstaller auto-hats.spec
```

El ejecutable se genera en `dist/auto-hats.exe`.

## Estructura del proyecto

```
auto-hats.py                     # Código fuente principal
auto-hats.spec                   # Configuración de PyInstaller (Windows)
auto-hats.png                    # Icono PNG (AppImage / Linux)
icon.ico                         # Icono de la aplicación y del ejecutable
packaging/
  AppRun                         # Punto de entrada del AppImage
  auto-hats.desktop              # Entrada de menú del AppImage
  build-appimage.sh              # Script de compilación del AppImage
.github/workflows/
  build-appimage.yml             # CI que compila el AppImage en Arch Linux
```

## Licencia

MIT
