# Main entry point for the application
import multiprocessing
import sys
import os

def set_taskbar_icon():
    """Establece el ícono de la barra de tareas en Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = 'TrackSIMTools.1.0' # Identificador arbitrario
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"No se pudo establecer el AppUserModelID: {e}")

# Ensure the script's directory is in sys.path for local module imports
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)
from gui import ConvertidorApp
import customtkinter as ctk

# --- APARIENCIA INICIAL ---
ctk.set_appearance_mode("System")  # "Light", "Dark", "System"
ctk.set_default_color_theme("blue") # "blue", "green", "dark-blue"

if __name__ == "__main__":
    multiprocessing.freeze_support()
    set_taskbar_icon()
    app = ConvertidorApp()
    app.mainloop()
