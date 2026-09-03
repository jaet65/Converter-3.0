import os
import sys
import json
import time
import zipfile
import urllib.request
import subprocess

# =====================================================================
# CONFIGURACIÓN DEL REPOSITORIO DE GITHUB
# =====================================================================
GITHUB_USER = "jaet65"
REPO_NAME = "Converter-3.0"
ZIP_ASSET_NAME = "TrackSIMTools.zip"  # Nombre exacto del archivo subido en el Release
# =====================================================================

def obtener_version_local():
    """Lee la versión actual desde el archivo config.json local."""
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    config_path = os.path.join(app_dir, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("version", "1.0.0")
        except Exception:
            pass
    return "1.0.0"

def verificar_actualizacion_silent():
    """Consulta la API pública de GitHub para verificar si existe una versión más reciente."""
    url = f"https://api.github.com/repos/{GITHUB_USER}/{REPO_NAME}/releases/latest"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            latest_version = data["tag_name"].replace("v", "")
            local_version = obtener_version_local()
            
            if latest_version != local_version:
                download_url = None
                for asset in data.get("assets", []):
                    if asset["name"] == ZIP_ASSET_NAME:
                        download_url = asset["browser_download_url"]
                        break
                return latest_version, download_url
    except Exception as e:
        print(f"Error al verificar actualizaciones en GitHub: {e}")
    return None, None

def archivo_zip_valido(zip_path):
    """Comprueba que el ZIP sea legible y que sus archivos no tengan errores CRC."""
    try:
        if not zipfile.is_zipfile(zip_path):
            return False
        with zipfile.ZipFile(zip_path) as archivo_zip:
            return archivo_zip.testzip() is None
    except (OSError, zipfile.BadZipFile, RuntimeError):
        return False

def actualizacion_descargada(latest_version):
    """Indica si existe un ZIP local reutilizable para la versión detectada."""
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    zip_path = os.path.join(app_dir, "update.zip")
    cache_version_path = os.path.join(app_dir, "update.version")
    if not archivo_zip_valido(zip_path):
        return False
    if not os.path.exists(cache_version_path):
        return True
    try:
        with open(cache_version_path, "r", encoding="utf-8") as f:
            return f.read().strip() == latest_version
    except OSError:
        return False

def descargar_y_preparar(download_url, latest_version, on_status=None):
    """Descarga la actualización y deja preparado el instalador sin ejecutarlo."""
    zip_temp = "update.zip"
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    zip_path = os.path.join(app_dir, zip_temp)
    zip_part_path = f"{zip_path}.part"
    cache_version_path = os.path.join(app_dir, "update.version")

    try:
        cached_version = None
        if os.path.exists(cache_version_path):
            with open(cache_version_path, "r", encoding="utf-8") as f:
                cached_version = f.read().strip()

        if archivo_zip_valido(zip_path) and cached_version in (None, latest_version):
            if on_status:
                on_status(f"Usando actualización v{latest_version} ya descargada")
            if cached_version is None:
                with open(cache_version_path, "w", encoding="utf-8") as f:
                    f.write(latest_version)
        else:
            if on_status:
                on_status(f"Descargando actualización v{latest_version}...")
            print(f"Descargando actualización v{latest_version}...")
            inicio_descarga = time.monotonic()

            def formatear_velocidad(bytes_por_segundo):
                unidades = ("B/s", "KB/s", "MB/s", "GB/s")
                velocidad = float(bytes_por_segundo)
                unidad = unidades[0]
                for unidad_actual in unidades:
                    unidad = unidad_actual
                    if velocidad < 1024 or unidad_actual == unidades[-1]:
                        break
                    velocidad /= 1024
                return f"{velocidad:.2f} {unidad}"

            def reportar_descarga(block_count, block_size, total_size):
                if on_status and total_size > 0:
                    downloaded = min(block_count * block_size, total_size)
                    percentage = int(downloaded * 100 / total_size)
                    elapsed = max(time.monotonic() - inicio_descarga, 0.001)
                    speed = formatear_velocidad(downloaded / elapsed)
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    on_status(
                        f"Descargando actualización v{latest_version}... "
                        f"{percentage}% ({downloaded_mb:.2f} MB/{total_mb:.2f} MB, {speed})"
                    )

            if os.path.exists(zip_part_path):
                os.remove(zip_part_path)
            urllib.request.urlretrieve(download_url, zip_part_path, reporthook=reportar_descarga)
            if not archivo_zip_valido(zip_part_path):
                raise ValueError("El archivo descargado no es un ZIP válido o está incompleto")
            os.replace(zip_part_path, zip_path)
            with open(cache_version_path, "w", encoding="utf-8") as f:
                f.write(latest_version)

        if on_status:
            on_status("Descarga completada. Preparando instalación...")
        
        parent_dir = os.path.dirname(app_dir)
        
# --- SCRIPT BATCH CON EXTRACCIÓN Y COPIA COMPENSADA ---
        bat_content = f"""@echo off
title Actualizador TrackSIM Tools v{latest_version}
color 0A
echo ====================================================
echo      ACTUALIZANDO TRACKSIM TOOLS A v{latest_version}
echo ====================================================
echo.
echo [1/4] Esperando a que la aplicacion principal se cierre...
timeout /t 3 /nobreak > nul

echo [2/4] Extrayendo paquete de actualizacion...
if exist "{app_dir}_temp" rd /S /Q "{app_dir}_temp" > nul 2>&1
mkdir "{app_dir}_temp"
tar -xf "{os.path.join(app_dir, zip_temp)}" -C "{app_dir}_temp"

if errorlevel 1 (
    color 0C
    echo ERROR: No se pudo extraer el archivo de update.
    rd /S /Q "{app_dir}_temp" > nul 2>&1
    pause
    (goto) 2>nul & del "%~f0" & exit
)

if exist "{app_dir}_temp" (
    echo [3/4] Instalando nuevos archivos de sistema...
    
    :: Comprobamos si los archivos se extrajeron dentro de una subcarpeta "TrackSIM_Tools"
    if exist "{app_dir}_temp\\TrackSIM_Tools" (
        xcopy "{app_dir}_temp\\TrackSIM_Tools\\*" "{app_dir}\\" /E /I /Y
    ) else (
        :: Si venían sueltos por alguna razón, se copian de la raíz temporal
        xcopy "{app_dir}_temp\\*" "{app_dir}\\" /E /I /Y
    )
    
    echo [4/4] Limpiando archivos temporales...
    
    :: Forzamos la eliminación del archivo zip y la carpeta temporal completa (incluyendo subcarpetas)
    del /F /Q "{os.path.join(app_dir, zip_temp)}" > nul 2>&1
    del /F /Q "{cache_version_path}" > nul 2>&1
    rd /S /Q "{app_dir}_temp" > nul 2>&1
    
    echo.
    echo ====================================================
    echo    ¡ACTUALIZACION COMPLETADA CON EXITO!
    echo ====================================================
    echo Reiniciando TrackSIM Tools...
    timeout /t 2 /nobreak > nul
    
    :: Abrimos la aplicación envolviendo la ruta entre comillas dobles para evitar problemas con espacios
    start "" "{sys.argv[0]}"
    
    :: Borramos este archivo batch y cerramos la consola limpiamente en líneas separadas
    (goto) 2>nul & del "%~f0" & exit
) else (
    color 0C
    echo.
    echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    echo   ERROR: No se pudo extraer el archivo de update.
    echo XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
    echo.
    pause
    (goto) 2>nul & del "%~f0" & exit
)
"""
        bat_path = os.path.join(parent_dir, "updater.bat")
        with open(bat_path, "w", encoding="utf-8") as bat_file:
            bat_file.write(bat_content)
            
        return bat_path

    except Exception as e:
        if os.path.exists(zip_part_path):
            try:
                os.remove(zip_part_path)
            except OSError:
                pass
        print(f"Ocurrió un error crítico durante la instalación: {e}")
        if on_status:
            on_status(f"Error en la actualización: {e}")
        return None

def instalar_actualizacion(bat_path, latest_version, on_status=None):
    """Lanza el instalador después de confirmar que la actualización está lista."""
    try:
        subprocess.Popen(f'start "" "{bat_path}"', shell=True)
        if on_status:
            on_status("Instalación iniciada. Reiniciando la aplicación...")
        return True
    except Exception as e:
        print(f"Ocurrió un error al iniciar la instalación: {e}")
        if on_status:
            on_status(f"Error al iniciar la instalación: {e}")
        return False