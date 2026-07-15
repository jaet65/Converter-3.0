# Main entry point for the application
import multiprocessing
import sys
import os
import tkinter as tk


def set_taskbar_icon():
    """Establece el ícono de la barra de tareas en Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = 'TrackSIMTools.1.0' # Identificador arbitrario
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception as e:
            print(f"No se pudo establecer el AppUserModelID: {e}")


def get_base_path():
    """Devuelve la ruta base correcta tanto en desarrollo como empaquetado."""
    return getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))


def crear_splash():
    """
    Crea y muestra un splash screen personalizado usando Tkinter puro con animaciones.
    Sin transiciones fade, sin bordes/líneas naranjas y sin barra de progreso.
    Devuelve la ventana del splash y una función para cerrarla de forma segura de inmediato.
    """
    base_path = get_base_path()

    splash = tk.Tk()
    splash.overrideredirect(True)          # Sin bordes ni barra de título
    splash.attributes("-topmost", True)    # Siempre al frente
    splash.attributes("-alpha", 1.0)       # Aparece instantáneamente al 100%

    # Paleta de colores de la marca (#1a3a5c → #0f2740)
    SPLASH_W, SPLASH_H = 480, 300
    BG_COLOR   = "#0f2740"
    CARD_COLOR = "#1a3a5c"
    TEXT_COLOR = "#ffffff"
    SUB_COLOR  = "#a8c4e0"

    # Centrar en pantalla
    sw = splash.winfo_screenwidth()
    sh = splash.winfo_screenheight()
    x  = (sw - SPLASH_W) // 2
    y  = (sh - SPLASH_H) // 2
    splash.geometry(f"{SPLASH_W}x{SPLASH_H}+{x}+{y}")
    splash.configure(bg=BG_COLOR)

    # Canvas principal
    canvas = tk.Canvas(splash, width=SPLASH_W, height=SPLASH_H,
                       bg=BG_COLOR, highlightthickness=0)
    canvas.pack(fill="both", expand=True)

    # Rectángulo de tarjeta central (sin bordes)
    pad = 20
    canvas.create_rectangle(pad, pad, SPLASH_W - pad, SPLASH_H - pad,
                             fill=CARD_COLOR, outline="", width=0)

    # Logo de la aplicación
    logo_path = os.path.join(base_path, "logo.png")
    logo_img = None
    if os.path.exists(logo_path):
        try:
            from PIL import Image, ImageTk
            img = Image.open(logo_path).resize((72, 72), Image.LANCZOS)
            logo_img = ImageTk.PhotoImage(img)
            canvas.create_image(SPLASH_W // 2, 110, image=logo_img, anchor="center")
            canvas._logo_img = logo_img  # Evitar que el GC elimine la imagen
        except ImportError:
            # Fallback: círculo azul claro (sin naranja) si PIL no está disponible
            cx, cy, r = SPLASH_W // 2, 110, 34
            canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=SUB_COLOR, outline="")

    # Nombre de la app
    canvas.create_text(SPLASH_W // 2, 175,
                       text="TrackSIM Report Tools",
                       fill=TEXT_COLOR,
                       font=("Segoe UI", 18, "bold"))

    # Subtítulo (dinámico con animación de puntos suspensivos)
    sub_text = canvas.create_text(SPLASH_W // 2, 210,
                                  text="Iniciando aplicación",
                                  fill=SUB_COLOR,
                                  font=("Segoe UI", 10))

    # Versión
    canvas.create_text(SPLASH_W - pad - 15, SPLASH_H - pad - 10,
                       text="v3.0", fill=SUB_COLOR,
                       font=("Segoe UI", 8), anchor="se")

    # Control de estados de las animaciones
    anim_state = {
        "after_id_dots": None,
        "dots_count": 0,
        "closing": False
    }

    # Animación: Puntos suspensivos del subtítulo
    def animar_puntos():
        if anim_state["closing"]:
            return
        s = anim_state
        s["dots_count"] = (s["dots_count"] + 1) % 4
        puntos = "." * s["dots_count"]
        try:
            canvas.itemconfig(sub_text, text=f"Iniciando aplicación...{puntos}")
            s["after_id_dots"] = splash.after(400, animar_puntos)
        except Exception:
            pass

    # Iniciar animación de puntos
    anim_state["after_id_dots"] = splash.after(400, animar_puntos)
    
    splash.update()

    def cerrar_splash():
        """Cancela la animación pendiente de puntos suspensivos y destruye la ventana inmediatamente."""
        anim_state["closing"] = True
        
        if anim_state["after_id_dots"] is not None:
            try:
                splash.after_cancel(anim_state["after_id_dots"])
            except Exception:
                pass

        try:
            splash.destroy()
        except Exception:
            pass

    return splash, cerrar_splash

# Ensure the script's directory is in sys.path for local module imports
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import customtkinter as ctk

# --- APARIENCIA INICIAL ---
ctk.set_appearance_mode("System")  # "Light", "Dark", "System"
ctk.set_default_color_theme("blue") # "blue", "green", "dark-blue"

if __name__ == "__main__":
    multiprocessing.freeze_support()
    set_taskbar_icon()

    # Mostrar splash antes de cargar los módulos pesados
    splash_win, cerrar_splash = crear_splash()

    # Importar módulos pesados (DB, reportes, etc.) mientras el splash está visible
    from gui import ConvertidorApp

    # Cancelar animación y cerrar splash de forma segura antes de la app principal
    cerrar_splash()

    app = ConvertidorApp()
    app.mainloop()
