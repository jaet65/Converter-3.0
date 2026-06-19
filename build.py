import json
import subprocess
import sys
from datetime import datetime

CONFIG_FILE = "config.json"
SPEC_FILE = "convertidor_reportes.spec"

def run_build():
    """
    Increments the patch version in config.json and runs the PyInstaller build.
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


    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error reading {CONFIG_FILE}: {e}")
        sys.exit(1)

    current_version = config.get("version", "1.0.0")
    print(f"Current version: {current_version}")

    try:
        major, minor, patch = map(int, current_version.split('.'))
        patch += 1
        new_version = f"{major}.{minor}.{patch}"
    except ValueError:
        print(f"Invalid version format in {CONFIG_FILE}. Expected 'major.minor.patch'.")
        print("Build script requires a 'major.minor.patch' version format in config.json.")
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
