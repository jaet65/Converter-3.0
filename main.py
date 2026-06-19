import multiprocessing
import sys
import os

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
    app = ConvertidorApp()
    app.mainloop()
