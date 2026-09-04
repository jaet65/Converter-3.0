# Build script for the Converter 3.0 application
import json
import subprocess
import sys
import os
import shutil
from datetime import datetime

CONFIG_FILE = "config.json"
SPEC_FILE = "convertidor_reportes.spec"

def clean_old_builds():
    """
    Elimina de forma segura las carpetas temporales 'build' y 'dist'
    antes de comenzar una nueva compilación limpia.
    """
    folders_to_clean = ["build", "dist"]
    print("Limpiando compilaciones antiguas...")
    
    for folder in folders_to_clean:
        if os.path.exists(folder):
            try:
                # shutil.rmtree equivale a Remove-Item -Recurse -Force
                shutil.rmtree(folder)
                print(f"  -> Carpeta '{folder}' eliminada con éxito.")
            except Exception as e:
                print(f"  [!] No se pudo eliminar '{folder}': {e}")
                print("  [!] Asegúrate de que ningún archivo esté abierto o en uso.")
        else:
            print(f"  -> Carpeta '{folder}' no existe, no hace falta limpiar.")

def run_build():
    """
    Uses the GitHub tag version when available and runs the PyInstaller build.
    """
    print("Installing/updating dependencies...")
    pip_install_command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-r",
        "requirements.txt"
    ]
    subprocess.run(pip_install_command, check=True, text=True)
    print("Dependencies installed/updated.")

    clean_old_builds()

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading {CONFIG_FILE}: {e}")
        sys.exit(1)

    current_version = config.get("version", "1.0.0")
    tag_name = os.environ.get("GITHUB_REF_NAME", "").strip()
    if tag_name.startswith("v"):
        new_version = tag_name[1:]
        print(f"Using GitHub tag version: {new_version}")
        os.environ.pop("TRACKSIM_BOOTSTRAP_BUILD", None)
    else:
        new_version = current_version
        print(f"No GitHub version tag found; keeping version: {new_version}")
        if os.environ.get("TRACKSIM_FULL_BUILD") != "1":
            os.environ["TRACKSIM_BOOTSTRAP_BUILD"] = "1"
            print("Local build mode: generating compact bootstrap installer")

    version_parts = new_version.split('.')
    if len(version_parts) != 3 or not all(part.isdigit() for part in version_parts):
        print(f"Invalid version '{new_version}'. Expected a tag in the format vMAJOR.MINOR.PATCH.")
        sys.exit(1)


    build_date = datetime.now().strftime("%d/%m/%y")
    config["version"] = new_version
    config["build_date"] = build_date
    print(f"New version: {new_version}")
    print(f"Build date: {build_date}")

    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except IOError as e:
        print(f"Error writing to {CONFIG_FILE}: {e}")
        sys.exit(1)

    print("Starting PyInstaller build...")
    build_command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        SPEC_FILE
    ]

    try:
        process = subprocess.run(
            build_command,
            check=True,
            text=True
        )
        print("--------------------------")
        print("Build successful!")
        print(f"Build version: {new_version} ({build_date})")

    except FileNotFoundError:
        print(f"Error: Command '{build_command[0]}' not found. Is Python/PyInstaller in your PATH?")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print("--------------------------")
        print(f"Build failed with exit code {e.returncode}.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred during the build: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_build()
