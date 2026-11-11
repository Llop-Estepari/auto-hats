import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import queue
import zipfile
import urllib.request
import ctypes
import json
import tkinter as tk
from tkinter import ttk, font as tkfont, filedialog

# Paleta del tema oscuro (a juego con el icono verde de la aplicación)
COLOR_BG = "#0f1419"
COLOR_CARD = "#1a2229"
COLOR_CARD_ALT = "#212b34"
COLOR_BORDER = "#2c3742"
COLOR_TEXT = "#e8eef2"
COLOR_MUTED = "#93a1ad"
COLOR_ACCENT = "#2eb85c"
COLOR_ACCENT_HOVER = "#27a04f"
COLOR_ACCENT_PRESSED = "#218a44"
COLOR_ACCENT_SOFT = "#17301f"
COLOR_ACCENT_TEXT = "#08130c"
COLOR_WARNING = "#f0b429"
COLOR_ERROR = "#ef6b6b"
COLOR_TROUGH = "#26313a"

def obtener_ruta_config():
    """Obtiene una ruta de configuración oculta y persistente según el sistema operativo."""
    if sys.platform == "win32":
        base_dir = os.environ.get('APPDATA', os.path.expanduser('~'))
    else:
        base_dir = os.path.expanduser('~/.config')
        
    app_dir = os.path.join(base_dir, 'AutoHats')
    if not os.path.exists(app_dir):
        os.makedirs(app_dir, exist_ok=True)
        
    return os.path.join(app_dir, 'config.json')

CONFIG_FILE = obtener_ruta_config()
DEFAULT_URL = "https://github.com/sthetix/HATS/releases/download/HATS-2026-11-09-5bf0df1/HATS-2026-11-09-5bf0df1.zip"

def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso compatible con PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

CONFIG_DEFAULT = {"modo": "release", "url": DEFAULT_URL, "carpeta": ""}

def cargar_config():
    """Carga la configuración persistente (modo, URL y carpeta local)."""
    config = dict(CONFIG_DEFAULT)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                if data.get("modo") in ("release", "local"):
                    config["modo"] = data["modo"]
                if isinstance(data.get("url"), str) and data["url"].strip():
                    config["url"] = data["url"].strip()
                if isinstance(data.get("carpeta"), str):
                    config["carpeta"] = data["carpeta"]
                # Compatibilidad con versiones anteriores (solo "url")
                if "modo" not in data and isinstance(data.get("url"), str):
                    config["modo"] = "release"
        except Exception:
            pass
    return config

def guardar_config(config):
    """Guarda la configuración persistente."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(
                {
                    "modo": config.get("modo", "release"),
                    "url": config.get("url", DEFAULT_URL),
                    "carpeta": config.get("carpeta", ""),
                },
                f,
                indent=4,
            )
    except Exception as e:
        print(f"Error al guardar la configuración: {e}")

def _tamano_legible(num_bytes):
    """Convierte un tamaño en bytes a un texto legible."""
    try:
        valor = float(num_bytes)
    except (TypeError, ValueError):
        return "?"
    for unidad in ("B", "KB", "MB", "GB", "TB"):
        if valor < 1000 or unidad == "TB":
            return f"{valor:.0f} {unidad}" if unidad == "B" else f"{valor:.1f} {unidad}"
        valor /= 1000
    return f"{valor:.1f} TB"

def _disco_raiz():
    """Nombre del disco que contiene el sistema de archivos raíz (p. ej. nvme0n1)."""
    res = _ejecutar(["findmnt", "-n", "-o", "SOURCE", "/"])
    if res is None or res.returncode != 0 or not res.stdout.strip():
        return None
    dispositivo = re.sub(r"\[.*$", "", res.stdout.strip().splitlines()[0])
    res = _ejecutar(["lsblk", "-n", "-o", "PKNAME", dispositivo])
    if res is not None and res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip().splitlines()[0]
    return dispositivo.rsplit("/", 1)[-1]

def obtener_unidades_linux():
    """Detecta solo discos extraíbles (USB/SD) y devuelve (texto, punto_montaje, dispositivo)."""
    if shutil.which("lsblk") is None:
        return []
    res = subprocess.run(
        ["lsblk", "-J", "-b", "-o",
         "NAME,PATH,TYPE,RM,TRAN,MOUNTPOINTS,LABEL,SIZE,FSTYPE"],
        capture_output=True, text=True
    )
    if res.returncode != 0:
        return []
    try:
        datos = json.loads(res.stdout)
    except ValueError:
        return []

    raiz = _disco_raiz()
    unidades = []
    for disco in datos.get("blockdevices", []):
        if disco.get("type") != "disk" or disco.get("name") == raiz:
            continue  # nunca ofrecer el disco donde está el sistema
        if not (bool(disco.get("rm")) or disco.get("tran") in ("usb", "mmc")):
            continue

        candidatos = disco.get("children") or []
        if not candidatos and disco.get("fstype"):
            candidatos = [disco]
        for particion in candidatos:
            if particion.get("type") not in ("part", "disk") or not particion.get("fstype"):
                continue
            puntos = [p for p in (particion.get("mountpoints") or []) if p and p.startswith("/")]
            etiqueta = (particion.get("label") or "").strip() or "sin etiqueta"
            dispositivo = particion.get("path") or f"/dev/{particion.get('name', '?')}"
            texto = f"{etiqueta} — {dispositivo} ({_tamano_legible(particion.get('size'))})"
            if not puntos:
                texto += " · sin montar"
            unidades.append((texto, puntos[0] if puntos else None, dispositivo))
    return unidades

def obtener_unidades_con_nombre():
    """Detecta las unidades disponibles y devuelve (texto, punto_montaje, dispositivo)."""
    unidades = []
    if sys.platform == "win32":
        import string
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drive_letter = f"{letter}:"
                volume_name_buf = ctypes.create_unicode_buffer(261)
                file_system_name_buf = ctypes.create_unicode_buffer(261)
                serial_number = ctypes.c_ulong()
                max_component_len = ctypes.c_ulong()
                file_system_flags = ctypes.c_ulong()
                
                result = ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(drive_letter + "\\"),
                    volume_name_buf,
                    ctypes.sizeof(volume_name_buf),
                    ctypes.byref(serial_number),
                    ctypes.byref(max_component_len),
                    ctypes.byref(file_system_flags),
                    file_system_name_buf,
                    ctypes.sizeof(file_system_name_buf)
                )
                
                vol_name = volume_name_buf.value if result else ""
                texto = f"{drive_letter} [{vol_name}]" if vol_name else drive_letter
                unidades.append((texto, drive_letter, None))
            bitmask >>= 1
    else:
        unidades = obtener_unidades_linux()
    return unidades

def _ejecutar(cmd):
    """Ejecuta un comando sin shell y devuelve el resultado (o None si falta el binario)."""
    if shutil.which(cmd[0]) is None:
        return None
    return subprocess.run(cmd, capture_output=True, text=True)

def resolver_dispositivo_linux(punto_montaje):
    """Obtiene el dispositivo de bloque (/dev/sdX1) asociado a un punto de montaje."""
    if shutil.which("findmnt") is None:
        raise Exception("Falta el comando 'findmnt' (paquete util-linux).")
    res = subprocess.run(
        ["findmnt", "-n", "-o", "SOURCE", "--target", punto_montaje],
        capture_output=True, text=True
    )
    device = res.stdout.strip().splitlines()[0] if res.stdout.strip() else ""
    if res.returncode != 0 or not device.startswith("/dev/"):
        raise Exception(
            f"No se pudo determinar el dispositivo de '{punto_montaje}'.\n"
            "Asegúrate de que la unidad está montada y es un dispositivo de bloque."
        )
    return device

def desmontar_linux(device, punto_montaje):
    """Desmonta la unidad usando udisksctl y, si falla, pkexec umount."""
    res = _ejecutar(["udisksctl", "unmount", "-b", device])
    if res is not None and res.returncode == 0:
        return
    res = _ejecutar(["pkexec", "umount", punto_montaje])
    if res is None or res.returncode != 0:
        detalle = (res.stderr or res.stdout).strip() if res is not None else "pkexec no está instalado"
        raise Exception(f"No se pudo desmontar {punto_montaje}: {detalle}")

def _punto_montaje_de(device):
    """Devuelve el punto de montaje actual de un dispositivo, o None."""
    res = _ejecutar(["findmnt", "-n", "-o", "TARGET", "--source", device])
    if res is not None and res.returncode == 0 and res.stdout.strip():
        return res.stdout.strip().splitlines()[0]
    return None

def _object_path_udisks(device):
    """Convierte /dev/sdX1 en su ruta de objeto D-Bus de UDisks2."""
    return "/org/freedesktop/UDisks2/block_devices/" + os.path.basename(device)


def _formatear_udisks(device):
    """Formatea el dispositivo a FAT32 usando UDisks2 (sin pedir contraseña)."""
    object_path = _object_path_udisks(device)
    if shutil.which("gdbus") is not None:
        cmd = [
            "gdbus", "call", "--system",
            "--dest", "org.freedesktop.UDisks2",
            "--object-path", object_path,
            "--method", "org.freedesktop.UDisks2.Block.Format",
            "vfat", "{'label': <'HATS_DISK'>}",
        ]
    elif shutil.which("busctl") is not None:
        cmd = [
            "busctl", "call", "--system",
            "org.freedesktop.UDisks2", object_path,
            "org.freedesktop.UDisks2.Block", "Format",
            "s a{sv}", "vfat", "1", "label", "s", "HATS_DISK",
        ]
    else:
        raise Exception("Falta 'gdbus' o 'busctl' (paquete glib2/systemd).")
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        detalle = (res.stderr or res.stdout).strip()
        raise Exception(f"UDisks2 no pudo formatear {device}: {detalle}")


def _montar_udisks(device, punto_montaje):
    """Monta el dispositivo con udisksctl y devuelve el punto de montaje."""
    nuevo_punto = punto_montaje
    res = None
    for intento in range(3):
        res = _ejecutar(["udisksctl", "mount", "-b", device])
        if res is not None and res.returncode == 0:
            break
        if intento < 2:
            time.sleep(1)  # udev puede tardar en refrescar el dispositivo recién formateado
    if res is not None and res.returncode == 0:
        coincidencia = re.search(r"\bat (.+?)\.?\s*$", res.stdout.strip())
        nuevo_punto = (coincidencia.group(1).rstrip(".") if coincidencia else None) or _punto_montaje_de(device)
        if not nuevo_punto:
            raise Exception(
                f"El disco se formateó pero no se pudo determinar dónde se montó {device}.\n"
                "Móntalo manualmente y copia el contenido a mano."
            )
        return nuevo_punto
    if not punto_montaje:
        detalle = (res.stderr or res.stdout).strip() if res is not None else "udisksctl no está instalado"
        raise Exception(
            f"El disco se formateó pero no se pudo volver a montar {device}:\n{detalle}\n"
            "Móntalo manualmente y copia el contenido a mano."
        )
    res = _ejecutar(["pkexec", "mount", device, punto_montaje])
    if res is None or res.returncode != 0:
        detalle = (res.stderr or res.stdout).strip() if res is not None else "pkexec no está instalado"
        raise Exception(
            f"El disco se formateó pero no se pudo volver a montar {device}:\n{detalle}"
        )
    return punto_montaje


def formatear_linux(punto_montaje=None, dispositivo=None):
    """Formatea la unidad en FAT32 y devuelve el punto de montaje resultante."""
    device = dispositivo or resolver_dispositivo_linux(punto_montaje)
    punto_montaje = punto_montaje or _punto_montaje_de(device)
    if punto_montaje:
        desmontar_linux(device, punto_montaje)

    # Primero intentamos UDisks2: no pide contraseña en sesiones locales activas.
    formateado_udisks = False
    try:
        _formatear_udisks(device)
        formateado_udisks = True
        return _montar_udisks(device, punto_montaje)
    except Exception as e_udisks:
        if formateado_udisks:
            raise Exception(f"El disco se formateó pero no se pudo montar: {e_udisks}")

    # Fallback clásico con mkfs.vfat (+ pkexec si hace falta).
    cmd = ["mkfs.vfat", "-F", "32", "-n", "HATS_DISK", device]
    if shutil.which("mkfs.vfat") is None:
        raise Exception(
            "Falta 'mkfs.vfat'. Instálalo con:\n\n"
            "    sudo pacman -S dosfstools\n\n"
            "También necesitas 'udisks2' para formatear sin contraseña."
        )

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        res = _ejecutar(["pkexec"] + cmd)
        if res is None:
            raise Exception(f"No se pudo formatear {device}: hace falta 'pkexec' (paquete polkit) o permisos de root.")
        if res.returncode != 0:
            raise Exception(f"Error al formatear {device}:\n{(res.stderr or res.stdout).strip()}")

    return _montar_udisks(device, punto_montaje)

def _elegir_familia(root, candidatas):
    """Devuelve la primera familia tipográfica disponible del sistema."""
    try:
        disponibles = set(tkfont.families(root))
    except Exception:
        disponibles = set()
    for nombre in candidatas:
        if nombre in disponibles:
            return nombre
    try:
        return tkfont.nametofont("TkDefaultFont").actual("family")
    except Exception:
        return "Helvetica"

def configurar_estilos(root):
    """Aplica el tema oscuro y devuelve la familia tipográfica elegida."""
    familia = _elegir_familia(
        root, ("Segoe UI", "Inter", "Noto Sans", "DejaVu Sans", "Cantarell", "Helvetica")
    )
    estilo = ttk.Style(root)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    estilo.configure("TFrame", background=COLOR_BG)

    # Botón principal
    estilo.configure(
        "Accent.TButton",
        background=COLOR_ACCENT,
        foreground=COLOR_ACCENT_TEXT,
        font=(familia, 10, "bold"),
        borderwidth=0,
        focusthickness=0,
        focuscolor=COLOR_ACCENT,
        padding=(18, 12),
    )
    estilo.map(
        "Accent.TButton",
        background=[
            ("disabled", "#2a3a30"),
            ("pressed", COLOR_ACCENT_PRESSED),
            ("active", COLOR_ACCENT_HOVER),
        ],
        foreground=[("disabled", "#6f8a7a")],
    )

    # Botón secundario
    estilo.configure(
        "Ghost.TButton",
        background=COLOR_CARD_ALT,
        foreground=COLOR_TEXT,
        font=(familia, 10),
        borderwidth=0,
        focusthickness=0,
        focuscolor=COLOR_CARD_ALT,
        padding=(12, 9),
    )
    estilo.map(
        "Ghost.TButton",
        background=[
            ("disabled", "#232b32"),
            ("pressed", "#2a353f"),
            ("active", "#2a353f"),
        ],
        foreground=[("disabled", COLOR_MUTED)],
    )

    # Campos de texto
    estilo.configure(
        "Dark.TEntry",
        fieldbackground=COLOR_CARD_ALT,
        foreground=COLOR_TEXT,
        insertcolor=COLOR_TEXT,
        bordercolor=COLOR_BORDER,
        lightcolor=COLOR_BORDER,
        darkcolor=COLOR_BORDER,
        selectbackground=COLOR_ACCENT,
        selectforeground=COLOR_ACCENT_TEXT,
        padding=8,
    )
    estilo.map(
        "Dark.TEntry",
        bordercolor=[("focus", COLOR_ACCENT)],
        lightcolor=[("focus", COLOR_ACCENT)],
        darkcolor=[("focus", COLOR_ACCENT)],
    )

    # Desplegable de unidades (incluida su lista)
    estilo.configure(
        "Dark.TCombobox",
        fieldbackground=COLOR_CARD_ALT,
        background=COLOR_CARD_ALT,
        foreground=COLOR_TEXT,
        arrowcolor=COLOR_MUTED,
        bordercolor=COLOR_BORDER,
        lightcolor=COLOR_BORDER,
        darkcolor=COLOR_BORDER,
        insertcolor=COLOR_TEXT,
        padding=7,
    )
    estilo.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", COLOR_CARD_ALT), ("disabled", "#1b232b")],
        foreground=[("readonly", COLOR_TEXT), ("disabled", COLOR_MUTED)],
        selectbackground=[("readonly", COLOR_CARD_ALT)],
        selectforeground=[("readonly", COLOR_TEXT)],
        arrowcolor=[("disabled", "#586470")],
    )
    root.option_add("*TCombobox*Listbox.background", COLOR_CARD_ALT)
    root.option_add("*TCombobox*Listbox.foreground", COLOR_TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", COLOR_ACCENT)
    root.option_add("*TCombobox*Listbox.selectForeground", COLOR_ACCENT_TEXT)
    root.option_add("*TCombobox*Listbox.font", f"{{{familia}}} 10")

    # Barra de progreso
    estilo.configure(
        "Accent.Horizontal.TProgressbar",
        troughcolor=COLOR_TROUGH,
        background=COLOR_ACCENT,
        bordercolor=COLOR_TROUGH,
        lightcolor=COLOR_ACCENT,
        darkcolor=COLOR_ACCENT,
        thickness=12,
    )

    return familia

def copiar_con_progreso(origen, destino, al_progresar=None):
    """Copia el contenido de origen en destino por bloques, informando del progreso."""
    archivos = []
    total = 0
    for raiz, _directorios, ficheros in os.walk(origen):
        relativa = os.path.relpath(raiz, origen)
        if relativa != ".":
            os.makedirs(os.path.join(destino, relativa), exist_ok=True)
        for nombre in ficheros:
            ruta = os.path.join(raiz, nombre)
            try:
                total += os.path.getsize(ruta)
            except OSError:
                pass
            archivos.append(ruta)

    copiados = 0
    for ruta in archivos:
        relativa = os.path.relpath(ruta, origen)
        destino_archivo = os.path.join(destino, relativa)
        carpeta = os.path.dirname(destino_archivo)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        with open(ruta, "rb") as origen_f, open(destino_archivo, "wb") as destino_f:
            while True:
                bloque = origen_f.read(1024 * 1024)
                if not bloque:
                    break
                destino_f.write(bloque)
                copiados += len(bloque)
                if al_progresar is not None:
                    al_progresar(copiados, total, len(archivos))
        shutil.copystat(ruta, destino_archivo)

    if al_progresar is not None and not archivos:
        al_progresar(0, 0, 0)

class AppHatsPersistentFormatter:
    PASOS = ("Descargar", "Formatear", "Copiar")

    def __init__(self, root):
        self.root = root
        self.root.title("Auto HATS")
        self.root.configure(bg=COLOR_BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        self.familia = configurar_estilos(root)
        self.cola = queue.Queue()
        self.procesando = False
        self._after_id = None
        self._indeterminado = False
        self._paso_actual = 0
        self._icono = None
        self.unidades = {}

        self.config = cargar_config()
        self.modo_origen = self.config.get("modo", "release")
        if self.modo_origen not in ("release", "local"):
            self.modo_origen = "release"
        self.nombres_pasos = self._nombres_pasos_para(self.modo_origen)

        self._cargar_icono()
        self._construir_interfaz()
        self.refrescar_unidades()
        self._centrar_ventana()

    # ------------------------------------------------------------------ UI
    def _cargar_icono(self):
        try:
            if sys.platform == "win32":
                self.root.iconbitmap(resource_path("icon.ico"))
            else:
                icono = tk.PhotoImage(file=resource_path("auto-hats.png"))
                self.root.iconphoto(True, icono)
                self._icono = icono
        except Exception:
            pass

    @staticmethod
    def _nombres_pasos_para(modo):
        if modo == "local":
            return ("Formatear", "Copiar")
        return ("Descargar", "Formatear", "Copiar")

    def _seccion(self, parent, titulo, pady=(16, 0)):
        tarjeta = tk.Frame(
            parent, bg=COLOR_CARD, highlightbackground=COLOR_BORDER, highlightthickness=1
        )
        tarjeta.pack(fill="x", pady=pady)
        tk.Label(
            tarjeta,
            text=titulo.upper(),
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            font=(self.familia, 8, "bold"),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(12, 8))
        return tarjeta

    def _construir_pasos(self, parent):
        self.pasos = []
        for indice, nombre in enumerate(self.nombres_pasos):
            etiqueta = tk.Label(
                parent,
                text=f"{indice + 1}  {nombre}",
                bg=COLOR_CARD_ALT,
                fg=COLOR_MUTED,
                font=(self.familia, 9, "bold"),
                padx=10,
                pady=5,
            )
            etiqueta.pack(side="left", padx=(0, 6))
            self.pasos.append(etiqueta)

    def _construir_interfaz(self):
        contenedor = tk.Frame(self.root, bg=COLOR_BG)
        contenedor.pack(fill="both", expand=True, padx=24, pady=22)

        # Origen de los archivos
        tarjeta = self._seccion(contenedor, "Origen de los archivos")
        fila_modo = tk.Frame(tarjeta, bg=COLOR_CARD)
        fila_modo.pack(fill="x", padx=16, pady=(0, 8))
        self.btn_modo_release = ttk.Button(
            fila_modo, text="Release (URL)", style="Ghost.TButton",
            command=lambda: self._cambiar_modo("release"),
        )
        self.btn_modo_release.pack(side="left")
        self.btn_modo_local = ttk.Button(
            fila_modo, text="Carpeta local", style="Ghost.TButton",
            command=lambda: self._cambiar_modo("local"),
        )
        self.btn_modo_local.pack(side="left", padx=(8, 0))

        self.panel_release = tk.Frame(tarjeta, bg=COLOR_CARD)
        self.panel_release.pack(fill="x")
        self.entry_url = ttk.Entry(
            self.panel_release,
            style="Dark.TEntry",
            font=(self.familia, 10),
        )
        self.entry_url.pack(fill="x", padx=16)
        self.entry_url.insert(0, self.config.get("url", DEFAULT_URL))
        tk.Label(
            self.panel_release,
            text="Se guarda automáticamente para la próxima vez.",
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            font=(self.familia, 9),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(4, 12))

        self.panel_local = tk.Frame(tarjeta, bg=COLOR_CARD)
        self.panel_local.pack(fill="x")
        fila_carpeta = tk.Frame(self.panel_local, bg=COLOR_CARD)
        fila_carpeta.pack(fill="x", padx=16)
        self.entry_carpeta = ttk.Entry(
            fila_carpeta,
            style="Dark.TEntry",
            font=(self.familia, 10),
        )
        self.entry_carpeta.pack(side="left", fill="x", expand=True)
        self.entry_carpeta.insert(0, self.config.get("carpeta", ""))
        ttk.Button(
            fila_carpeta, text="Elegir…", style="Ghost.TButton",
            command=self._elegir_carpeta,
        ).pack(side="left", padx=(8, 0))
        tk.Label(
            self.panel_local,
            text="Se copiará todo el contenido de la carpeta a la unidad formateada.",
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            font=(self.familia, 9),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(4, 12))

        self._aplicar_modo_visual()

        # Unidad de destino
        tarjeta = self._seccion(contenedor, "Unidad de destino")
        fila = tk.Frame(tarjeta, bg=COLOR_CARD)
        fila.pack(fill="x", padx=16)
        self.combo_unidades = ttk.Combobox(
            fila, state="readonly", style="Dark.TCombobox", font=(self.familia, 10)
        )
        self.combo_unidades.pack(side="left", fill="x", expand=True)
        self.btn_refrescar = ttk.Button(
            fila, text="↻", width=3, style="Ghost.TButton", command=self.refrescar_unidades
        )
        self.btn_refrescar.pack(side="left", padx=(8, 0))
        self.lbl_unidades = tk.Label(
            tarjeta, text="Buscando unidades…", bg=COLOR_CARD, fg=COLOR_MUTED,
            font=(self.familia, 9), anchor="w",
        )
        self.lbl_unidades.pack(fill="x", padx=16, pady=(6, 0))
        tk.Label(
            tarjeta,
            text="⚠  Se borrarán todos los datos de la unidad seleccionada",
            bg=COLOR_CARD,
            fg=COLOR_WARNING,
            font=(self.familia, 9),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(2, 12))

        # URL del release
        tarjeta = self._seccion(contenedor, "URL del release")
        self.entry_url = ttk.Entry(
            tarjeta,
            style="Dark.TEntry",
            font=(self.familia, 10),
        )
        self.entry_url.pack(fill="x", padx=16)
        self.entry_url.insert(0, self.config.get("url", DEFAULT_URL))
        tk.Label(
            tarjeta,
            text="Se guarda automáticamente para la próxima vez.",
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            font=(self.familia, 9),
            anchor="w",
        ).pack(fill="x", padx=16, pady=(4, 12))

        # Progreso
        tarjeta = self._seccion(contenedor, "Progreso")
        fila_pasos = tk.Frame(tarjeta, bg=COLOR_CARD)
        fila_pasos.pack(fill="x", padx=16)
        self._fila_pasos = fila_pasos
        self.pasos = []
        self._construir_pasos(fila_pasos)

        fila_estado = tk.Frame(tarjeta, bg=COLOR_CARD)
        fila_estado.pack(fill="x", padx=16, pady=(12, 6))
        self.lbl_estado = tk.Label(
            fila_estado, text="Listo para comenzar", bg=COLOR_CARD, fg=COLOR_TEXT,
            font=(self.familia, 10, "bold"), anchor="w",
        )
        self.lbl_estado.pack(side="left")
        self.lbl_pct = tk.Label(
            fila_estado, text="0 %", bg=COLOR_CARD, fg=COLOR_ACCENT,
            font=(self.familia, 10, "bold"), anchor="e",
        )
        self.lbl_pct.pack(side="right")

        self.barra = ttk.Progressbar(
            tarjeta, style="Accent.Horizontal.TProgressbar",
            mode="determinate", maximum=100, value=0,
        )
        self.barra.pack(fill="x", padx=16)

        self.lbl_detalle = tk.Label(
            tarjeta,
            text="Selecciona una unidad y pulsa el botón para empezar.",
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            font=(self.familia, 9),
            anchor="w",
        )
        self.lbl_detalle.pack(fill="x", padx=16, pady=(6, 14))

        # Acción principal
        self.btn_ejecutar = ttk.Button(
            contenedor, text="Formatear y copiar",
            style="Accent.TButton", command=self.ejecutar_proceso,
        )
        self.btn_ejecutar.pack(fill="x", pady=(18, 0))

    def _centrar_ventana(self):
        self.root.update_idletasks()
        ancho = max(600, self.root.winfo_reqwidth())
        alto = self.root.winfo_reqheight()
        x = max(0, (self.root.winfo_screenwidth() - ancho) // 2)
        y = max(0, (self.root.winfo_screenheight() - alto) // 2 - 20)
        self.root.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _pintar_paso(self, etiqueta, estado, indice):
        if estado == "activo":
            fondo, color = COLOR_ACCENT_SOFT, COLOR_ACCENT
        elif estado == "hecho":
            fondo, color = COLOR_CARD_ALT, COLOR_ACCENT
        elif estado == "error":
            fondo, color = "#3a1d1d", COLOR_ERROR
        else:
            fondo, color = COLOR_CARD_ALT, COLOR_MUTED
        texto = f"{indice + 1}  {self.nombres_pasos[indice]}"
        if estado == "hecho":
            texto = f"✓  {self.nombres_pasos[indice]}"
        elif estado == "error":
            texto = f"✕  {self.nombres_pasos[indice]}"
        etiqueta.config(bg=fondo, fg=color, text=texto)

    def _aplicar_modo_visual(self):
        if self.modo_origen == "release":
            self.btn_modo_release.config(style="Accent.TButton")
            self.btn_modo_local.config(style="Ghost.TButton")
            self.panel_release.pack(fill="x")
            self.panel_local.pack_forget()
        else:
            self.btn_modo_release.config(style="Ghost.TButton")
            self.btn_modo_local.config(style="Accent.TButton")
            self.panel_release.pack_forget()
            self.panel_local.pack(fill="x")

    def _cambiar_modo(self, modo):
        if modo == self.modo_origen or self.procesando:
            return
        self.modo_origen = modo
        self.nombres_pasos = self._nombres_pasos_para(modo)
        # Reconstruir pills
        for widget in self.pasos:
            widget.destroy()
        # fila_pasos is parent; find it via first paso's parent if exists
        parent = None
        if hasattr(self, "_fila_pasos"):
            parent = self._fila_pasos
        if parent is None:
            # fallback: recreate in the progress card's first child frame
            parent = self.pasos[0].master if self.pasos else None
        if parent is not None:
            self._construir_pasos(parent)
        self._aplicar_modo_visual()
        self._guardar_config_actual()

    def _elegir_carpeta(self):
        inicial = self.entry_carpeta.get().strip() or self.config.get("carpeta") or os.path.expanduser("~")
        carpeta = filedialog.askdirectory(title="Selecciona la carpeta con los archivos de HATS", initialdir=inicial)
        if carpeta:
            self.entry_carpeta.delete(0, "end")
            self.entry_carpeta.insert(0, carpeta)

    def _guardar_config_actual(self):
        self.config["modo"] = self.modo_origen
        self.config["url"] = self.entry_url.get().strip() or DEFAULT_URL
        self.config["carpeta"] = self.entry_carpeta.get().strip()
        guardar_config(self.config)

    # ------------------------------------------------------------- diálogos
    def _dialogo(self, titulo, mensaje, tipo="info", confirmar=False, texto_ok="Continuar"):
        """Diálogo modal con la estética oscura de la aplicación."""
        dialogo = tk.Toplevel(self.root)
        dialogo.title(titulo)
        dialogo.configure(bg=COLOR_BG)
        dialogo.resizable(False, False)
        dialogo.transient(self.root)
        dialogo.grab_set()
        resultado = {"ok": False}

        marco = tk.Frame(dialogo, bg=COLOR_CARD)
        marco.pack(fill="both", expand=True, padx=1, pady=1)

        cabecera = tk.Frame(marco, bg=COLOR_CARD)
        cabecera.pack(fill="x", padx=24, pady=(20, 8))
        iconos = {"info": "i", "warning": "!", "error": "×", "success": "✓"}
        colores = {"warning": COLOR_WARNING, "error": COLOR_ERROR, "success": COLOR_ACCENT}
        tk.Label(
            cabecera,
            text=iconos.get(tipo, "i"),
            bg=COLOR_CARD,
            fg=colores.get(tipo, COLOR_ACCENT),
            font=(self.familia, 18, "bold"),
            width=2,
        ).pack(side="left", padx=(0, 10))
        tk.Label(
            cabecera, text=titulo, bg=COLOR_CARD, fg=COLOR_TEXT,
            font=(self.familia, 12, "bold"), anchor="w", justify="left",
            wraplength=400,
        ).pack(side="left")

        tk.Label(
            marco,
            text=mensaje,
            bg=COLOR_CARD,
            fg=COLOR_MUTED,
            font=(self.familia, 10),
            justify="left",
            anchor="w",
            wraplength=420,
        ).pack(fill="x", padx=24, pady=(0, 6))

        botones = tk.Frame(marco, bg=COLOR_CARD)
        botones.pack(fill="x", padx=24, pady=(12, 20))

        def cerrar(ok):
            resultado["ok"] = ok
            dialogo.destroy()

        if confirmar:
            ttk.Button(
                botones, text=texto_ok, style="Accent.TButton",
                command=lambda: cerrar(True),
            ).pack(side="right")
            ttk.Button(
                botones, text="Cancelar", style="Ghost.TButton",
                command=lambda: cerrar(False),
            ).pack(side="right", padx=(0, 8))
            dialogo.bind("<Return>", lambda _e: cerrar(True))
            dialogo.bind("<Escape>", lambda _e: cerrar(False))
        else:
            ttk.Button(
                botones, text="Cerrar", style="Accent.TButton",
                command=lambda: cerrar(True),
            ).pack(side="right")
            dialogo.bind("<Return>", lambda _e: cerrar(True))
            dialogo.bind("<Escape>", lambda _e: cerrar(False))

        dialogo.update_idletasks()
        ancho = max(440, dialogo.winfo_reqwidth())
        alto = dialogo.winfo_reqheight()
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - ancho) // 2)
        y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - alto) // 2)
        dialogo.geometry(f"{ancho}x{alto}+{x}+{y}")
        dialogo.focus_set()
        dialogo.wait_window()
        return resultado["ok"]

    # ---------------------------------------------------------------- datos
    def refrescar_unidades(self):
        try:
            detectadas = obtener_unidades_con_nombre()
        except Exception:
            detectadas = []
        self.unidades = {
            texto: (punto, dispositivo) for texto, punto, dispositivo in detectadas
        }
        valores = list(self.unidades)
        self.combo_unidades["values"] = valores
        if valores:
            self.combo_unidades.current(0)
            if len(valores) == 1:
                texto = "1 unidad extraíble detectada"
            else:
                texto = f"{len(valores)} unidades extraíbles detectadas"
            self.lbl_unidades.config(text=texto, fg=COLOR_MUTED)
        else:
            self.combo_unidades.set("")
            self.lbl_unidades.config(
                text="No se detectaron unidades extraíbles. Conecta un USB y pulsa ↻.",
                fg=COLOR_WARNING,
            )

    # --------------------------------------------------------------- proceso
    def ejecutar_proceso(self):
        if self.procesando:
            return

        seleccion = self.combo_unidades.get()
        current_url = self.entry_url.get().strip()
        current_folder = self.entry_carpeta.get().strip()

        if not self.unidades:
            self._dialogo(
                "Sin unidades",
                "No se ha detectado ninguna unidad extraíble.\n\n"
                "Conecta el disco USB y pulsa el botón ↻ para actualizar la lista.",
                "warning",
            )
            return
        if not seleccion:
            self._dialogo("Error", "Por favor, selecciona una unidad de disco.", "error")
            return

        if self.modo_origen == "release":
            if not current_url:
                self._dialogo("Error", "La URL de descarga no puede estar vacía.", "error")
                return
        else:
            if not current_folder or not os.path.isdir(current_folder):
                self._dialogo("Error", "Selecciona una carpeta local válida.", "error")
                return
            try:
                if not any(True for _ in os.scandir(current_folder)):
                    self._dialogo("Error", "La carpeta seleccionada está vacía.", "error")
                    return
            except OSError as e:
                self._dialogo("Error", f"No se pudo leer la carpeta:\n{e}", "error")
                return

        punto_montaje, dispositivo = self.unidades[seleccion]
        target_drive = punto_montaje or dispositivo

        if self.modo_origen == "local":
            try:
                if self._carpeta_en_unidad(current_folder, target_drive):
                    self._dialogo(
                        "Error",
                        "La carpeta de origen está dentro de la unidad que se va a formatear.\n"
                        "Elige otra carpeta para no perder los archivos.",
                        "error",
                    )
                    return
            except Exception:
                pass

        origen_texto = current_url if self.modo_origen == "release" else current_folder
        confirmado = self._dialogo(
            "Confirmar formateo",
            "Se formateará la unidad en FAT32 y se borrarán TODOS sus datos:\n\n"
            f"{seleccion}\n\n"
            f"Origen: {origen_texto}\n\nEsta acción no se puede deshacer.",
            "warning",
            confirmar=True,
            texto_ok="Sí, formatear y copiar",
        )
        if not confirmado:
            return

        self._guardar_config_actual()
        self._preparar_interfaz_proceso()
        threading.Thread(
            target=self._trabajo,
            args=(self.modo_origen, current_url, current_folder, punto_montaje, dispositivo, target_drive),
            daemon=True,
        ).start()
        self._programar_poll()

    def _preparar_interfaz_proceso(self):
        self.procesando = True
        self._indeterminado = False
        self._paso_actual = 0
        self.btn_ejecutar.config(state="disabled", text="Procesando…")
        self.combo_unidades.config(state="disabled")
        self.btn_refrescar.config(state="disabled")
        self.entry_url.config(state="disabled")
        for indice, etiqueta in enumerate(self.pasos):
            self._pintar_paso(etiqueta, None, indice)
        self.barra.stop()
        self.barra.config(mode="determinate", value=0)
        self.lbl_estado.config(text="Iniciando el proceso…")
        self.lbl_pct.config(text="0 %")
        self.lbl_detalle.config(text="Preparando la descarga…")

    @staticmethod
    def _carpeta_en_unidad(carpeta, target_drive):
        try:
            origen = os.path.realpath(carpeta)
            destino = os.path.realpath(target_drive)
            return origen == destino or origen.startswith(destino + os.sep)
        except Exception:
            return False

    def _reactivar_controles(self):
        self.btn_ejecutar.config(state="normal", text="Formatear y copiar")
        self.combo_unidades.config(state="readonly")
        self.btn_refrescar.config(state="normal")
        self.entry_url.config(state="normal")

    def descargar_archivo_directo(self, zip_url, extract_to, al_progresar=None, al_extraer=None):
        req = urllib.request.Request(zip_url, headers={"User-Agent": "Mozilla/5.0"})
        zip_path = os.path.join(extract_to, "hats_direct.zip")
        try:
            with urllib.request.urlopen(req, timeout=60) as response, open(zip_path, "wb") as out_file:
                total = int(response.headers.get("Content-Length") or 0)
                leidos = 0
                inicio = time.time()
                while True:
                    bloque = response.read(65536)
                    if not bloque:
                        break
                    out_file.write(bloque)
                    leidos += len(bloque)
                    if al_progresar is not None:
                        transcurrido = max(time.time() - inicio, 0.001)
                        al_progresar(leidos, total, leidos / transcurrido)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                miembros = zip_ref.infolist()
                total_miembros = max(len(miembros), 1)
                for indice, miembro in enumerate(miembros, 1):
                    zip_ref.extract(miembro, extract_to)
                    if al_extraer is not None:
                        al_extraer(indice, total_miembros)

            os.remove(zip_path)

            extracted_items = os.listdir(extract_to)
            if len(extracted_items) == 1:
                inner_dir = os.path.join(extract_to, extracted_items[0])
                if os.path.isdir(inner_dir):
                    return inner_dir
            return extract_to
        except Exception as e:
            raise Exception(f"Error al descargar el archivo ZIP: {str(e)}")

    def _progreso_descarga(self, hechos, total, velocidad):
        detalle = _tamano_legible(hechos)
        if total:
            self.cola.put(("indeterminado", False))
            detalle += f" de {_tamano_legible(total)}"
            self.cola.put(("global", 45 * min(hechos / total, 1)))
        else:
            self.cola.put(("indeterminado", True))
        if velocidad:
            detalle += f" · {_tamano_legible(velocidad)}/s"
        self.cola.put(("detalle", detalle))

    def _progreso_extraccion(self, indice, total):
        self.cola.put(("indeterminado", False))
        self.cola.put(("global", 45 + 10 * (indice / max(total, 1))))
        self.cola.put(("estado", "Paso 1 de 3 · Descomprimiendo el release"))
        self.cola.put(("detalle", f"Descomprimiendo archivos… ({indice}/{total})"))

    def _progreso_copia(self, hechos, total, archivos):
        fraccion = (hechos / total) if total else 1
        if getattr(self, "_modo_actual", "release") == "local":
            pct = 100 * min(fraccion, 1)
        else:
            pct = 65 + 35 * min(fraccion, 1)
        self.cola.put(("global", pct))
        self.cola.put(
            ("detalle", f"{_tamano_legible(hechos)} de {_tamano_legible(total)} · {archivos} archivo(s)")
        )

    def _trabajo(self, modo, url, carpeta, punto_montaje, dispositivo, target_drive):
        self._modo_actual = modo
        temp_dir = tempfile.mkdtemp()
        try:
            if modo == "release":
                self.cola.put(("paso", (0, "Paso 1 de 3 · Descargando el release")))
                self.cola.put(("global", 0))
                repo_source_path = self.descargar_archivo_directo(
                    url,
                    temp_dir,
                    al_progresar=self._progreso_descarga,
                    al_extraer=self._progreso_extraccion,
                )
            else:
                repo_source_path = carpeta

            if modo == "release":
                self.cola.put(("paso", (1, "Paso 2 de 3 · Formateando la unidad")))
                self.cola.put(("global", 55))
            else:
                self.cola.put(("paso", (0, "Paso 1 de 2 · Formateando la unidad")))
                self.cola.put(("global", 0))
            self.cola.put(("indeterminado", True))
            self.cola.put(("detalle", f"Formateando {dispositivo or target_drive} a FAT32…"))

            if sys.platform == "win32":
                drive_letter_clean = target_drive.replace(":", "")
                cmd = f"powershell -Command \"Format-Volume -DriveLetter {drive_letter_clean} -FileSystem FAT32 -NewFileSystemLabel 'HATS_DISK' -Confirm:$false -Force\""
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"Error al formatear mediante PowerShell: {result.stderr}")
            else:
                target_drive = formatear_linux(punto_montaje, dispositivo)

            self.cola.put(("indeterminado", False))
            if modo == "release":
                self.cola.put(("global", 65))
            else:
                self.cola.put(("global", 0))

            if modo == "release":
                self.cola.put(("paso", (2, "Paso 3 de 3 · Copiando archivos")))
            else:
                self.cola.put(("paso", (1, "Paso 2 de 2 · Copiando archivos")))
            destination_path = f"{target_drive}\\" if sys.platform == "win32" else target_drive
            copiar_con_progreso(
                repo_source_path,
                destination_path,
                al_progresar=self._progreso_copia,
            )

            self.cola.put(("global", 100))
            self.cola.put(("fin", None))
        except Exception as e:
            self.cola.put(("indeterminado", False))
            self.cola.put(("error", str(e)))
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------- eventos
    def _programar_poll(self):
        if self._after_id is not None:
            try:
                self.root.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.root.after(80, self._poll_cola)

    def _poll_cola(self):
        self._after_id = None
        try:
            while True:
                tipo, dato = self.cola.get_nowait()
                self._aplicar_evento(tipo, dato)
                if not self.procesando:
                    break
        except queue.Empty:
            pass
        if self.procesando:
            self._after_id = self.root.after(80, self._poll_cola)

    def _aplicar_evento(self, tipo, dato):
        if tipo == "paso":
            indice, texto = dato
            self._paso_actual = indice
            for i, etiqueta in enumerate(self.pasos):
                if i < indice:
                    self._pintar_paso(etiqueta, "hecho", i)
                elif i == indice:
                    self._pintar_paso(etiqueta, "activo", i)
                else:
                    self._pintar_paso(etiqueta, None, i)
            self._indeterminado = False
            self.barra.stop()
            self.barra.config(mode="determinate")
            self.lbl_estado.config(text=texto)
        elif tipo == "global":
            self.lbl_pct.config(text=f"{int(round(dato))} %")
            if not self._indeterminado:
                self.barra.config(value=dato)
        elif tipo == "detalle":
            self.lbl_detalle.config(text=dato)
        elif tipo == "estado":
            self.lbl_estado.config(text=dato)
        elif tipo == "indeterminado":
            if dato and not self._indeterminado:
                self._indeterminado = True
                self.barra.config(mode="indeterminate")
                self.barra.start(14)
            elif not dato and self._indeterminado:
                self._indeterminado = False
                self.barra.stop()
                self.barra.config(mode="determinate")
        elif tipo == "fin":
            self._terminar_ok()
        elif tipo == "error":
            self._terminar_error(dato)

    def _terminar_ok(self):
        self.procesando = False
        self._indeterminado = False
        self.barra.stop()
        self.barra.config(mode="determinate", value=100)
        self.lbl_pct.config(text="100 %")
        self.lbl_estado.config(text="¡Listo! HATS está en la unidad")
        self.lbl_detalle.config(
            text="El disco se formateó y los archivos se copiaron correctamente."
        )
        for indice, etiqueta in enumerate(self.pasos):
            self._pintar_paso(etiqueta, "hecho", indice)
        self._reactivar_controles()
        self._dialogo(
            "Proceso completado",
            "El release de HATS se descargó, el disco se formateó a FAT32 y los archivos "
            "se copiaron correctamente.",
            "success",
        )

    def _terminar_error(self, detalle):
        self.procesando = False
        self._indeterminado = False
        self.barra.stop()
        self.barra.config(mode="determinate")
        self.lbl_estado.config(text="El proceso no pudo completarse")
        self.lbl_detalle.config(text="Revisa el detalle del error y vuelve a intentarlo.")
        self._pintar_paso(self.pasos[self._paso_actual], "error", self._paso_actual)
        self._reactivar_controles()
        self._dialogo(
            "Error crítico",
            f"Ocurrió un error durante el proceso:\n\n{detalle}",
            "error",
        )

    def _al_cerrar(self):
        if self.procesando:
            cerrar = self._dialogo(
                "Proceso en curso",
                "Todavía se está descargando o copiando. Si cierras ahora, el proceso se "
                "interrumpirá y la unidad podría quedar incompleta.\n\n¿Cerrar de todos modos?",
                "warning",
                confirmar=True,
                texto_ok="Cerrar de todos modos",
            )
            if not cerrar:
                return
        self.root.destroy()

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    app = AppHatsPersistentFormatter(root)
    root.mainloop()