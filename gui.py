# Creación de la interfaz gráfica para el Convertidor de Reportes TAB Convertir
import os
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import filedialog, BooleanVar
import customtkinter as ctk
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import queue
import threading
import sys
import subprocess
from file_operations import procesar_un_archivo
from app import ImporterApp
from streamdb import DataApp
from config_utils import load_config, save_config
import shutil

class ConvertidorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Dimensiones de la ventana
        window_width = 1000
        window_height = 700

        # Dimensión de la pantalla        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        screen_width = self.winfo_screenwidth()

        # Centro de pantalla
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)-30

        self.title("TrackSIM Report Tools")
        self.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        self.minsize(window_width, window_height)

        self.log_queue = queue.Queue()
        self.log_shown_this_run = False
        self.progress_max_value = 100
        self.app_version = ""
        self.app_build_date = ""

        try:
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(base_path, 'Icon.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception as e:
            print(f"No se pudo cargar el ícono: {e}")

        self.convert_to_pdf = BooleanVar(value=True)
        self.convert_to_excel = BooleanVar(value=True)
        self.limpiar_salida = BooleanVar(value=False)
        
        # Spinner for converter
        self.converter_spinner_activo = False
        self.converter_spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.converter_spinner_idx = 0

        self.cargar_configuracion()
        self.crear_interfaz()
        self.verificar_log_queue()

    def cargar_configuracion(self):
        config = load_config()
        self.ruta_origen = config.get("ruta_origen", "")
        self.ruta_destino = config.get("ruta_destino", "")
        self.convert_to_pdf.set(config.get("convert_to_pdf", True))
        self.convert_to_excel.set(config.get("convert_to_excel", True))
        self.limpiar_salida.set(config.get("limpiar_salida", False))
        self.app_version = config.get("version", "")
        self.app_build_date = config.get("build_date", "")

    def guardar_configuracion(self):
        try:
            save_config({
                "ruta_origen": self.entry_origen.get(),
                "ruta_destino": self.entry_destino.get(),
                "convert_to_pdf": self.convert_to_pdf.get(),
                "convert_to_excel": self.convert_to_excel.get(),
                "limpiar_salida": self.limpiar_salida.get(),
            })
        except OSError as e:
            self.log_queue.put({'type':'log', 'msg':f"Error al guardar la configuración: {e}", 'is_error':True})

    def crear_interfaz(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tab_view = ctk.CTkTabview(self, corner_radius=8)
        self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        
        data_tab = self.tab_view.add("Data")
        config_tab = self.tab_view.add("Convertir")
        importer_tab = self.tab_view.add("Importar")

        # --- Pestaña Data ---
        data_frame = DataApp(master=data_tab)
        data_frame.pack(fill="both", expand=True)

        # --- Pestaña de Configuración ---
        config_tab.grid_columnconfigure(0, weight=1)
        config_tab.grid_rowconfigure(3, weight=1) # Give weight to the log area row

        frame_rutas = ctk.CTkFrame(config_tab, corner_radius=10)
        frame_rutas.grid(row=0, column=0, padx=20, pady=10, sticky="ew")
        frame_rutas.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(frame_rutas, text="Carpeta Origen:").grid(row=0, column=0, padx=15, pady=10, sticky="w")
        self.entry_origen = ctk.CTkEntry(frame_rutas, placeholder_text="Selecciona la carpeta con los reportes...")
        self.entry_origen.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(frame_rutas, text="Seleccionar", width=120, command=lambda: self.seleccionar_ruta('origen')).grid(row=0, column=2, padx=15, pady=10)

        ctk.CTkLabel(frame_rutas, text="Carpeta Destino:").grid(row=1, column=0, padx=15, pady=10, sticky="w")
        self.entry_destino = ctk.CTkEntry(frame_rutas, placeholder_text="Selecciona dónde guardar los archivos convertidos...")
        self.entry_destino.grid(row=1, column=1, padx=10, pady=10, sticky="ew")
        ctk.CTkButton(frame_rutas, text="Seleccionar", width=120, command=lambda: self.seleccionar_ruta('destino')).grid(row=1, column=2, padx=15, pady=10)

        self.entry_origen.insert(0, self.ruta_origen)
        self.entry_destino.insert(0, self.ruta_destino)

        bottom_frame = ctk.CTkFrame(config_tab, fg_color="transparent")
        bottom_frame.grid(row=1, column=0, padx=20, pady=(0, 0), sticky="ew")
        bottom_frame.grid_columnconfigure((0, 1), weight=1)

        frame_opts = ctk.CTkFrame(bottom_frame)
        frame_opts.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        frame_opts.grid_columnconfigure((0, 1), weight=1)
        ctk.CTkLabel(frame_opts, text="Opciones de Procesamiento", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, padx=20, pady=(10, 5), sticky="w")
        ctk.CTkCheckBox(frame_opts, text="Convertir a PDF", variable=self.convert_to_pdf, command=self.guardar_configuracion).grid(row=1, column=0, padx=20, pady=5, sticky="w")
        ctk.CTkCheckBox(frame_opts, text="Convertir a Excel", variable=self.convert_to_excel, command=self.guardar_configuracion).grid(row=2, column=0, padx=20, pady=(5, 10), sticky="w")
        ctk.CTkCheckBox(frame_opts, text="Limpiar carpeta de salida", variable=self.limpiar_salida, command=self.guardar_configuracion).grid(row=1, column=1, rowspan=2, padx=10, pady=5, sticky="w")
        
        progress_frame = ctk.CTkFrame(bottom_frame)
        progress_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        progress_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(progress_frame, text="Progreso", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=20, pady=(10, 5))
        self.lbl_status = ctk.CTkLabel(progress_frame, text="Listo para iniciar.", text_color="gray60")
        self.lbl_status.grid(row=1, column=0, padx=20, pady=(0, 5), sticky="w")
        self.progress = ctk.CTkProgressBar(progress_frame)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")

        btn_frame = ctk.CTkFrame(config_tab, fg_color="transparent")
        btn_frame.grid(row=2, column=0, padx=20, pady=(5, 0), sticky="ew")
        btn_frame.grid_columnconfigure(0, weight=0)
        btn_frame.grid_columnconfigure(1, weight=1)
        btn_frame.grid_columnconfigure(2, weight=0)
        
        self.btn_abrir_destino = ctk.CTkButton(btn_frame, text="Abrir Carpeta de Destino", command=self.abrir_carpeta_destino)
        self.btn_abrir_destino.grid(row=0, column=0, padx=0, pady=5, sticky="w")
        
        self.btn_ejecutar = ctk.CTkButton(btn_frame, text="Iniciar Proceso", command=self.iniciar_procesamiento, height=35, font=ctk.CTkFont(size=14, weight="bold"))
        self.btn_ejecutar.grid(row=0, column=2, padx=0, pady=5)

        # --- Pestaña de Importador ---
        importer_frame = ImporterApp(master=importer_tab, fg_color="transparent")
        importer_frame.pack(fill="both", expand=True)

        # --- Log Area within Config Tab ---
        self.log_area = ctk.CTkTextbox(config_tab, font=("Consolas", 13), state='disabled', corner_radius=8)
        self.log_area.grid(row=3, column=0, columnspan=3, padx=20, pady=(5, 20), sticky="nsew")

        # --- Version Label ---
        if self.app_version:
            version_text = f"Version {self.app_version}"
            if self.app_build_date:
                version_text += f" ({self.app_build_date})"
            version_label = ctk.CTkLabel(self, text=version_text, text_color="gray50", font=ctk.CTkFont(size=10))
            version_label.grid(row=1, column=0, padx=25, pady=(0, 5), sticky="se")

    def seleccionar_ruta(self, tipo):
        current_path = getattr(self, f"entry_{tipo}").get()
        path = filedialog.askdirectory(initialdir=current_path or os.path.expanduser("~"))
        if path:
            entry = getattr(self, f"entry_{tipo}")
            entry.delete(0, "end")
            entry.insert(0, path)
            self.guardar_configuracion()

    def limpiar_log(self):
        self.log_area.configure(state='normal')
        self.log_area.delete("1.0", "end")
        self.log_area.configure(state='disabled')

    def log_message(self, message, is_error=False):
        # El usuario ha solicitado no cambiar automáticamente a la pestaña de Log.
        # La bandera log_shown_this_run ya no es necesaria aquí.

        self.log_area.configure(state='normal')
        # TODO: Agregar tags de color si es necesario (CustomTkinter tags)
        self.log_area.insert("end", message + os.linesep)
        self.log_area.see("end")
        self.log_area.configure(state='disabled')

    def _converter_animar_spinner(self):
        if not self.converter_spinner_activo:
            return
        
        char = self.converter_spinner_chars[self.converter_spinner_idx]
        self.converter_spinner_idx = (self.converter_spinner_idx + 1) % len(self.converter_spinner_chars)
        
        # Get the current status message (like "Procesando 5/12...")
        current_status = self.lbl_status.cget("text")
        
        # Basic parsing to avoid overwriting progress numbers
        if "Procesando" in current_status and "/" in current_status:
            parts = current_status.split(" ")
            self.lbl_status.configure(text=f"Procesando {char} {parts[1]}...")
        else:
             self.lbl_status.configure(text=f"Procesando {char}...")

        self.after(100, self._converter_animar_spinner)

    def verificar_log_queue(self):
        while not self.log_queue.empty():
            rec = self.log_queue.get_nowait()
            if rec['type'] == 'log':
                self.log_message(rec['msg'], rec.get('is_error', False))
            elif rec['type'] == 'status':
                # Update status only if spinner is not active, or if it's the final message
                if not self.converter_spinner_activo or "Finalizado" in rec['msg']:
                    self.lbl_status.configure(text=rec['msg'])
                else:
                    # If spinner is active, embed its progress into the spinner message
                    self.lbl_status.configure(text=rec['msg'])
            elif rec['type'] == 'progress':
                if self.progress_max_value > 0:
                    progress_value = rec['value'] / self.progress_max_value
                    self.progress.set(progress_value)
            elif rec['type'] == 'progress_max':
                self.progress_max_value = rec['value']
            elif rec['type'] == 'done':
                self.converter_spinner_activo = False
                self.btn_ejecutar.configure(state="normal")
        self.after(100, self.verificar_log_queue)

    def abrir_carpeta_destino(self):
        ruta_actual = self.entry_destino.get()
        if not ruta_actual or not os.path.isdir(ruta_actual):
            self.log_queue.put({'type': 'log', 'msg': "La ruta de destino es inválida o está vacía.", 'is_error': True})
            return
        try:
            if sys.platform == "win32":
                os.startfile(ruta_actual)
            else:
                subprocess.run(['open' if sys.platform == "darwin" else 'xdg-open', ruta_actual], check=True)
        except Exception as e:
            self.log_queue.put({'type': 'log', 'msg': f"Error al abrir la carpeta: {e}", 'is_error': True})

    def iniciar_procesamiento(self):
        self.btn_ejecutar.configure(state="disabled")
        self.limpiar_log()
        
        self.ruta_origen = self.entry_origen.get()
        self.ruta_destino = self.entry_destino.get()
        
        if not self.ruta_origen or not os.path.isdir(self.ruta_origen):
            self.log_queue.put({'type':'log','msg':"La ruta de origen es inválida o está vacía.","is_error":True})
            self.btn_ejecutar.configure(state="normal")
            return
            
        self.guardar_configuracion()
        
        self.progress.set(0)
        self.lbl_status.configure(text="Iniciando...")
        self.converter_spinner_activo = True
        self._converter_animar_spinner()
        
        threading.Thread(target=self.procesar_archivos_thread, daemon=True).start()

    def procesar_archivos_thread(self):
        tiempo_inicio = time.time()
        if not (self.convert_to_pdf.get() or self.convert_to_excel.get()):
            self.log_queue.put({'type':'log','msg':"Seleccione al menos un formato de salida.","is_error":True})
            self.log_queue.put({'type':'done','show_open_button':False})
            return
        
        files = []
        try:
            for r,d,f in os.walk(self.ruta_origen):
                for file in f:
                    if file.endswith(".csv") and datetime.fromtimestamp(os.path.getmtime(os.path.join(r,file))) > datetime.now()-timedelta(days=100):
                        files.append(os.path.join(r,file))
        except Exception as e:
            self.log_queue.put({'type':'log','msg':f"Error buscando archivos: {e}","is_error":True})
            self.log_queue.put({'type':'done','show_open_button':False}); return
        
        if not files:
            self.log_queue.put({'type':'log','msg':"No se encontraron archivos .csv recientes en la carpeta de origen.","is_error":False})
            self.log_queue.put({'type':'done','show_open_button':False}); return
        
        if self.limpiar_salida.get():
            for folder in ["Converted", "MinorReport"]:
                folder_path = os.path.join(self.ruta_destino, folder)
                if os.path.exists(folder_path):
                    try:
                        shutil.rmtree(folder_path)
                        self.log_queue.put({'type':'log','msg':f"Carpeta antigua '{folder}' eliminada.","is_error":False})
                    except Exception as e:
                        self.log_queue.put({'type':'log','msg':f"Error al limpiar la carpeta '{folder}': {e}","is_error":True})
        
        os.makedirs(os.path.join(self.ruta_destino, "MinorReport"), exist_ok=True)
        os.makedirs(os.path.join(self.ruta_destino, "Converted"), exist_ok=True)
        
        self.log_queue.put({'type':'progress_max','value':len(files)})
        tasks = [(f, os.path.join(self.ruta_destino,"MinorReport"), os.path.join(self.ruta_destino,"Converted"), self.convert_to_pdf.get(), self.convert_to_excel.get()) for f in files]
        ok, err, workers = 0, 0, min(multiprocessing.cpu_count(), 8)
        
        self.log_queue.put({'type':'log','msg':f"Iniciando conversión de {len(files)} archivos con {workers} procesos...\n"})
        
        with ProcessPoolExecutor(max_workers=workers) as executor:
            f_to_t = {executor.submit(procesar_un_archivo, t): t for t in tasks}
            for i, f in enumerate(as_completed(f_to_t)):
                try:
                    succ, msg = f.result()
                    if succ: ok += 1
                    else: err += 1
                    self.log_queue.put({'type':'log','msg':msg,'is_error':not succ})
                except Exception as exc:
                    err+=1
                    self.log_queue.put({'type':'log','msg':f"ERROR CRÍTICO: {os.path.basename(f_to_t[f][0])} -> {exc}",'is_error':True})
                
                self.log_queue.put({'type':'progress','value':i+1})
                self.log_queue.put({'type':'status','msg':f"Procesando {i+1}/{len(files)}... (Éxito: {ok}, Fallos: {err})"})
        
        resumen = f"\n--- PROCESO FINALIZADO --- \nArchivos exitosos: {ok} \nArchivos fallidos: {err} \nTiempo total: {(time.time()-tiempo_inicio):.2f} segundos."
        self.log_queue.put({'type':'log','msg':resumen,'is_error':err>0})
        self.log_queue.put({'type':'status','msg':f"Finalizado. {ok} OK, {err} fallidos."})
        self.log_queue.put({'type':'done','show_open_button':ok>0})
