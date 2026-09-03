import os
import sys
import json
import time
import zipfile
import urllib.request
import subprocess
import shutil
import tempfile
from datetime import datetime

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
                incremental_name = f"TrackSIMTools-{local_version}-to-{latest_version}.zip"
                for asset in data.get("assets", []):
                    if asset["name"] == incremental_name:
                        download_url = asset["browser_download_url"]
                        break
                if download_url is None:
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

        return zip_path

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

def instalar_actualizacion(zip_path, latest_version, on_status=None):
    """Lanza una copia auxiliar para instalar la actualización con interfaz gráfica."""
    try:
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
        target_executable = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
        if getattr(sys, "frozen", False):
            updater_dir = tempfile.mkdtemp(prefix="TrackSIM_Tools_updater_")
            shutil.copytree(
                app_dir,
                updater_dir,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("*_temp", "*.part"),
            )
            updater_executable = os.path.join(updater_dir, os.path.basename(sys.executable))
            command = [updater_executable, "--apply-update", zip_path, latest_version, target_executable]
        else:
            command = [sys.executable, os.path.abspath(sys.argv[0]), "--apply-update", zip_path, latest_version, target_executable]
        subprocess.Popen(command, close_fds=True, start_new_session=True)
        if on_status:
            on_status("Instalación iniciada. Reiniciando la aplicación...")
        return True
    except Exception as e:
        print(f"Ocurrió un error al iniciar la instalación: {e}")
        if on_status:
            on_status(f"Error al iniciar la instalación: {e}")
        return False

def aplicar_actualizacion(zip_path, latest_version, target_dir, target_executable, on_status=None):
    """Extrae e instala el paquete desde el proceso auxiliar."""
    temp_dir = f"{target_dir}_temp"
    try:
        if on_status:
            on_status("Extrayendo el paquete de actualización...")
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        os.makedirs(temp_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archivo_zip:
            archivos = archivo_zip.infolist()
            total_bytes = sum(archivo.file_size for archivo in archivos) or 1
            extraidos_bytes = 0
            for indice, archivo in enumerate(archivos, start=1):
                archivo_zip.extract(archivo, temp_dir)
                extraidos_bytes += archivo.file_size
                porcentaje = min(int(extraidos_bytes * 100 / total_bytes), 100)
                if on_status:
                    on_status(
                        f"Extrayendo paquete de actualización... {porcentaje}% "
                        f"({indice}/{len(archivos)} archivos)"
                    )

        manifest_path = os.path.join(temp_dir, "update_manifest.json")
        manifest = {}
        if os.path.isfile(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as manifest_file:
                manifest = json.load(manifest_file)

        source_dir = os.path.join(temp_dir, "TrackSIM_Tools")
        if not os.path.isdir(source_dir):
            source_dir = temp_dir
        if on_status:
            on_status("Instalando los nuevos archivos...")
        ultimo_error = None
        for intento in range(8):
            try:
                shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
                ultimo_error = None
                break
            except OSError as error:
                ultimo_error = error
                time.sleep(1)
        if ultimo_error is not None:
            raise ultimo_error
        for relative_path in manifest.get("deleted_files", []):
            deleted_path = os.path.join(target_dir, relative_path.replace("/", os.sep))
            if os.path.isfile(deleted_path):
                os.remove(deleted_path)
        if manifest.get("type") == "incremental":
            latest_version = manifest.get("to_version", latest_version)
        config_path = os.path.join(target_dir, "config.json")
        config = {}
        if os.path.isfile(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as archivo_config:
                    config = json.load(archivo_config)
            except (OSError, json.JSONDecodeError):
                config = {}
        config["version"] = latest_version
        config["build_date"] = datetime.now().strftime("%d/%m/%y")
        config_temp_path = f"{config_path}.tmp"
        with open(config_temp_path, "w", encoding="utf-8") as archivo_config:
            json.dump(config, archivo_config, indent=4, ensure_ascii=False)
        os.replace(config_temp_path, config_path)
        if on_status:
            on_status("Limpiando archivos temporales...")
        os.remove(zip_path)
        cache_version_path = os.path.join(target_dir, "update.version")
        if os.path.exists(cache_version_path):
            os.remove(cache_version_path)
        shutil.rmtree(temp_dir, ignore_errors=True)
        if on_status:
            on_status("Actualización completada. Reiniciando la aplicación...")
        subprocess.Popen([target_executable], close_fds=True, start_new_session=True)
        return True
    except Exception as error:
        if on_status:
            on_status(f"No se pudo instalar la actualización: {error}")
        return False