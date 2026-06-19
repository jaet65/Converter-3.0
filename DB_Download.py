import psycopg2
import csv
import os
from datetime import date, timedelta
import configparser
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from tkcalendar import DateEntry
import threading
import subprocess # Para abrir la carpeta
import unicodedata
import sys


def get_db_params():
    """Lee la configuración de la base de datos desde config.ini."""
    config = configparser.ConfigParser()
    # Usamos una ruta absoluta para asegurar que PyInstaller encuentre el archivo
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(base_path, 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError("No se encontró el archivo config.ini.")
        
    config.read(config_path)
    if 'database' not in config:
        raise configparser.NoSectionError('database')
        
    return dict(config['database'])

def get_app_version():
    """Lee la versión desde version.txt."""
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        version_path = os.path.join(base_path, 'version.txt')
        with open(version_path, 'r') as f:
            return f.read().strip()
    except Exception:
        return "?.?.?"

def get_build_date():
    """Lee la fecha de build desde build_date.txt."""
    try:
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        date_path = os.path.join(base_path, 'build_date.txt')
        with open(date_path, 'r') as f:
            return f.read().strip()
    except Exception:
        return None

# Carpeta de salida
carpeta_salida = "Sesiones_Lander"
os.makedirs(carpeta_salida, exist_ok=True)

def format_duration(seconds):
    """Convierte segundos en formato HH:MM:SS."""
    if seconds is None:
        return "00:00:00"
    return str(timedelta(seconds=int(seconds)))

def slugify(value):
    """Normaliza un string, convierte a ASCII, quita caracteres no-alfanuméricos y convierte espacios a guiones bajos."""
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
    value = "".join(c for c in value if c.isalnum() or c in (' ', '_')).strip()
    return value.replace(' ', '_')

def load_user_settings():
    """Carga la configuración del usuario desde user_settings.ini."""
    settings_parser = configparser.ConfigParser()
    settings_path = 'user_settings.ini'
    today_str = date.today().isoformat()
    
    defaults = {
        'last_start_date': today_str,
        'last_end_date': today_str,
        'include_anonymous': 'true',
        'clean_folder': 'false'
    }

    if not os.path.exists(settings_path):
        return defaults

    try:
        settings_parser.read(settings_path)
        settings = dict(settings_parser.items('UserSettings'))
        # Validar fechas para evitar errores si el archivo está corrupto
        date.fromisoformat(settings.get('last_start_date', today_str))
        date.fromisoformat(settings.get('last_end_date', today_str))
        return {**defaults, **settings} # Mezcla con defaults por si faltan claves
    except (configparser.Error, ValueError):
        return defaults # Si el archivo es inválido, usa los valores por defecto

def save_user_settings(start_date, end_date, include_anonymous, clean_folder):
    """Guarda la configuración del usuario en user_settings.ini."""
    settings_parser = configparser.ConfigParser()
    settings_parser['UserSettings'] = {
        'last_start_date': start_date.isoformat(),
        'last_end_date': end_date.isoformat(),
        'include_anonymous': str(include_anonymous).lower(),
        'clean_folder': str(clean_folder).lower()
    }
    with open('user_settings.ini', 'w') as configfile:
        settings_parser.write(configfile)

def check_connection_and_count(fecha_inicio, fecha_fin, log_callback, progress_callback, include_anonymous):
    """
    Verifica la conexión con la BD y cuenta los archivos disponibles
    para el rango de fechas sin descargar nada.
    """
    conn = None
    params = [fecha_inicio, fecha_fin]
    progress_callback(0)
    try:
        conn_params = get_db_params()
        log_callback(f"\nConectando a la base de datos en {conn_params['host']}...\n")
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        log_callback("✅ Conexión exitosa a la base de datos.\n")
        
        query_base = """
            SELECT COUNT(*) as total
            FROM sessions 
            WHERE ncicles > 0 AND CAST(dtcreation AS DATE) BETWEEN %s AND %s
        """
        
        if not include_anonymous:
            query_base += " AND LOWER(sstudentname) NOT IN ('anonymous', 'anónimo')"
        
        cursor.execute(query_base, params)
        total_count = cursor.fetchone()[0]
        
        log_callback(f"✅ Se encontraron {total_count} conducciones disponibles para descargar.\n")
        
        # Mostrar también información de primeros y últimos registros
        if total_count > 0:
            query_dates = """
                SELECT MIN(CAST(dtcreation AS DATE)), MAX(CAST(dtcreation AS DATE))
                FROM sessions 
                WHERE ncicles > 0 AND CAST(dtcreation AS DATE) BETWEEN %s AND %s
            """
            if not include_anonymous:
                query_dates += " AND LOWER(sstudentname) NOT IN ('anonymous', 'anónimo')"
            
            cursor.execute(query_dates, params)
            min_date, max_date = cursor.fetchone()
            log_callback(f"📅 Rango de fechas: {min_date} a {max_date}")
        
        progress_callback(100)
        
    except FileNotFoundError as e:
        log_callback(f"\n❌ Error de configuración: {e}")
    except psycopg2.OperationalError as e:
        log_callback(f"\n❌ Error de conexión: {e}\nVerifica la conexión y que el firewall no esté bloqueando el puerto.")
    except configparser.NoSectionError:
        log_callback("\n❌ Error: No se encontró la sección [database] en config.ini.")
    except Exception as e:
        log_callback(f"\n❌ Ocurrió un error inesperado: {e}")
    finally:
        if conn:
            conn.close()
            log_callback("\nConexión a la base de datos cerrada.")

def run_extraction(fecha_inicio, fecha_fin, log_callback, progress_callback, include_anonymous, log_error_callback=None, alert_callback=None):
    """
    Conecta a la BD y extrae los datos de las sesiones para el rango de fechas.
    Usa log_callback para reportar el progreso a la GUI.
    """
    conn = None
    params = [fecha_inicio, fecha_fin]
    progress_callback(0) # Inicia la barra de progreso en 0
    try:
        conn_params = get_db_params()
        log_callback(f"Conectando a la base de datos en {conn_params['host']}...\n")
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()

        query_base = """
            SELECT id, sstudentname, dtcreation, 
                   sinstructorname, (ncicles * dcicleperiod / 1000.0) as duration,
                   idexercise, idaula
            FROM sessions 
            WHERE ncicles > 0 AND CAST(dtcreation AS DATE) BETWEEN %s AND %s
        """

        if not include_anonymous:
            query_base += " AND LOWER(sstudentname) NOT IN ('anonymous', 'anónimo')"
        
        query_sesiones = query_base + " ORDER BY dtcreation DESC;"

        log_callback(f"Buscando sesiones entre {fecha_inicio} y {fecha_fin}...")
        cursor.execute(query_sesiones, params)
        sesiones = cursor.fetchall()

        if not sesiones:
            log_callback("\nNo se encontraron conducciones para las fechas seleccionadas.")
            progress_callback(100) # Completa la barra si no hay nada que hacer
            return
        
        log_callback(f"Descargando {len(sesiones)} conduccion(es)...\n")

        # Bucle principal para procesar sesiones
        for i, sesion in enumerate(sesiones):
            id_sesion, nombre_alumno, fecha, instructor, duracion, id_ejercicio, id_aula = sesion
            nombre_alumno_limpio = slugify(nombre_alumno)
            fecha_str = fecha.strftime("%Y-%m-%d")
            nombre_archivo = f"{carpeta_salida}/Conduccion_ID{id_sesion}_{nombre_alumno_limpio}_{fecha_str}.csv"

            log_callback(f"({i+1}/{len(sesiones)}) Generando: {os.path.basename(nombre_archivo)}")

            # Actualizar la barra de progreso
            progress_value = (i + 1) / len(sesiones) * 100
            progress_callback(progress_value)

            with open(nombre_archivo, mode='w', newline='', encoding='utf-8', errors='replace') as archivo:
                escritor = csv.writer(archivo, delimiter=';')
                
                # --- SECCIÓN DE INFORME DE SESIÓN ---
                escritor.writerow(['Informe de sesión', ''])
                escritor.writerow([])

                # Lección, Unidad y Ejercicio — réplica exacta del query de header.php
                # edunit → Lección, lesson → Unidad, exercise → Ejercicio (igual que el PHP)
                leccion, unidad, ejercicio = "N/A", "N/A", "N/A"
                try:
                    cursor.execute("""
                        SELECT edunits.sname AS edunit, lessons.sname AS lesson, exercises.sname AS exercise
                        FROM sessions,
                             exercises,
                             lessons, idxexerciseslessons,
                             edunits, idxlessonsedunits
                        WHERE sessions.id = %s
                          AND sessions.idexercise = exercises.id
                          AND idxexerciseslessons.idexercise = exercises.id
                          AND idxexerciseslessons.idlesson = lessons.id
                          AND idxlessonsedunits.idlesson = lessons.id
                          AND idxlessonsedunits.idedunit = edunits.id
                    """, (id_sesion,))
                    info_ejercicio = cursor.fetchone()
                    if info_ejercicio:
                        leccion, unidad, ejercicio = info_ejercicio[0], info_ejercicio[1], info_ejercicio[2]
                    else:
                        # Fallback parsing of sessions.sname
                        cursor.execute("SELECT sname FROM sessions WHERE id = %s", (id_sesion,))
                        sname_row = cursor.fetchone()
                        if sname_row and sname_row[0]:
                            parts = [p.strip() for p in sname_row[0].split('\n') if p.strip()]
                            if len(parts) >= 3:
                                leccion, unidad, ejercicio = parts[0], parts[1], parts[2]
                            elif len(parts) == 2:
                                leccion, unidad = parts[0], parts[1]
                            elif len(parts) == 1:
                                leccion = parts[0]
                except Exception:
                    conn.rollback()

                escritor.writerow(['Lección', 'Unidad', 'Ejercicio'])
                escritor.writerow([leccion, unidad, ejercicio])
                escritor.writerow([])
                escritor.writerow(['FECHA', 'CONDUCTOR', 'INSTRUCTOR', 'DURACIÓN']); escritor.writerow([fecha.strftime("%Y-%m-%d"), instructor, nombre_alumno or "-", format_duration(duracion)]); escritor.writerow([])

                # --- Condiciones iniciales ---
                escritor.writerow([])
                escritor.writerow(['Condiciones iniciales', ''])
                escritor.writerow([])
                try:
                    cursor.execute("""
                        SELECT
                            substring(sessionsextradata.sdescription from '[^:]+'),
                            sessionsextradata.svalue
                        FROM idxsessionsextradatasessions, sessionsextradata
                        WHERE idxsessionsextradatasessions.idsessionsextradata = sessionsextradata.id
                          AND idxsessionsextradatasessions.idsession = %s
                          AND idxsessionsextradatasessions.IdAulaSession = %s
                    """, (id_sesion, id_aula))
                    condiciones = cursor.fetchall()
                    if condiciones:
                        for descripcion, valor in condiciones:
                            escritor.writerow([descripcion + ':', valor])
                except Exception:
                    conn.rollback()
                escritor.writerow([])

                # Comentarios, Palabras clave, Notas del instructor
                comentarios = ""
                try:
                    cursor.execute("""
                        SELECT exercises.scomments
                        FROM sessions, exercises
                        WHERE sessions.idexercise = exercises.id
                          AND sessions.id = %s
                    """, (id_sesion,))
                    row_comments = cursor.fetchone()
                    if row_comments and row_comments[0]:
                        comentarios = row_comments[0]
                except Exception:
                    conn.rollback()

                escritor.writerow(['Comentarios', ''])
                escritor.writerow([comentarios])
                escritor.writerow([])

                # --- Palabras clave del ejercicio ---
                palabras_clave = ""
                try:
                    cursor.execute("""
                        SELECT exercises.stags
                        FROM sessions, exercises
                        WHERE sessions.idexercise = exercises.id
                          AND sessions.id = %s
                    """, (id_sesion,))
                    row_tags = cursor.fetchone()
                    if row_tags and row_tags[0]:
                        palabras_clave = row_tags[0]
                except Exception:
                    conn.rollback()

                escritor.writerow(['Palabras clave del ejercicio', ''])
                escritor.writerow([palabras_clave])
                escritor.writerow([])

                # --- Notas del instructor ---
                notas_instructor = ""
                try:
                    cursor.execute("""
                        SELECT sessions.sinstructornotes
                        FROM sessions
                        WHERE sessions.id = %s
                    """, (id_sesion,))
                    row_notes = cursor.fetchone()
                    if row_notes and row_notes[0]:
                        notas_instructor = row_notes[0]
                except Exception:
                    conn.rollback()

                escritor.writerow(['Notas del instructor', ''])
                escritor.writerow([notas_instructor])
                escritor.writerow([])

                # --- Marcas ---
                escritor.writerow([])
                escritor.writerow(['Marcas', ''])
                escritor.writerow([])
                try:
                    cursor.execute("""
                        SELECT marks.ncicle*sessions.dcicleperiod/1000.0 AS tiempo,
                                marks.stipo,
                                marks.scomment
                        FROM sessions, marks, idxmarkssessions
                        WHERE sessions.id = %s
                          AND sessions.IdAula = %s
                          AND idxmarkssessions.idsession = sessions.id
                          AND idxmarkssessions.idmark = marks.id
                        ORDER BY marks.ncicle ASC
                    """, (id_sesion, id_aula))
                    for tiempo, tipo, comentario in cursor.fetchall():
                        escritor.writerow([format_duration(tiempo), tipo, comentario])
                except Exception:
                    conn.rollback()
                escritor.writerow([])

                # --- Resumen de marcas ---
                escritor.writerow([])
                escritor.writerow(['Resumen de marcas', ''])
                escritor.writerow([])
                try:
                    cursor.execute("""
                        SELECT marks.stipo, marks.scomment, COUNT(marks.id)
                        FROM marks, idxmarkssessions, sessions
                        WHERE idxmarkssessions.idsession = sessions.id
                          AND idxmarkssessions.idmark = marks.id
                          AND sessions.id = %s
                          AND sessions.IdAula = %s
                          AND sessions.ncicles*sessions.dcicleperiod > 0
                        GROUP BY marks.stipo, marks.scomment
                        ORDER BY marks.stipo, COUNT(marks.id) DESC
                    """, (id_sesion, id_aula))
                    resumen_rows = cursor.fetchall()
                    
                    from collections import defaultdict
                    resumen_por_tipo = defaultdict(list)
                    for tipo, comentario, cantidad in resumen_rows:
                        resumen_por_tipo[tipo].append((comentario, cantidad))
                    
                    tipos_ordenados = [
                        ('ERROR', 'Errores'),
                        ('BREAKDOWN', 'Averias'),
                        ('START EVENT', 'Incidencias'),
                        ('MARK', 'Marcas'),
                        ('WEATHER', 'Eventos de clima'),
                        ('ILLUMINATION', 'Eventos de iluminacion'),
                        ('TRAFFIC', 'Eventos de trafico'),
                        ('START COMM', 'Comunicaciones'),
                        ('ENDING', 'Desenlaces'),
                        ('INFO', 'Mensajes de informacion'),
                        ('STUDENT MARK', 'Marcas de alumno'),
                        ('MESSAGE', 'Mensajes'),
                        ('TRAIN_LOAD', 'Evento de carga de tren'),
                        ('TRAFFIC_CONDS', 'Evento de condiciones de trafico'),
                        ('PULSADOR', 'Pulsador')
                    ]
                    
                    tiene_marcas = False
                    for tipo_db, tipo_es in tipos_ordenados:
                        if tipo_db in resumen_por_tipo:
                            tiene_marcas = True
                            escritor.writerow([tipo_es, ''])
                            for comentario, cantidad in resumen_por_tipo[tipo_db]:
                                escritor.writerow([comentario, cantidad])
                            escritor.writerow([])
                    
                    if not tiene_marcas:
                        escritor.writerow(['La sesion no contiene marcas'])
                        escritor.writerow([])
                except Exception:
                    conn.rollback()
                escritor.writerow([])

                # --- Indicadores genéricos ---
                escritor.writerow([])
                escritor.writerow(['Indicadores genéricos', ''])
                escritor.writerow([])
                try:
                    cursor.execute("""
                        SELECT
                            genericindics.sdescription,
                            substring(genericindics.svalue from '[0-9.:]+') AS value,
                            substring(genericindics.svalue from '[^0-9.:].*') AS unit
                        FROM idxgenindicssessions, genericindics
                        WHERE idxgenindicssessions.idgenindics = genericindics.id
                          AND idxgenindicssessions.idsession = %s
                    """, (id_sesion,))
                    for descripcion, valor, unidad in cursor.fetchall():
                        escritor.writerow([descripcion, valor or '', unidad or ''])
                except Exception:
                    conn.rollback()

        log_callback("\n¡Proceso completado! Los archivos han sido guardados.")

    except FileNotFoundError as e:
        log_callback(f"\n❌ Error de configuración: {e}")
    except psycopg2.OperationalError as e:
        log_callback(f"\n❌ Error de conexión: {e}\nVerifica la conexión y que el firewall no esté bloqueando el puerto.")
    except configparser.NoSectionError:
        log_callback("\n❌ Error: No se encontró la sección [database] en config.ini.")
    except Exception as e:
        log_callback(f"\n❌ Ocurrió un error inesperado: {e}")
    finally:
        if conn:
            conn.close()
            log_callback("\nConexión a la base de datos cerrada.")

class App:
    def __init__(self, root):
        # Dimensiones de la ventana
        window_width = 950
        window_height = 680

        # Dimensiones de la pantalla
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()-50

        #Centro de pantalla
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)

        self.root = root
        root.title("Report Downloader")
        
        try:
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
            icon_path = os.path.join(base_path, 'LanderDown.ico')
            root.iconbitmap(icon_path)
        except Exception as e:
            print(f"No se pudo cargar el ícono: {e}")
        
        root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
        root.minsize(window_width, window_height)
        
        # Tema oscuro moderno
        style = ttk.Style(root)
        style.theme_use('clam')
        
        bg_color = "#121212"
        card_color = "#1f2937"
        accent_color = "#38bdf8"
        accent_light = "#0f172a"
        text_color = "#e2e8f0"
        secondary_color = "#94a3b8"
        border_color = "#334155"
        input_bg = "#0f172a"
        button_bg = "#2563eb"
        button_hover = "#1d4ed8"
        secondary_button_bg = "#334155"
        progress_trough = "#334155"
        
        root.configure(bg=bg_color)
        style.configure('App.TFrame', background=bg_color)
        style.configure('Card.TFrame', background=card_color, relief='flat', borderwidth=1)
        style.configure('Card.TLabelframe', background=card_color, foreground=text_color, borderwidth=1, relief='flat')
        style.configure('Card.TLabelframe.Label', background=card_color, foreground=accent_color, font=('Segoe UI', 11, 'bold'))
        style.configure('Header.TLabel', background=bg_color, foreground=accent_color, font=('Segoe UI', 16, 'bold'))
        style.configure('SubHeader.TLabel', background=bg_color, foreground=secondary_color, font=('Segoe UI', 10))
        style.configure('Section.TLabel', background=card_color, foreground=text_color, font=('Segoe UI', 10, 'bold'))
        style.configure('CardLabel.TLabel', background=card_color, foreground=secondary_color, font=('Segoe UI', 10))
        style.configure('Accent.TButton', font=('Segoe UI', 10, 'bold'), foreground='white', background=button_bg, borderwidth=0, padding=10)
        style.configure('Secondary.TButton', font=('Segoe UI', 10), foreground=text_color, background=secondary_button_bg, borderwidth=0, padding=10)
        style.map('Accent.TButton', background=[('active', button_hover), ('pressed', '#1e40af')])
        style.map('Secondary.TButton', background=[('active', '#475569'), ('pressed', '#334155')])
        style.configure('TCheckbutton', background=bg_color, foreground=text_color, font=('Segoe UI', 10))
        style.configure('TProgressbar', troughcolor=progress_trough, background=accent_color, thickness=18)
        style.configure('TLabel', background=bg_color, foreground=text_color, font=('Segoe UI', 10))
        style.configure('TEntry', fieldbackground=input_bg, background=input_bg, foreground=text_color, insertcolor=text_color)
        style.configure('TMenubutton', background=input_bg, foreground=text_color)
        style.configure('Vertical.TScrollbar', background=card_color, troughcolor=card_color, bordercolor=card_color)
        
        # Cargar configuración de usuario
        user_settings = load_user_settings()

        # Encabezado
        header_frame = ttk.Frame(root, style='App.TFrame', padding=(24, 18, 24, 10))
        header_frame.pack(fill=tk.X)
        ttk.Label(header_frame, text="Report Downloader", style='Header.TLabel').pack(anchor='w')
        ttk.Label(header_frame, text="Verifica conexión, selecciona fechas y genera tus descargas en CSV.", style='SubHeader.TLabel').pack(anchor='w', pady=(6, 0))

        # Contenido principal
        main_frame = ttk.Frame(root, style='App.TFrame', padding=(24, 0, 24, 8))
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Barra de estado inferior
        status_bar_frame = ttk.Frame(root, style='App.TFrame', padding=(24, 0, 24, 8))
        status_bar_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_var = tk.StringVar(value='Listo')
        status_label = ttk.Label(status_bar_frame, textvariable=self.status_var, style='SubHeader.TLabel')
        status_label.pack(side=tk.LEFT)

        version = get_app_version()
        build_date = get_build_date()
        version_text = f"v{version} ({build_date})" if build_date else f"v{version}"
        version_label = ttk.Label(status_bar_frame, text=version_text, style='SubHeader.TLabel')
        version_label.pack(side=tk.RIGHT)
        main_frame.columnconfigure(0, weight=0)
        main_frame.columnconfigure(1, weight=1)

        # Panel izquierdo de controles
        left_panel = ttk.Frame(main_frame, style='Card.TFrame', padding=20)
        left_panel.grid(row=0, column=0, sticky='nsw', padx=(0, 12), pady=(0, 5))
        left_panel.columnconfigure(0, weight=1)

        # Panel derecho de log
        right_panel = ttk.Frame(main_frame, style='Card.TFrame', padding=20)
        right_panel.grid(row=0, column=1, sticky='nsew', pady=(0, 5))
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(2, weight=1)

        # Sección de fechas
        dates_box = ttk.LabelFrame(left_panel, text='📅 Fechas', style='Card.TLabelframe', padding=16)
        dates_box.grid(row=0, column=0, sticky='ew', pady=(0, 12))
        dates_box.columnconfigure(0, weight=1)
        dates_box.columnconfigure(1, weight=0)

        ttk.Label(dates_box, text='Fecha de Inicio', style='Section.TLabel').grid(row=0, column=0, sticky='w')
        inicio_frame = ttk.Frame(dates_box, style='Card.TFrame')
        inicio_frame.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(6, 10))
        self.fecha_inicio_entry = DateEntry(inicio_frame, width=16, background=accent_color, foreground='white', borderwidth=2, date_pattern='y-mm-dd', todaybackground='#10b981', todayforeground='white')
        self.fecha_inicio_entry.set_date(user_settings['last_start_date'])
        self.fecha_inicio_entry.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(inicio_frame, text='Hoy', command=self.set_today_start, style='Secondary.TButton', width=8).pack(side=tk.LEFT)

        ttk.Label(dates_box, text='Fecha de Fin', style='Section.TLabel').grid(row=2, column=0, sticky='w')
        fin_frame = ttk.Frame(dates_box, style='Card.TFrame')
        fin_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        self.fecha_fin_entry = DateEntry(fin_frame, width=16, background=accent_color, foreground='white', borderwidth=2, date_pattern='y-mm-dd', todaybackground='#10b981', todayforeground='white')
        self.fecha_fin_entry.set_date(user_settings['last_end_date'])
        self.fecha_fin_entry.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(fin_frame, text='Hoy', command=self.set_today_end, style='Secondary.TButton', width=8).pack(side=tk.LEFT)

        # Sección de opciones
        options_box = ttk.LabelFrame(left_panel, text='⚙️ Opciones', style='Card.TLabelframe', padding=16)
        options_box.grid(row=1, column=0, sticky='ew', pady=(0, 12))
        self.include_anonymous_var = tk.BooleanVar(value=(user_settings['include_anonymous'] == 'true'))
        ttk.Checkbutton(options_box, text='Incluir anónimos', variable=self.include_anonymous_var).grid(row=0, column=0, sticky='w', pady=4)
        self.clean_folder_var = tk.BooleanVar(value=(user_settings['clean_folder'] == 'true'))
        ttk.Checkbutton(options_box, text='Limpiar carpeta antes de extraer', variable=self.clean_folder_var).grid(row=1, column=0, sticky='w', pady=4)

        # Sección de acciones
        actions_box = ttk.LabelFrame(left_panel, text='🎯 Acciones', style='Card.TLabelframe', padding=16)
        actions_box.grid(row=2, column=0, sticky='ew')
        self.check_button = ttk.Button(actions_box, text='Verificar Conexión', command=self.check_connection_thread, style='Accent.TButton')
        self.check_button.pack(fill=tk.X, pady=(0, 10))
        self.start_button = ttk.Button(actions_box, text='Iniciar Extracción', command=self.start_extraction_thread, style='Accent.TButton')
        self.start_button.pack(fill=tk.X, pady=(0, 10))
        self.open_folder_button = ttk.Button(actions_box, text='Abrir Carpeta', command=self.open_download_folder, state=tk.DISABLED, style='Accent.TButton')
        # El botón permanece oculto hasta que haya una extracción completada



        # Panel derecho: log y progreso
        ttk.Label(right_panel, text='📝 Progreso y Registro', style='Section.TLabel').grid(row=0, column=0, sticky='w')
        self.progress_bar = ttk.Progressbar(right_panel, orient='horizontal', mode='determinate')
        self.progress_bar.grid(row=1, column=0, sticky='ew', pady=(10, 18))
        self.log_text = scrolledtext.ScrolledText(right_panel, wrap=tk.WORD, state=tk.DISABLED, font=('Segoe UI', 10), background='#0f172a', foreground=text_color, insertbackground=text_color, relief='flat', borderwidth=0)
        self.log_text.grid(row=2, column=0, sticky='nsew')
        # Configurar tag para mensajes de error en rojo
        self.log_text.tag_configure('error', foreground='#f87171', font=('Segoe UI', 10, 'bold'))
        
        # Ajustar tamaño del logo de la sección derecha
        right_panel.rowconfigure(2, weight=1)

        # Separador estético
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(8, 0))

    def set_today_start(self):
        """Establece la fecha de inicio a hoy."""
        self.fecha_inicio_entry.set_date(date.today())

    def set_today_end(self):
        """Establece la fecha de fin a hoy."""
        self.fecha_fin_entry.set_date(date.today())

    def log(self, message):
        """Añade un mensaje al área de log de forma segura desde cualquier hilo."""
        self.root.after(0, self._log_message, message)

    def _log_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def log_error(self, message):
        """Añade un mensaje de error (rojo) al log de forma segura desde cualquier hilo."""
        self.root.after(0, self._log_error_message, message)

    def _log_error_message(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n", 'error')
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def show_damaged_alert(self, sesiones_danadas):
        """Muestra una ventana de alerta con las sesiones omitidas."""
        lines = [f"  • ID {s[0]} | {s[1]} | {s[2].strftime('%Y-%m-%d') if hasattr(s[2], 'strftime') else s[2]}" for s in sesiones_danadas]
        detail = "\n".join(lines)
        messagebox.showwarning(
            "Sesiones con datos incompletos",
            f"{len(sesiones_danadas)} conduccion(es) fueron omitidas por tener datos de ejercicio/leccion/unidad corruptos o inexistentes en la base de datos:\n\n{detail}\n\nRevisa el LOG para más detalles."
        )

    def update_progress(self, value):
        """Actualiza la barra de progreso de forma segura desde cualquier hilo."""
        self.root.after(0, self._update_progress_bar, value)

    def _update_progress_bar(self, value):
        self.progress_bar['value'] = value

    def open_download_folder(self):
        """Abre la carpeta de descargas en el explorador de archivos del sistema."""
        path = os.path.abspath(carpeta_salida)
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:
            self.log(f"❌ Error al abrir la carpeta: {e}")

    def clean_download_folder(self):
        """Elimina todos los archivos de la carpeta de descargas."""
        path = os.path.abspath(carpeta_salida)
        if not os.path.isdir(path):
            self.log(f"La carpeta '{path}' no existe, no se necesita limpieza.")
            os.makedirs(path, exist_ok=True)
            return True

        self.log(f"Limpiando la carpeta de descargas: {path}...\n")
        file_count = 0
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                    file_count += 1
            except Exception as e:
                self.log(f"❌ No se pudo eliminar {file_path}. Razón: {e}")
        self.log(f"Limpieza completada. Se eliminaron {file_count} archivos.\n")

    def start_extraction_thread(self):
        """Inicia el proceso de extracción en un hilo separado."""
        self.start_button.config(state=tk.DISABLED)
        self.check_button.config(state=tk.DISABLED)
        self.open_folder_button.config(state=tk.DISABLED)
        self.status_var.set('Extrayendo sesiones...')
        self.log_text.config(state=tk.NORMAL)
        # Limpiar log y barra de progreso
        self.progress_bar['value'] = 0
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)

        fecha_inicio = self.fecha_inicio_entry.get_date()
        fecha_fin = self.fecha_fin_entry.get_date()
        include_anonymous = self.include_anonymous_var.get()
        clean_folder = self.clean_folder_var.get()

        # Guardar configuración actual
        save_user_settings(fecha_inicio, fecha_fin, include_anonymous, clean_folder)

        # Limpiar carpeta si la opción está marcada
        if clean_folder:
            if messagebox.askyesno("Confirmar Limpieza", 
                                   f"¿Estás seguro de que deseas eliminar todos los archivos de la carpeta '{carpeta_salida}'? Esta acción no se puede deshacer."):
                self.clean_download_folder()
            else:
                self.log("Limpieza cancelada por el usuario.")
                self.status_var.set('Listo')
                self.start_button.config(state=tk.NORMAL)
                self.check_button.config(state=tk.NORMAL)
                return

        if fecha_inicio > fecha_fin:
            self.log("La fecha de inicio no puede ser posterior a la fecha de fin.")
            self.status_var.set('Error en fechas')
            self.start_button.config(state=tk.NORMAL)
            self.check_button.config(state=tk.NORMAL)
            return

        thread = threading.Thread(target=self.run_extraction_task, args=(fecha_inicio, fecha_fin, include_anonymous), daemon=True)
        thread.daemon = True
        thread.start()

    def run_extraction_task(self, fecha_inicio, fecha_fin, include_anonymous):
        """Tarea que se ejecuta en el hilo para no bloquear la GUI."""
        run_extraction(
            fecha_inicio, fecha_fin,
            self.log, self.update_progress, include_anonymous,
            log_error_callback=self.log_error,
            alert_callback=lambda d: self.root.after(0, self.show_damaged_alert, d)
        )
        self.root.after(0, self.on_extraction_complete)

    def check_connection_thread(self):
        """Inicia la verificación de conexión en un hilo separado."""
        self.check_button.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.status_var.set('Verificando conexión...')
        self.log_text.config(state=tk.NORMAL)
        # Limpiar log y barra de progreso
        self.progress_bar['value'] = 0
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state=tk.DISABLED)

        fecha_inicio = self.fecha_inicio_entry.get_date()
        fecha_fin = self.fecha_fin_entry.get_date()
        include_anonymous = self.include_anonymous_var.get()

        if fecha_inicio > fecha_fin:
            self.log("La fecha de inicio no puede ser posterior a la fecha de fin.")
            self.status_var.set('Error en fechas')
            self.check_button.config(state=tk.NORMAL)
            self.start_button.config(state=tk.NORMAL)
            return

        thread = threading.Thread(target=self.run_check_connection_task, args=(fecha_inicio, fecha_fin, include_anonymous), daemon=True)
        thread.daemon = True
        thread.start()

    def run_check_connection_task(self, fecha_inicio, fecha_fin, include_anonymous):
        """Tarea que se ejecuta en el hilo para verificar conexión."""
        check_connection_and_count(fecha_inicio, fecha_fin, self.log, self.update_progress, include_anonymous)
        self.root.after(0, self.on_check_complete)

    def on_check_complete(self):
        """Se ejecuta cuando la verificación termina para reactivar los botones."""
        self.check_button.config(state=tk.NORMAL)
        self.start_button.config(state=tk.NORMAL)
        self.status_var.set('Verificación completada')

    def on_extraction_complete(self):
        """Se ejecuta cuando la extracción termina para reactivar el botón."""
        self.start_button.config(state=tk.NORMAL)
        self.check_button.config(state=tk.NORMAL)
        if not self.open_folder_button.winfo_ismapped():
            self.open_folder_button.pack(fill=tk.X)
        self.open_folder_button.config(state=tk.NORMAL) # Activar al finalizar
        self.status_var.set('Extracción completa')
def set_taskbar_icon():
    """Establece el ícono de la barra de tareas en Windows."""
    if sys.platform == "win32":
        try:
            import ctypes
            myappid = 'Simumak.ReportDownloader.1.0' # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except (ImportError, AttributeError, ValueError) as e:
            print(f"No se pudo establecer el AppUserModelID: {e}")

if __name__ == "__main__":
    set_taskbar_icon()
    try:
        import pyi_splash # type: ignore
        pyi_splash.update_text("Cargando Report Downloader...")
        pyi_splash.update_text("Inicializando...")

    except (ImportError, RuntimeError):
        pass

    root = tk.Tk()
    app = App(root)
    
    # Cerrar el splash screen
    try:
        if 'pyi_splash' in sys.modules:
            import time
            time.sleep(2)
            pyi_splash.close()
    except RuntimeError:
        pass

    root.mainloop()