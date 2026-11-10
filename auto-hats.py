import os
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

def cargar_url_persistente():
    """Carga la URL desde el archivo de configuración oculto o devuelve la predeterminada."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("url", DEFAULT_URL)
        except Exception:
            pass
    return DEFAULT_URL

def guardar_url_persistente(url):
    """Guarda la URL actual en el archivo de configuración oculto."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
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
        media_path = "/media" if os.path.exists("/media") else "/Volumes"
        if os.path.exists(media_path):
            for d in os.listdir(media_path):
                full_path = os.path.join(media_path, d)
                unidades.append(f"{full_path} [{d}]")
    return unidades

class AppHatsPersistentFormatter:
    def __init__(self, root):
        self.root = root
        self.root.title("HATS Formatter & Persistent Downloader")
        self.root.geometry("520x360")
        self.root.resizable(False, False)

        try:
            icon_path = resource_path("icon.ico")
            self.root.iconbitmap(icon_path)
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
        target_drive = seleccion.split()[0]

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
                drive_letter_clean = target_drive.replace(":", "")
                cmd = f"powershell -Command \"Format-Volume -DriveLetter {drive_letter_clean} -FileSystem FAT32 -NewFileSystemLabel 'HATS_DISK' -Confirm:$false -Force\""
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"Error al formatear mediante PowerShell: {result.stderr}")
            else:
                cmd = f"mkfs.vfat -F 32 -n HATS_DISK {target_drive}"
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"Error al formatear: {result.stderr}")

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