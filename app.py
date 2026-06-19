import os
import re
import glob
import threading
import warnings
import datetime
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from openpyxl.utils import get_column_letter

# Avisos inofensivos al leer reportes (.xlsx) con openpyxl
for _patron in (
    r"Print area cannot be set to Defined name:.*",
    r"Unknown extension is not supported.*",
    r"Conditional Formatting extension is not supported.*",
    r"Data Validation extension is not supported.*",
    r"Unable to read chart.*",
):
    warnings.filterwarnings(
        "ignore",
        message=_patron,
        category=UserWarning,
    )
import customtkinter as ctk
from config_utils import load_config, save_config
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# --- Configuración del maestro ---
MAESTRO_NOMBRE_DEFECTO = "Master_Simulador.xlsm"
EXTENSIONES_MAESTRO = (".xlsm", ".xlsx")
HOJAS_SIM = ("Sim1", "Sim2", "Sim3")
COL_INICIO = 5  # Columna E
FILA_NAME = 53  # Name desde E53
FILA_FILENAME = 54  # FileName desde E54
FILA_INICIO_DATOS = 55  # Copia de datos desde E55
UMBRAL_SIMILITUD = 0.55
MAX_COLUMNAS_MAESTRO = 400


def limpiar_acentos(texto):
    if not texto:
        return ""
    texto = str(texto).lower()
    remplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u",
        "ñ": "n", "à": "a", "è": "e", "ì": "i", "ò": "o", "ù": "u"
    }
    for orig, dest in remplazos.items():
        texto = texto.replace(orig, dest)
    return texto


def normalizar_texto(valor):
    if valor is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", limpiar_acentos(valor))


def similitud(a, b):
    na, nb = normalizar_texto(a), normalizar_texto(b)
    if not na or not nb:
        return 0.0
    # Optimización 1: Si uno contiene al otro, cálculo inmediato de similitud
    if na in nb or nb in na:
        return min(len(na), len(nb)) / max(len(na), len(nb))
        
    # Optimización 2: Coincidencia por tokens (Jaccard) muy rápida para nombres
    clean_a = limpiar_acentos(a)
    clean_b = limpiar_acentos(b)
    words_a = set(re.split(r"[^a-z0-9]", clean_a))
    words_b = set(re.split(r"[^a-z0-9]", clean_b))
    words_a = {w for w in words_a if len(w) > 2}
    words_b = {w for w in words_b if len(w) > 2}
    if words_a and words_b:
        interseccion = words_a.intersection(words_b)
        union = words_a.union(words_b)
        jaccard = len(interseccion) / len(union)
        if jaccard >= 0.7:
            return jaccard
            
    # Fallback si las longitudes o diferencias son muy ambiguas
    return SequenceMatcher(None, na, nb).ratio()


def unidad_coincide(texto_referencia, unidad_reporte):
    """Compara B4 del reporte con FileName del maestro (o nombre de archivo)."""
    if not texto_referencia or not unidad_reporte:
        return False
    fn = str(texto_referencia).strip().lower()
    u = str(unidad_reporte).strip().lower()
    if fn.endswith(f"_{u}") or fn.endswith(u) or u in fn:
        return True
    nu, nfn = normalizar_texto(u), normalizar_texto(fn)
    if nu and (nu in nfn or nfn.endswith(nu)):
        return True
    for token in re.split(r"[\s\-_]+", u):
        if len(token) < 4:
            continue
        tok = normalizar_texto(token)
        if tok and tok in nfn:
            return True
    return False


def _file_name_valido(valor):
    if valor is None:
        return False
    if isinstance(valor, (int, float)) and valor == 0:
        return False
    texto = str(valor).strip()
    if not texto or texto == "0":
        return False
    if texto.startswith("="):
        return False
    return True


def leer_mapa_columnas_excel(hoja):
    """FileName en fila 54 (E54…), Name en fila 53."""
    columnas = []
    try:
        rango = hoja.Range(hoja.Cells(FILA_NAME, COL_INICIO), hoja.Cells(FILA_FILENAME, MAX_COLUMNAS_MAESTRO))
        valores = rango.Value  # Retorna una tupla de tuplas: (fila_53_valores, fila_54_valores)
    except Exception:
        valores = None

    if valores and len(valores) >= 2:
        vacias_seguidas = 0
        fila_name_vals = valores[0]
        fila_file_vals = valores[1]
        num_cols = len(fila_name_vals)
        for idx in range(num_cols):
            col = COL_INICIO + idx
            name = fila_name_vals[idx]
            file_name = fila_file_vals[idx]
            
            if not _file_name_valido(file_name):
                vacias_seguidas += 1
                if columnas and vacias_seguidas >= 5:
                    break
                continue
            vacias_seguidas = 0
            columnas.append(
                {
                    "col": col,
                    "name": name,
                    "fileName": str(file_name).strip(),
                }
            )
    else:
        vacias_seguidas = 0
        for col in range(COL_INICIO, MAX_COLUMNAS_MAESTRO + 1):
            file_name = hoja.Cells(FILA_FILENAME, col).Value
            if not _file_name_valido(file_name):
                vacias_seguidas += 1
                if columnas and vacias_seguidas >= 5:
                    break
                continue
            vacias_seguidas = 0
            name = hoja.Cells(FILA_NAME, col).Value
            columnas.append(
                {
                    "col": col,
                    "name": name,
                    "fileName": str(file_name).strip(),
                }
            )
    return columnas


def reporte_corresponde_hoja(unidad_tipo, nombre_hoja, sim_valores):
    u = str(unidad_tipo).lower()
    hoja = str(nombre_hoja).strip().lower()
    mapping_val = sim_valores.get(hoja, "")
    
    if not mapping_val or mapping_val in ("0", "none", "false"):
        if hoja == "sim1":
            return "montaña" in u or "montana" in u
        if hoja == "sim2":
            return "pillones" in u
        if hoja == "sim3":
            return "autopista" in u
        return True

    def simplificar(txt):
        txt = txt.lower()
        txt = (
            txt.replace("á", "a")
            .replace("é", "e")
            .replace("í", "i")
            .replace("ó", "o")
            .replace("ú", "u")
            .replace("ñ", "n")
        )
        return txt

    return simplificar(mapping_val) in simplificar(u)


def _celda(df, fila_excel, col_excel):
    return df.iloc[fila_excel - 1, col_excel - 1]


def _valor_celda(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _etiqueta_celda(val):
    return re.sub(r"\s+", " ", _valor_celda(val)).lower()


def _es_informe_sesion(df):
    if df.empty:
        return False
    titulo = _etiqueta_celda(df.iloc[0, 0])
    return titulo in ("informe de sesión", "informe de sesion")


def _buscar_celda_seccion(df, nombre):
    objetivo = _etiqueta_celda(nombre)
    max_col = min(df.shape[1], 15)
    for i in range(len(df)):
        for j in range(max_col):
            if _etiqueta_celda(df.iloc[i, j]) == objetivo:
                return i, j
    return None, None


def _buscar_seccion_indicadores(df):
    max_col = min(df.shape[1], 15)
    for i in range(len(df)):
        for j in range(max_col):
            et = _etiqueta_celda(df.iloc[i, j])
            if et == "indicadores" or et.startswith("indicadores "):
                return i, j
    return None, None


def _columna_datos_seccion(df, fila_titulo, col_titulo, preferida):
    if preferida < df.shape[1]:
        val = df.iloc[fila_titulo + 2, preferida] if fila_titulo + 2 < len(df) else None
        if not pd.isna(val) and _valor_celda(val) != "":
            return preferida
    for offset in (2, 1, 3):
        col = col_titulo + offset
        if col < df.shape[1] and fila_titulo + 2 < len(df):
            val = df.iloc[fila_titulo + 2, col]
            if not pd.isna(val) and _valor_celda(val) != "":
                return col
    return preferida


def _extraer_columna_datos(df, fila_titulo, col_datos, fila_inicio_offset=2):
    datos = []
    for i in range(fila_titulo + fila_inicio_offset, len(df)):
        val = df.iloc[i, col_datos]
        if pd.isna(val) or _valor_celda(val) == "":
            break
        datos.append(val)
    return datos


def _puntaje_hoja_reporte(df):
    fm, _ = _buscar_celda_seccion(df, "Marcas")
    fi, _ = _buscar_seccion_indicadores(df)
    puntos = (2 if fm is not None else 0) + (2 if fi is not None else 0)
    if _es_informe_sesion(df):
        puntos += 1
    return puntos


def _cargar_hoja_reporte(ruta_reporte):
    xl = pd.ExcelFile(ruta_reporte)
    sheet_names = xl.sheet_names
    
    # Intentar cargar primero hojas con nombres probables (Report o la primera)
    preferidas = [s for s in sheet_names if s.strip().lower() in ("report", "reporte")]
    if not preferidas and sheet_names:
        preferidas.append(sheet_names[0])
        
    for nombre in preferidas:
        df = pd.read_excel(xl, sheet_name=nombre, header=None)
        if _puntaje_hoja_reporte(df) >= 4 or _es_informe_sesion(df):
            return df
            
    # Si no funcionó con las preferidas, cargar el resto como fallback
    for nombre in sheet_names:
        if nombre in preferidas:
            continue
        df = pd.read_excel(xl, sheet_name=nombre, header=None)
        if _puntaje_hoja_reporte(df) >= 4 or _es_informe_sesion(df):
            return df
            
    # Fallback definitivo si nada da puntaje suficiente
    if preferidas:
        return pd.read_excel(xl, sheet_name=preferidas[0], header=None)
    return pd.read_excel(xl, sheet_name=sheet_names[0], header=None)


def leer_metadatos_reporte(ruta_reporte):
    df_raw = _cargar_hoja_reporte(ruta_reporte)
    if _puntaje_hoja_reporte(df_raw) < 4 and not _es_informe_sesion(df_raw):
        raise ValueError("Celda A1 no válida (se esperaba 'Informe de sesión').")

    unidad_tipo = _valor_celda(_celda(df_raw, 4, 2))
    if not unidad_tipo:
        raise ValueError("Celda B4 (Unidad) vacía o no legible.")

    idx_marcas, col_marcas = _buscar_celda_seccion(df_raw, "Marcas")
    idx_indicadores, col_indicadores = _buscar_seccion_indicadores(df_raw)
    if idx_marcas is None or idx_indicadores is None:
        raise ValueError(
            "No se encontraron secciones 'Marcas' o 'Indicadores genéricos'."
        )

    col_datos_marcas = _columna_datos_seccion(
        df_raw, idx_marcas, col_marcas, preferida=2
    )
    col_datos_ind = _columna_datos_seccion(
        df_raw, idx_indicadores, col_indicadores, preferida=1
    )
    datos_marcas = _extraer_columna_datos(df_raw, idx_marcas, col_datos_marcas)
    datos_indicadores = _extraer_columna_datos(
        df_raw, idx_indicadores, col_datos_ind
    )

    return {
        "unidad_tipo": unidad_tipo,
        "datos_marcas": datos_marcas,
        "datos_indicadores": datos_indicadores,
        "nombre_archivo": Path(ruta_reporte).stem,
    }


def unidad_compatible_con_reporte(file_name_maestro, meta):
    unidad = meta["unidad_tipo"]
    return unidad_coincide(file_name_maestro, unidad) or unidad_coincide(
        meta["nombre_archivo"], unidad
    )


def puntuar_emparejamiento(col_info, meta):
    fn = col_info["fileName"]
    if not unidad_compatible_con_reporte(fn, meta):
        return 0.0
    stem = meta["nombre_archivo"]
    return max(
        similitud(stem, fn),
        similitud(stem, fn.rsplit("_", 1)[0] if "_" in fn else fn),
    )


def emparejar_reportes_con_columnas(columnas_maestro, reportes_meta):
    asignaciones = []
    usados = set()
    for col_info in sorted(columnas_maestro, key=lambda c: c["fileName"]):
        mejor_ruta = None
        mejor_meta = None
        mejor_score = UMBRAL_SIMILITUD
        for ruta, meta in reportes_meta:
            if ruta in usados:
                continue
            score = puntuar_emparejamiento(col_info, meta)
            if score > mejor_score:
                mejor_score = score
                mejor_ruta = ruta
                mejor_meta = meta
        if mejor_ruta:
            usados.add(mejor_ruta)
            asignaciones.append((col_info, mejor_ruta, mejor_meta, mejor_score))
    return asignaciones, usados


def _obtener_excel():
    import win32com.client
    
    try:
        excel = win32com.client.GetActiveObject("Excel.Application")
    except Exception:
        excel = win32com.client.Dispatch("Excel.Application")
    # Hide Excel UI during processing
    excel.Visible = False
    excel.DisplayAlerts = False
    excel.ScreenUpdating = False
    return excel


def _abrir_libro_excel(excel, ruta_maestro):
    ruta_abs = str(Path(ruta_maestro).resolve())
    for i in range(1, excel.Workbooks.Count + 1):
        libro = excel.Workbooks(i)
        try:
            if Path(libro.FullName).resolve() == Path(ruta_abs).resolve():
                return libro
        except Exception:
            continue
    return excel.Workbooks.Open(
        ruta_abs,
        UpdateLinks=0,
        ReadOnly=False,
        IgnoreReadOnlyRecommended=True,
    )


def _resolver_hoja_excel(libro, nombre_hoja):
    """Busca una hoja por nombre, de forma robusta."""
    try:
        # Intento directo, que es lo más rápido
        hoja = libro.Worksheets(nombre_hoja)
        return hoja
    except Exception:
        # Fallback: iterar por las hojas si el acceso directo falla
        objetivo = str(nombre_hoja).strip().lower()
        try:
            for i in range(1, libro.Worksheets.Count + 1):
                try:
                    hoja_candidata = libro.Worksheets(i)
                    if str(hoja_candidata.Name).strip().lower() == objetivo:
                        return hoja_candidata
                except Exception:
                    # Si una hoja específica da error, la saltamos
                    continue
        except Exception:
            # Si la colección Worksheets en sí misma da error
            return None
    return None


def _valor_para_excel(valor):
    """Convierte tipos de pandas/Python a variantes que Excel COM acepta."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, datetime.datetime):
        epoch = datetime.datetime(1899, 12, 30)
        delta = valor - epoch
        return delta.days + (
            delta.seconds + delta.microseconds / 1_000_000
        ) / 86400.0
    if isinstance(valor, datetime.time):
        seg = valor.hour * 3600 + valor.minute * 60 + valor.second
        seg += valor.microsecond / 1_000_000
        return seg / 86400.0
    if isinstance(valor, datetime.date):
        epoch = datetime.date(1899, 12, 30)
        return (valor - epoch).days
    if isinstance(valor, pd.Timestamp):
        return _valor_para_excel(valor.to_pydatetime())
    if isinstance(valor, (int, float)):
        return float(valor) if isinstance(valor, float) else int(valor)
    if hasattr(valor, "item"):
        try:
            return _valor_para_excel(valor.item())
        except (ValueError, AttributeError):
            pass
    return str(valor)


def _pegar_columna_valores(hoja, col, fila_inicio, valores):
    if not valores:
        return
    valores_convertidos = [[_valor_para_excel(val)] for val in valores]
    fila_fin = fila_inicio + len(valores) - 1
    try:
        rango = hoja.Range(hoja.Cells(fila_inicio, col), hoja.Cells(fila_fin, col))
        rango.Value = valores_convertidos
    except Exception:
        # Fallback cell-by-cell in case of COM error
        for idx, valor in enumerate(valores):
            hoja.Cells(fila_inicio + idx, col).Value = _valor_para_excel(valor)


def _buscar_celda_por_nombre(hoja, name_value, max_filas=150):
    if not name_value:
        return None, None
    try:
        xl_values = -4163
        xl_whole = 1
        xl_by_rows = 1
        xl_next = 2
        encontrada = hoja.Cells.Find(
            What=name_value,
            LookIn=xl_values,
            LookAt=xl_whole,
            SearchOrder=xl_by_rows,
            SearchDirection=xl_next,
            MatchCase=False,
        )
        if encontrada is not None:
            return encontrada.Row, encontrada.Column
    except Exception:
        pass
    
    # Búsqueda manual ultra rápida en memoria en lugar de celda por celda COM
    try:
        valores_matriz = hoja.Range(hoja.Cells(1, 1), hoja.Cells(150, 120)).Value
        if valores_matriz:
            target = str(name_value).strip().lower()
            for r_idx, fila_vals in enumerate(valores_matriz):
                for c_idx, val in enumerate(fila_vals):
                    if val is not None and str(val).strip().lower() == target:
                        return r_idx + 1, c_idx + 1
    except Exception:
        pass
    return None, None


def _pegar_indicadores(hoja_ind, name_value, valores):
    if not name_value or not valores:
        return
    fila_coincidencia, col_coincidencia = _buscar_celda_por_nombre(hoja_ind, name_value)
    if fila_coincidencia and col_coincidencia:
        fila_destino = max(1, fila_coincidencia - 18)
        _pegar_columna_valores(hoja_ind, col_coincidencia, fila_destino, valores)


def pegar_en_maestro(archivo_maestro, carpeta_reportes, log_callback=None):
    """
    Pega solo valores en el maestro usando Excel (preserva fórmulas).
    No guarda el archivo: lo deja abierto para que el usuario guarde manualmente.
    """
    import pythoncom

    pythoncom.CoInitialize()
    excel = None
    try:
        def log(msg, is_alert=False):
            if log_callback:
                log_callback(msg, is_alert=is_alert)

        archivos = sorted(glob.glob(os.path.join(carpeta_reportes, "*.xlsx")))
        if not archivos:
            raise FileNotFoundError(
                f"No hay archivos .xlsx en '{carpeta_reportes}'."
            )

        log(f"Se encontraron {len(archivos)} reportes en la carpeta.")

        reportes_meta = []
        omitted_reports = [] # Initializing the new list
        for ruta in archivos:
            try:
                meta = leer_metadatos_reporte(ruta)
                reportes_meta.append((ruta, meta))
                log(f"  · {Path(ruta).name} | unidad B4: {meta['unidad_tipo']}")
            except Exception as exc:
                omitted_reports.append((ruta, exc)) # Storing omitted reports

        if not reportes_meta and not omitted_reports: # Modified condition
            raise ValueError("Ningún reporte válido para procesar.")

        excel = _obtener_excel()
        libro = _abrir_libro_excel(excel, archivo_maestro)

        # Obtener valores dinámicos de correspondencia de Sim1, Sim2, Sim3
        hoja_asistencia = _resolver_hoja_excel(libro, "Asistencia")
        sim_valores = {}
        origen_maestro = False
        
        if hoja_asistencia is not None:
            try:
                sim1_val = str(hoja_asistencia.Range("N41").Value or "").strip().lower()
                sim2_val = str(hoja_asistencia.Range("N42").Value or "").strip().lower()
                sim3_val = str(hoja_asistencia.Range("N43").Value or "").strip().lower()

                if sim1_val or sim2_val or sim3_val:
                    sim_valores["sim1"] = sim1_val
                    sim_valores["sim2"] = sim2_val
                    sim_valores["sim3"] = sim3_val
                    origen_maestro = True
                else:
                    raise ValueError("Celdas de configuración de SIM vacías en hoja Asistencia.")
            except Exception as exc:
                log(
                    f"[aviso] No se pudieron leer las celdas N41-N43 de la hoja Asistencia ({exc}). Se usan valores por defecto.",
                    is_alert=True,
                )
                origen_maestro = False
        
        if not origen_maestro:
            sim_valores = {"sim1": "montaña", "sim2": "pillones", "sim3": "autopista"}

        log(f"\nConfiguración de correspondencia de simulaciones:")
        if origen_maestro:
            log("  (Obtenidos del archivo maestro, hoja 'Asistencia', celdas N41-N43)")
        else:
            log(
                "  (Usando valores por defecto. No se encontró 'Asistencia' o las celdas están vacías)",
                is_alert=True,
            )

        sim_alert = not origen_maestro
        log(f"  · Sim1: '{sim_valores.get('sim1', 'N/A')}'", is_alert=sim_alert)
        log(f"  · Sim2: '{sim_valores.get('sim2', 'N/A')}'", is_alert=sim_alert)
        log(f"  · Sim3: '{sim_valores.get('sim3', 'N/A')}'", is_alert=sim_alert)

        usados = set()
        total_copiados = 0
        paso = 0
        total_pasos = len(reportes_meta)

        hoja_ind = _resolver_hoja_excel(libro, "Indicadores")

        for nombre_hoja in HOJAS_SIM:
            hoja_sim = _resolver_hoja_excel(libro, nombre_hoja)
            if hoja_sim is None:
                log(f"[aviso] No existe la hoja '{nombre_hoja}'; se omite.")
                continue

            columnas_maestro = leer_mapa_columnas_excel(hoja_sim)
            if not columnas_maestro:
                log(
                    f"[aviso] {nombre_hoja}: sin FileName en fila {FILA_FILENAME} "
                    f"(desde columna E)."
                )
                continue

            reportes_hoja = [
                (ruta, meta)
                for ruta, meta in reportes_meta
                if ruta not in usados
                and reporte_corresponde_hoja(meta["unidad_tipo"], nombre_hoja, sim_valores)
            ]

            log(f"\n--- {nombre_hoja}: {len(columnas_maestro)} columnas "
                f"(FileName E{FILA_FILENAME}, datos E{FILA_INICIO_DATOS}+) — "
                f"{len(reportes_hoja)} reporte(s) del escenario."
            )

            asignaciones, usados_hoja = emparejar_reportes_con_columnas(
                columnas_maestro, reportes_hoja
            )
            usados.update(usados_hoja)

            for col_info, ruta, meta, score in asignaciones:
                col = col_info["col"]
                letra_col = get_column_letter(col)
                try:
                    _pegar_columna_valores(
                        hoja_sim,
                        col,
                        FILA_INICIO_DATOS,
                        meta["datos_marcas"],
                    )

                    if hoja_ind is not None and col_info["name"]:
                        _pegar_indicadores(
                            hoja_ind,
                            col_info["name"],
                            meta["datos_indicadores"],
                        )
                except OSError as exc:
                    log(
                        f"[error] {Path(ruta).name} -> {letra_col}: {exc}"
                    )
                    usados.discard(ruta)
                    continue

                paso += 1
                total_copiados += 1
                log(
                    f"[{nombre_hoja}] {Path(ruta).name} -> {letra_col} "
                    f"(FileName: {col_info['fileName']}, {score:.0%}, "
                    f"{meta['unidad_tipo']})"

                )
                if log_callback:
                    log_callback(None, paso, total_pasos)

        reportes_no_emparejados = len(reportes_meta) - len(usados)
        if reportes_no_emparejados > 0:
            log(f"\nSe encontraron {reportes_no_emparejados} reportes sin emparejar:")
            for ruta, meta in reportes_meta:
                if ruta in usados:
                    continue
                log(
                    f"  · {Path(ruta).name} (unidad {meta['unidad_tipo']}) — "
                    "no hubo FileName compatible en el maestro."
                )

        if omitted_reports:
            log(f"\nSe encontraron {len(omitted_reports)} reportes omitidos por errores de lectura:")
            for ruta, exc in omitted_reports:
                log(f"  · {Path(ruta).name}: {exc}")

        if total_copiados == 0:
            raise ValueError(
                "No se copió ningún reporte. Revise FileName (fila 54) en Sim1/Sim2/Sim3."
            )
        if excel is not None:
            excel.ScreenUpdating = True
            excel.Visible = True
        try:
            libro.Activate()
            hoja_sim = _resolver_hoja_excel(libro, "Sim1")
            if hoja_sim:
                hoja_sim.Activate()
        except Exception:
            pass

        log("\nDatos pegados en Excel. Revise el maestro y guarde manualmente (Ctrl+S).")
        return total_copiados, len(reportes_meta) - len(usados)
    finally:

        pythoncom.CoUninitialize()


class ImporterApp(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.carpeta_var = tk.StringVar()
        self.maestro_var = tk.StringVar()

        self.spinner_activo = False
        self.spinner_chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.spinner_idx = 0
        self.inicio_tiempo = None
        self.tiempo_estimado_total = 0.0
        self.estado_var = tk.StringVar(value="Listo.")

        # --- Creación de la Interfaz dentro del Frame ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(8, weight=1)

        ctk.CTkLabel(self, text="Carpeta de reportes (reportes_simulacion):").grid(
            row=0, column=0, sticky="w", padx=20, pady=(20, 0))
        ctk.CTkEntry(self, textvariable=self.carpeta_var, width=70).grid(
            row=1, column=0, sticky="ew", pady=(2, 8), padx=20)
        ctk.CTkButton(self, text="Examinar…", command=self._elegir_carpeta).grid(
            row=1, column=1, padx=(0, 20))

        ctk.CTkLabel(self, text="Archivo Master_Simulador (.xlsm):").grid(
            row=2, column=0, sticky="w", padx=20)
        ctk.CTkEntry(self, textvariable=self.maestro_var, width=70).grid(
            row=3, column=0, sticky="ew", pady=(2, 8), padx=20)
        ctk.CTkButton(self, text="Examinar…", command=self._elegir_maestro).grid(
            row=3, column=1, padx=(0, 20))

        self.btn_procesar = ctk.CTkButton(
            self, text="Copiar y abrir maestro", command=self._iniciar_proceso
        )
        self.btn_procesar.grid(row=4, column=0, columnspan=2, pady=(4, 12), padx=20)

        self.progreso = ctk.CTkProgressBar(self)
        self.progreso.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 8), padx=20)
        self.progreso.set(0)

        ctk.CTkLabel(self, textvariable=self.estado_var).grid(
            row=6, column=0, columnspan=2, sticky="w", padx=20)
        
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=8, column=0, columnspan=2, sticky="nsew", pady=(8, 20), padx=20)
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(log_frame, font=("Consolas", 13), state='disabled', corner_radius=8)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.log_text._textbox.tag_configure("alert", foreground="#FF6B6B")

        # Autocompletar rutas
        base = Path(__file__).resolve().parent
        carpeta_def = base / "reportes_simulacion"
        if carpeta_def.is_dir():
            self.carpeta_var.set(str(carpeta_def))
        for nombre in (MAESTRO_NOMBRE_DEFECTO, "Master_Simulador.xlsx"):
            maestro_def = base / nombre
            if maestro_def.is_file():
                self.maestro_var.set(str(maestro_def))
                break
        if not self.maestro_var.get():
            for candidato in base.glob("*.xlsm"):
                if not candidato.name.startswith("~$") and ".bak" not in candidato.name:
                    self.maestro_var.set(str(candidato))
                    break
        
        self.cargar_configuracion_importer()

    def cargar_configuracion_importer(self):
        config = load_config()
        if config.get("importer_folder"):
            self.carpeta_var.set(config["importer_folder"])
        if config.get("importer_master_file"):
            self.maestro_var.set(config["importer_master_file"])

    def guardar_configuracion_importer(self):
        try:
            save_config({
                "importer_folder": self.carpeta_var.get(),
                "importer_master_file": self.maestro_var.get(),
            })
        except OSError as e:
            print(f"Error guardando configuración: {e}")


    def _elegir_carpeta(self):
        ruta = filedialog.askdirectory(title="Carpeta reportes_simulacion")
        if ruta:
            self.carpeta_var.set(ruta)
            self.guardar_configuracion_importer()

    def _elegir_maestro(self):
        ruta = filedialog.askopenfilename(
            title="Master_Simulador",
            filetypes=[
                ("Excel con macros (.xlsm)", "*.xlsm"),
                ("Excel (.xlsx)", "*.xlsx"),
                ("Todos", "*.*"),
            ],
        )
        if ruta:
            self.maestro_var.set(ruta)
            self.guardar_configuracion_importer()

    def _es_linea_alerta(self, mensaje):
        texto = mensaje.strip().lower()
        if "[error]" in texto:
            return True
        if "sin emparejar" in texto:
            return True
        if "no hubo filename compatible" in texto:
            return True
        if "omitidos por errores" in texto:
            return True
        if "valores por defecto" in texto:
            return True
        if texto.startswith("·") or texto.startswith("  ·"):
            if " | unidad" in texto:
                return False
            if re.match(r"[·\s]*sim[123]:", texto):
                return False
            if ": " in texto:
                return True
        return False

    def _log(self, mensaje, is_alert=False):
        self.log_text.configure(state=tk.NORMAL)
        linea = mensaje + "\n"
        if is_alert or self._es_linea_alerta(mensaje):
            self.log_text._textbox.insert(tk.END, linea, "alert")
        else:
            self.log_text.insert(tk.END, linea)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _callback_progreso(self, mensaje, paso=None, total=None, is_alert=False):
        if mensaje is not None:
            self.after(0, lambda m=mensaje, a=is_alert: self._log(m, is_alert=a))
        if paso is not None and total and total > 0:
            pct = int(100 * paso / total)
            self.after(0, lambda p=pct: self.progreso.set(p/100))
            
            if self.inicio_tiempo:
                tiempo_transcurrido = (datetime.datetime.now() - self.inicio_tiempo).total_seconds()
                if paso > 0:
                    tiempo_por_paso = tiempo_transcurrido / paso
                    self.tiempo_estimado_total = tiempo_por_paso * total

    def _animar_spinner(self):
        if not self.spinner_activo:
            return
        char = self.spinner_chars[self.spinner_idx]
        self.spinner_idx = (self.spinner_idx + 1) % len(self.spinner_chars)
        
        if self.inicio_tiempo:
            tiempo_transcurrido = datetime.datetime.now() - self.inicio_tiempo
            segundos = tiempo_transcurrido.total_seconds()
            tiempo_str = f"{int(segundos // 60):02d}:{int(segundos % 60):02d}"
            
            estimado_str = ""
            if self.tiempo_estimado_total > 0:
                restante = max(0.0, self.tiempo_estimado_total - segundos)
                estimado_str = f" | Est. restante: {int(restante // 60):02d}:{int(restante % 60):02d}"
            
            self.estado_var.set(f"Procesando {char} [Tiempo: {tiempo_str}{estimado_str}]")
        else:
            self.estado_var.set(f"Procesando {char}…")
            
        self.after(100, self._animar_spinner)

    def _iniciar_proceso(self):
        carpeta = self.carpeta_var.get().strip()
        maestro = self.maestro_var.get().strip()

        if not carpeta or not os.path.isdir(carpeta):
            messagebox.showerror("Error", "Seleccione una carpeta de reportes válida.")
            return
        if not maestro or not os.path.isfile(maestro):
            messagebox.showerror("Error", "Seleccione el archivo Master_Simulador.")
            return
        if not maestro.lower().endswith(EXTENSIONES_MAESTRO):
            messagebox.showerror(
                "Error",
                "El maestro debe ser un archivo .xlsm o .xlsx.",
            )
            return

        self.btn_procesar.configure(state=tk.DISABLED)
        self.progreso.set(0)
        self.estado_var.set("Procesando…")
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self.inicio_tiempo = datetime.datetime.now()
        self.tiempo_estimado_total = 0.0
        self.spinner_activo = True
        self._animar_spinner()

        def trabajo():
            try:
                ok, pendientes = pegar_en_maestro(
                    maestro,
                    carpeta,
                    log_callback=self._callback_progreso,
                )
                self.spinner_activo = False
                
                fin_tiempo = datetime.datetime.now()
                total_segundos = (fin_tiempo - self.inicio_tiempo).total_seconds()
                tiempo_copia_str = f"{int(total_segundos // 60):02d}:{int(total_segundos % 60):02d}"
                
                msg = (f"Listo: {ok} columna(s) con datos pegados en Excel." f"\nTiempo total de copia: {tiempo_copia_str} ({total_segundos:.1f} seg)." f"\nGuarde el maestro manualmente (Ctrl+S).")
                if pendientes:
                    msg += f"\n{pendientes} reporte(s) sin emparejar."
                self.after(0, lambda: self.estado_var.set(f"Listo en {tiempo_copia_str}!"))
                self.after(0, lambda: messagebox.showinfo("Completado", msg))
            except ImportError:
                self.spinner_activo = False
                self.after(
                    0,
                    lambda: messagebox.showerror("Error", "Se requiere Microsoft Excel y pywin32." "Instale con: pip install pywin32",),)
                self.after(0, lambda: self.estado_var.set("Error."))
            except Exception as exc:
                self.spinner_activo = False
                self.after(
                    0,
                    lambda: messagebox.showerror("Error", str(exc)),
                )
                self.after(0, lambda: self.estado_var.set("Error."))
            finally:
                self.spinner_activo = False
                self.after(
                    0,
                    lambda: self.btn_procesar.configure(state=tk.NORMAL),
                )
                self.after(0, lambda: self.progreso.set(1))

        threading.Thread(target=trabajo, daemon=True).start()


def main():
    ImporterApp().mainloop()


if __name__ == "__main__":
    main()
