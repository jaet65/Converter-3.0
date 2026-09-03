# Main entry point for the application
import multiprocessing
import sys
import os
import tkinter as tk
from tkinter import messagebox
import json
import threading
import time

# Importamos las funciones necesarias desde tu nuevo archivo update.py
from update import (
    verificar_actualizacion_silent,
    actualizacion_descargada,
    descargar_y_preparar,
    instalar_actualizacion,
    aplicar_actualizacion,
)

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

def obtener_version_config():
    """
    Lee el archivo config.json (o config) físico al lado del ejecutable en el disco duro
    y extrae la versión configurada del usuario.
    """
    # Determinamos la carpeta física real del ejecutable
    if getattr(sys, 'frozen', False):
        # Si está empaquetado, busca al lado de TrackSIM_Tools.exe
        base_dir_real = os.path.dirname(sys.executable)
    else:
        # Si está en modo de desarrollo, usa el directorio de main.py
        base_dir_real = os.path.dirname(os.path.abspath(__file__))

    posibles_nombres = ["config.json", "config"]
    for nombre in posibles_nombres:
        config_path = os.path.join(base_dir_real, nombre)
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return f"v{data.get('version', '3.0')}"
            except Exception as e:
                print(f"No se pudo leer el archivo de configuración: {e}")
                break
    return "v3.0"  # Fallback si no se encuentra o hay error


def crear_splash():
    """
    Crea y muestra un splash screen personalizado usando Tkinter puro con animaciones.
    Sin transiciones fade, sin bordes/líneas naranjas y sin barra de progreso.
    Devuelve la ventana del splash y una función para cerrarla de forma segura de inmediato.
    """
    base_path = get_base_path()
    version_app = obtener_version_config()  # Obtiene la versión dinámica del config

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
                                  text="Iniciando aplicación...",
                                  fill=SUB_COLOR,
                                  font=("Segoe UI", 10))

    # Versión dinámica del config.json
    canvas.create_text(SPLASH_W - pad - 15, SPLASH_H - pad - 10,
                       text=version_app, fill=SUB_COLOR,
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
            canvas.itemconfig(sub_text, text=f"Iniciando aplicación{puntos}")
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

# --- LÓGICA DE ACTUALIZACIÓN EN LA APP PRINCIPAL ---
def procesar_actualizacion(app):
    """Verifica si hay actualización disponible y abre el diálogo interactivo."""
    latest_version, download_url = verificar_actualizacion_silent()
    
    if latest_version and download_url:
        app.set_update_status(f"Actualización disponible: v{latest_version}")
        if actualizacion_descargada(latest_version):
            app.set_update_status(f"Actualización v{latest_version} ya descargada")
            descargar_actualizacion(app, download_url, latest_version)
            return

        respuesta = messagebox.askyesno(
            title="Actualización Disponible",
            message=f"Se ha detectado una nueva versión de la aplicación: v{latest_version}\n\n"
                    f"¿Deseas descargarla ahora en segundo plano?"
        )
        if respuesta:
            descargar_actualizacion(app, download_url, latest_version)
        else:
            app.set_update_status(f"Actualización v{latest_version} pendiente")
            app.show_update_button(lambda: descargar_actualizacion(app, download_url, latest_version), text="Descargar actualización")

def descargar_actualizacion(app, download_url, latest_version):
    app.hide_update_button()

    def informar_estado(message):
        app.after(0, app.set_update_status, message)

    def descargar_en_segundo_plano():
        zip_path = descargar_y_preparar(download_url, latest_version, informar_estado)
        if zip_path:
            app.after(0, lambda: confirmar_instalacion(app, zip_path, latest_version))
        else:
            app.after(0, lambda: app.show_update_button(
                lambda: descargar_actualizacion(app, download_url, latest_version), text="Reintentar descarga"))

    threading.Thread(target=descargar_en_segundo_plano, daemon=True).start()

def confirmar_instalacion(app, zip_path, latest_version):
    app.set_update_status(f"Actualización v{latest_version} descargada")
    respuesta = messagebox.askyesno(
        title="Actualización lista",
        message=f"La actualización v{latest_version} está lista para instalar.\n\n"
                "¿Deseas instalarla ahora?"
    )
    if respuesta:
        app.set_update_status("Iniciando instalación. Reiniciando la aplicación...")
        if instalar_actualizacion(zip_path, latest_version):
            app.after(1000, app.destroy)
    else:
        app.set_update_status(f"Actualización v{latest_version} lista para instalar")
        app.show_update_button(
            lambda: instalar_posteriormente(app, zip_path, latest_version),
            text="Instalar actualización",
        )

def instalar_posteriormente(app, zip_path, latest_version):
    app.hide_update_button()
    app.set_update_status("Iniciando instalación. Reiniciando la aplicación...")
    if instalar_actualizacion(zip_path, latest_version):
        app.after(1000, app.destroy)
    else:
        app.set_update_status("No se pudo iniciar la instalación")

# Ensure the script's directory is in sys.path for local module imports
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import customtkinter as ctk

def ejecutar_instalador_grafico(zip_path, latest_version, target_executable):
    instalador = ctk.CTk()
    instalador.withdraw()
    instalador.title("Actualizando TrackSIM Report Tools")
    instalador.geometry("580x420")
    instalador.resizable(False, False)
    instalador.protocol("WM_DELETE_WINDOW", lambda: None)

    ctk.CTkLabel(instalador, text="Instalando actualización", font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(24, 6))
    ctk.CTkLabel(instalador, text=f"Versión v{latest_version}", text_color="gray70").pack()
    estado = ctk.CTkLabel(instalador, text="Esperando el cierre de la aplicación...", wraplength=500)
    estado.pack(padx=24, pady=(18, 8))
    etapa = ctk.CTkLabel(instalador, text="Etapa 1 de 4: Cerrando aplicación", text_color="#4da6ff")
    etapa.pack(padx=24, pady=(0, 10))
    progreso = ctk.CTkProgressBar(instalador, width=500, mode="indeterminate")
    progreso.pack(padx=24, pady=(0, 16))
    progreso.start()
    detalle = ctk.CTkTextbox(instalador, width=500, height=125, state="disabled")
    detalle.pack(padx=24, pady=(0, 14), fill="both", expand=True)
    boton_cerrar = ctk.CTkButton(instalador, text="Cerrar", width=100, state="disabled", command=instalador.destroy)
    boton_cerrar.pack(pady=(0, 18))

    etapas = {
        "Extrayendo": "Etapa 2 de 4: Extrayendo paquete",
        "Instalando": "Etapa 3 de 4: Instalando archivos",
        "Limpiando": "Etapa 4 de 4: Limpiando archivos temporales",
        "Actualización completada": "Proceso finalizado",
        "No se pudo": "Proceso detenido",
    }

    def actualizar_estado_ui(mensaje):
        estado.configure(text=mensaje)
        etapa.configure(text=next((texto for clave, texto in etapas.items() if mensaje.startswith(clave)), etapa.cget("text")))
        detalle.configure(state="normal")
        detalle.insert("end", f"{mensaje}\n")
        detalle.see("end")
        detalle.configure(state="disabled")

    def actualizar_estado(mensaje):
        instalador.after(0, actualizar_estado_ui, mensaje)

    def finalizar(exito):
        progreso.stop()
        if exito:
            estado.configure(text="Actualización completada. Cerrando...")
            instalador.after(1200, instalador.destroy)
        else:
            estado.configure(text="No se pudo completar la actualización.")
            etapa.configure(text="Proceso detenido")
            progreso.configure(mode="determinate")
            progreso.set(0)
            boton_cerrar.configure(state="normal")

    def instalar_en_segundo_plano():
        time.sleep(2.5)
        instalador.after(0, instalador.deiconify)
        actualizar_estado("Aplicación cerrada. Iniciando instalación...")
        resultado = aplicar_actualizacion(zip_path, os.path.dirname(target_executable), target_executable, actualizar_estado)
        instalador.after(0, finalizar, resultado)

    threading.Thread(target=instalar_en_segundo_plano, daemon=True).start()
    instalador.mainloop()

# --- APARIENCIA INICIAL ---
ctk.set_appearance_mode("System")  # "Light", "Dark", "System"
ctk.set_default_color_theme("blue") # "blue", "green", "dark-blue"

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if "--apply-update" in sys.argv:
        indice = sys.argv.index("--apply-update")
        ejecutar_instalador_grafico(sys.argv[indice + 1], sys.argv[indice + 2], sys.argv[indice + 3])
        sys.exit(0)
    set_taskbar_icon()

    # Mostrar splash antes de cargar los módulos pesados
    splash_win, cerrar_splash = crear_splash()

    # Importar módulos pesados (DB, reportes, etc.) mientras el splash está visible
    from gui import ConvertidorApp

    # Cancelar animación y cerrar splash de forma segura antes de la app principal
    cerrar_splash()

    app = ConvertidorApp()

    # Ejecutar la búsqueda de actualizaciones 100ms después de abrir la ventana principal
    # para evitar congelar el inicio visual de la interfaz.
    app.after(100, lambda: procesar_actualizacion(app))

    app.mainloop()
