import sys
import os
import uuid
import datetime
from cx_Freeze import setup, Executable
#python setup.py bdist_msi
# --------------------------------------------
# CONFIGURACIÓN BÁSICA
# --------------------------------------------
base = "Win32GUI" if sys.platform == "win32" else None
python_dir = sys.exec_prefix
script_name = "alarma.py"
app_name = "BerlinTown Notifier"
exe_name = "BerlinTownNotifier.exe"
icon_file = "icono.ico"

# --------------------------------------------
# LISTA COMPLETA DE PAQUETES (optimizada)
# --------------------------------------------
packages = [
    "altgraph", "cabarchive", "cx_Logging", "filelock", "lief",
    "MetaTrader5", "numpy", "packaging", "pandas", "pefile",
    "PIL", "pygame", "pystray", "dateutil", "pytz",
    "six", "striprtf", "tomli", "tzdata"
]

# --------------------------------------------
# ARCHIVOS ADICIONALES A INCLUIR (versión robusta)
# --------------------------------------------
include_files = [icon_file]

# Función para encontrar archivos de pywin32
def find_pywin32_files():
    try:
        import win32api
        pywin32_path = os.path.dirname(win32api.__file__)
        
        # Archivos esenciales de pywin32
        dll_files = ["pywintypes.dll", "pythoncom.dll"]
        
        for dll in dll_files:
            dll_path = os.path.join(pywin32_path, dll)
            if os.path.exists(dll_path):
                include_files.append((dll_path, dll))
            else:
                print(f"Advertencia: No se encontró {dll} en {pywin32_path}")
                
    except ImportError:
        print("Advertencia: pywin32 no está instalado correctamente")

# Función para encontrar TCL/TK
def find_tcl_tk():
    python_base = os.path.dirname(os.path.dirname(sys.executable))
    for dir_name in ["tcl", "tk"]:
        path = os.path.join(python_base, dir_name)
        if os.path.exists(path):
            include_files.append((path, dir_name))
        else:
            print(f"Advertencia: No se encontró {dir_name} en {path}")

# Función para encontrar python3.dll
def find_python_dll():
    search_paths = [
        os.path.join(os.path.dirname(sys.executable), "python3.dll"),
        os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "python3.dll"),
        os.path.join(os.path.dirname(os.path.dirname(sys.executable)), "DLLs", "python3.dll"),
        r"C:\Windows\System32\python3.dll"
    ]
    
    for path in search_paths:
        if os.path.exists(path):
            include_files.append((path, os.path.basename(path)))
            return
    
    print("Advertencia: No se encontró python3.dll")

# Buscar todas las dependencias
find_pywin32_files()
find_tcl_tk()
find_python_dll()

# --------------------------------------------
# OPCIONES DE COMPILACIÓN (corregidas)
# --------------------------------------------
build_options = {
    "packages": packages,
    "include_files": include_files,
    "excludes": [
        "test", "unittest", "tkinter.test", 
        "setuptools", "pip", "wheel"
    ],
    "optimize": 2,
    "include_msvcr": True,
    "silent": True
}

# --------------------------------------------
# OPCIONES DEL INSTALADOR MSI
# --------------------------------------------
msi_options = {
    "upgrade_code": "{" + str(uuid.uuid4()) + "}",
    "add_to_path": False,
    "initial_target_dir": rf"[ProgramFilesFolder]\{app_name}",
    "install_icon": icon_file,
    "data": {
        "Shortcut": [
            (
                "DesktopShortcut", "DesktopFolder", app_name,
                "TARGETDIR", f"[TARGETDIR]{exe_name}",
                None, None, None, None, None, None, "TARGETDIR"
            ),
            (
                "MenuShortcut", "ProgramMenuFolder", app_name,
                "TARGETDIR", f"[TARGETDIR]{exe_name}",
                None, None, None, None, None, None, "TARGETDIR"
            )
        ]
    }
}

# --------------------------------------------
# CONFIGURACIÓN FINAL DEL SETUP
# --------------------------------------------
setup(
    name=app_name,
    version="1.0",
    description="Aplicación de notificaciones para trading en Forex",
    author="Elías Eduardo Liranza Pérez",
    author_email="liranzaelias@gmail.com",
    options={
        "build_exe": build_options,
        "bdist_msi": msi_options
    },
    executables=[
        Executable(
            script_name,
            base=base,
            icon=icon_file,
            target_name=exe_name,
            copyright=f"Copyright © {datetime.datetime.now().year} BERLINTOWN CAPITAL GROUP",
            trademarks="BerlinTown es una marca registrada",
            shortcut_name=app_name,
            shortcut_dir="ProgramMenuFolder"
        )
    ]
)
