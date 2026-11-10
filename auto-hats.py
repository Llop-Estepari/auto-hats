import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
import urllib.request
import ctypes
import json
import tkinter as tk
from tkinter import messagebox, ttk

APP_NAME = "auto-hats"
CONFIG_FILE_LEGACY = "config.json"
DEFAULT_URL = "https://github.com/sthetix/HATS/releases/download/HATS-2026-11-09-5bf0df1/HATS-2026-11-09-5bf0df1.zip"


def ruta_config():
    """Devuelve la ruta del archivo de configuración del usuario."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
    carpeta = os.path.join(base, APP_NAME)
    try:
        os.makedirs(carpeta, exist_ok=True)
    except Exception:
        return os.path.join(os.path.expanduser("~"), f".{APP_NAME}.json")
    return os.path.join(carpeta, "config.json")

def resource_path(relative_path):
    """Obtiene la ruta absoluta al recurso compatible con PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def cargar_url_persistente():
    """Carga la URL desde el archivo de configuración o devuelve la predeterminada."""
    for ruta in (ruta_config(), CONFIG_FILE_LEGACY):
        if not os.path.exists(ruta):
            continue
        try:
            with open(ruta, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("url", DEFAULT_URL)
        except Exception:
            pass
    return DEFAULT_URL

def guardar_url_persistente(url):
    """Guarda la URL actual en el archivo de configuración del usuario."""
    try:
        with open(ruta_config(), 'w', encoding='utf-8') as f:
            json.dump({"url": url}, f, indent=4)
    except Exception as e:
        print(f"Error al guardar la configuración: {e}")

def obtener_unidades_con_nombre():
    """Detecta las unidades disponibles y obtiene su etiqueta de volumen."""
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
                if vol_name:
                    unidades.append(f"{drive_letter} [{vol_name}]")
                else:
                    unidades.append(drive_letter)
            bitmask >>= 1
    else:
        usuario = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
        bases = []
        if usuario:
            bases.append(f"/run/media/{usuario}")
        bases.extend(["/media", "/mnt", "/Volumes"])
        nombres_usuario = []
        for base in bases:
            if not os.path.isdir(base):
                continue
            for d in sorted(os.listdir(base)):
                full_path = os.path.join(base, d)
                if full_path in nombres_usuario:
                    continue
                if not os.path.isdir(full_path):
                    continue
                nombres_usuario.append(full_path)
                etiqueta = d
                if base == "/media":
                    sub = os.path.join(base, d)
                    subdirs = [x for x in os.listdir(sub) if os.path.isdir(os.path.join(sub, x))]
                    if len(subdirs) == 1:
                        etiqueta = subdirs[0]
                        full_path = os.path.join(sub, subdirs[0])
                        nombres_usuario.append(full_path)
                unidades.append(f"{full_path} [{etiqueta}]")
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


def formatear_linux(punto_montaje):
    """Formatea la unidad montada en FAT32 y devuelve el punto de montaje resultante."""
    device = resolver_dispositivo_linux(punto_montaje)
    desmontar_linux(device, punto_montaje)

    cmd = ["mkfs.vfat", "-F", "32", "-n", "HATS_DISK", device]
    if shutil.which("mkfs.vfat") is None:
        raise Exception(
            "Falta 'mkfs.vfat'. Instálalo con:\n\n"
            "    sudo pacman -S dosfstools\n\n"
            "También necesitas 'udisks2' y 'polkit' para montar y desmontar sin sudo."
        )

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        res = _ejecutar(["pkexec"] + cmd)
        if res is None:
            raise Exception(f"No se pudo formatear {device}: hace falta 'pkexec' (paquete polkit) o permisos de root.")
        if res.returncode != 0:
            raise Exception(f"Error al formatear {device}:\n{(res.stderr or res.stdout).strip()}")

    nuevo_punto = punto_montaje
    res = _ejecutar(["udisksctl", "mount", "-b", device])
    if res is not None and res.returncode == 0:
        coincidencia = re.search(r"\bat (.+?)\.?\s*$", res.stdout.strip())
        if coincidencia:
            nuevo_punto = coincidencia.group(1).rstrip(".")
    else:
        res = _ejecutar(["pkexec", "mount", device, punto_montaje])
        if res is None or res.returncode != 0:
            detalle = (res.stderr or res.stdout).strip() if res is not None else "pkexec no está instalado"
            raise Exception(
                f"El disco se formateó pero no se pudo volver a montar {device}:\n{detalle}"
            )
    return nuevo_punto


class AppHatsPersistentFormatter:
    def __init__(self, root):
        self.root = root
        self.root.title("HATS Formatter & Persistent Downloader")
        self.root.geometry("520x360")
        self.root.resizable(False, False)

        try:
            if sys.platform == "win32":
                self.root.iconbitmap(resource_path("icon.ico"))
            else:
                icono = tk.PhotoImage(file=resource_path("auto-hats.png"))
                self.root.iconphoto(True, icono)
                self._icono = icono
        except Exception:
            pass

        tk.Label(root, text="Selecciona la unidad de disco destino:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        
        self.combo_unidades = ttk.Combobox(root, values=obtener_unidades_con_nombre(), state="readonly", width=55)
        self.combo_unidades.pack(padx=20, pady=5)
        if self.combo_unidades['values']:
            self.combo_unidades.current(0)

        tk.Label(root, text="URL del archivo ZIP del Release:", font=("Arial", 10, "bold")).pack(anchor="w", padx=20, pady=(15, 5))
        
        self.entry_url = tk.Entry(root, width=58)
        self.entry_url.pack(padx=20, pady=5)
        self.entry_url.insert(0, cargar_url_persistente())

        self.btn_ejecutar = tk.Button(root, text="Guardar URL, Formatear a FAT32 y Copiar", bg="#d9534f", fg="white", font=("Arial", 10, "bold"), command=self.ejecutar_proceso)
        self.btn_ejecutar.pack(padx=20, pady=25, fill="x")

    def descargar_archivo_directo(self, zip_url, extract_to):
        req = urllib.request.Request(zip_url, headers={'User-Agent': 'Mozilla/5.0'})
        
        try:
            zip_path = os.path.join(tempfile.gettempdir(), "hats_direct.zip")
            with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
                shutil.copyfileobj(response, out_file)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
            
            os.remove(zip_path)
            
            extracted_items = os.listdir(extract_to)
            if len(extracted_items) == 1:
                inner_dir = os.path.join(extract_to, extracted_items[0])
                if os.path.isdir(inner_dir):
                    return inner_dir
            return extract_to
        except Exception as e:
            raise Exception(f"Error al descargar el archivo ZIP: {str(e)}")

    def ejecutar_proceso(self):
        seleccion = self.combo_unidades.get()
        current_url = self.entry_url.get().strip()

        if not seleccion:
            messagebox.showerror("Error", "Por favor selecciona una unidad de disco.")
            return

        if not current_url:
            messagebox.showerror("Error", "La URL de descarga no puede estar vacía.")
            return

        guardar_url_persistente(current_url)
        target_drive = seleccion.rsplit(" [", 1)[0] if " [" in seleccion else seleccion

        confirm = messagebox.askyesno(
            "ADVERTENCIA CRÍTICA", 
            f"Se formateará la unidad {seleccion} en FAT32 y se borrarán TODOS sus datos.\n\n¿Deseas continuar?"
        )
        
        if not confirm:
            return

        self.btn_ejecutar.config(state="disabled", text="Procesando...")
        self.root.update()

        temp_dir = tempfile.mkdtemp()

        try:
            self.btn_ejecutar.config(text="Descargando archivo ZIP...")
            self.root.update()
            repo_source_path = self.descargar_archivo_directo(current_url, temp_dir)

            self.btn_ejecutar.config(text=f"Formateando {target_drive} a FAT32...")
            self.root.update()
            
            if sys.platform == "win32":
                cmd = f"format {target_drive} /FS:FAT32 /Q /V:HATS_DISK /Y"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"Error al formatear: {result.stderr}")
            else:
                target_drive = formatear_linux(target_drive)

            self.btn_ejecutar.config(text="Copiando archivos al disco...")
            self.root.update()
            
            destination_path = f"{target_drive}\\" if sys.platform == "win32" else target_drive
            
            for item in os.listdir(repo_source_path):
                s = os.path.join(repo_source_path, item)
                d = os.path.join(destination_path, item)
                
                if os.path.isdir(s):
                    shutil.copytree(s, d, dirs_exist_ok=True)
                else:
                    shutil.copy2(s, d)

            messagebox.showinfo("Éxito", "El archivo de HATS se descargó, el disco se formateó a FAT32 y los archivos se copiaron correctamente.")
        
        except Exception as e:
            messagebox.showerror("Error crítico", f"Ocurrió un error durante el proceso:\n{str(e)}")
        
        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            self.btn_ejecutar.config(state="normal", text="Guardar URL, Formatear a FAT32 y Copiar")

if __name__ == "__main__":
    root = tk.Tk()
    app = AppHatsPersistentFormatter(root)
    root.mainloop()