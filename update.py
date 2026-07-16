import os
import sys
import json
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

def descargar_y_actualizar(download_url, latest_version):
    """Descarga la nueva versión y reemplaza los archivos usando un script .bat visible."""
    zip_temp = "update.zip"
    app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    config_path = os.path.join(app_dir, "config.json")
    
    # Respaldar configuración actual en memoria
    config_respaldo = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config_respaldo = json.load(f)
        except Exception:
            pass

    config_respaldo["version"] = latest_version

    try:
        print(f"Descargando actualización v{latest_version}...")
        urllib.request.urlretrieve(download_url, os.path.join(app_dir, zip_temp))
        
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

echo [2/4] Extrayendo paquete de actualizacion (PowerShell)...
powershell -Command "Expand-Archive -Path '{os.path.join(app_dir, zip_temp)}' -DestinationPath '{app_dir}_temp' -Force"

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
            
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config_respaldo, f, indent=4, ensure_ascii=False)

        # --- ABRIR EN NUEVA VENTANA VISIBLE ---
        # Usamos 'start' para forzar a Windows a abrir una ventana de CMD dedicada
        subprocess.Popen(f'start "" "{bat_path}"', shell=True)
        sys.exit(0)
        
    except Exception as e:
        print(f"Ocurrió un error crítico durante la instalación: {e}")