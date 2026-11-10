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
- Windows (recomendado) o Linux/macOS con `mkfs.vfat` disponible.

## Uso

```bash
python auto-hats.py
```

1. Selecciona la unidad de disco destino.
2. Revisa o edita la URL del ZIP del release.
3. Pulsa **Guardar URL, Formatear a FAT32 y Copiar** y confirma la advertencia.

## Compilar el ejecutable

```bash
pip install pyinstaller
pyinstaller auto-hats.spec
```

El ejecutable se genera en `dist/auto-hats.exe`.

## Estructura del proyecto

```
auto-hats.py     # Código fuente principal
auto-hats.spec   # Configuración de PyInstaller
icon.ico         # Icono de la aplicación y del ejecutable
```

## Licencia

MIT
