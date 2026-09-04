import os
import sys
import threading
import tkinter as tk

from update import (
    aplicar_actualizacion,
    descargar_y_preparar,
    instalar_actualizacion,
    verificar_actualizacion_silent,
)


SPLASH_WIDTH = 480
SPLASH_HEIGHT = 300


def crear_splash():
    splash = tk.Tk()
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)
    splash.configure(bg="#0f2740")
    screen_width = splash.winfo_screenwidth()
    screen_height = splash.winfo_screenheight()
    position_x = (screen_width - SPLASH_WIDTH) // 2
    position_y = (screen_height - SPLASH_HEIGHT) // 2
    splash.geometry(f"{SPLASH_WIDTH}x{SPLASH_HEIGHT}+{position_x}+{position_y}")

    canvas = tk.Canvas(
        splash,
        width=SPLASH_WIDTH,
        height=SPLASH_HEIGHT,
        bg="#0f2740",
        highlightthickness=0,
    )
    canvas.pack(fill="both", expand=True)
    canvas.create_rectangle(20, 20, SPLASH_WIDTH - 20, SPLASH_HEIGHT - 20, fill="#1a3a5c", outline="")
    canvas.create_text(
        SPLASH_WIDTH // 2,
        115,
        text="TrackSIM Report Tools",
        fill="#ffffff",
        font=("Segoe UI", 18, "bold"),
    )
    status_item = canvas.create_text(
        SPLASH_WIDTH // 2,
        165,
        text="Buscando la última versión...",
        fill="#a8c4e0",
        font=("Segoe UI", 10),
        width=SPLASH_WIDTH - 70,
    )
    canvas.create_text(
        SPLASH_WIDTH - 35,
        SPLASH_HEIGHT - 35,
        text="Instalador",
        fill="#a8c4e0",
        font=("Segoe UI", 8),
        anchor="se",
    )
    splash.update()

    def actualizar_estado(texto):
        try:
            canvas.itemconfig(status_item, text=texto)
        except tk.TclError:
            pass

    return splash, actualizar_estado


def ejecutar_bootstrap():
    splash, actualizar_estado = crear_splash()

    def informar_estado(mensaje):
        try:
            splash.after(0, actualizar_estado, mensaje)
        except tk.TclError:
            pass

    def descargar_e_instalar():
        latest_version, download_url = verificar_actualizacion_silent(instalacion_inicial=True)
        if not latest_version or not download_url:
            informar_estado("No se encontró el release. Revisa tu conexión.")
            splash.after(5000, splash.destroy)
            return

        zip_path = descargar_y_preparar(download_url, latest_version, informar_estado)
        if not zip_path or not instalar_actualizacion(zip_path, latest_version, informar_estado):
            informar_estado("No se pudo instalar la aplicación.")
            splash.after(5000, splash.destroy)
            return

        informar_estado("Instalación preparada. Iniciando aplicación...")
        splash.after(1200, splash.destroy)

    threading.Thread(target=descargar_e_instalar, daemon=True).start()
    splash.mainloop()


def ejecutar_aplicador(zip_path, latest_version, target_executable):
    splash, actualizar_estado = crear_splash()
    actualizar_estado("Esperando el cierre del bootstrap...")

    def aplicar_en_segundo_plano():
        resultado = aplicar_actualizacion(
            zip_path,
            latest_version,
            os.path.dirname(target_executable),
            target_executable,
            informar_estado,
        )
        if resultado:
            informar_estado("Instalación completada. Cerrando instalador...")
            splash.after(1200, splash.destroy)
        else:
            informar_estado("No se pudo completar la instalación.")
            splash.after(5000, splash.destroy)

    def informar_estado(mensaje):
        splash.after(0, actualizar_estado, mensaje)

    threading.Thread(target=aplicar_en_segundo_plano, daemon=True).start()
    splash.mainloop()


if __name__ == "__main__":
    if "--apply-update" in sys.argv:
        indice = sys.argv.index("--apply-update")
        ejecutar_aplicador(
            sys.argv[indice + 1],
            sys.argv[indice + 2],
            sys.argv[indice + 3],
        )
        sys.exit(0)

    ejecutar_bootstrap()
