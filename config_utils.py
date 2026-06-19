import json
import os
import sys
from copy import deepcopy

CONFIG_FILENAME = "config.json"

DEFAULT_CONFIG = {
    "ruta_origen": "",
    "ruta_destino": "",
    "convert_to_pdf": True,
    "convert_to_excel": True,
    "importer_folder": "",
    "importer_master_file": "",
    "version": "1.0.0",
    "build_date": "",
}


def is_frozen():
    return getattr(sys, "frozen", False)


def get_app_dir():
    """Directorio donde se guarda la configuración del usuario."""
    if is_frozen():
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_bundle_dir():
    """Directorio de recursos empaquetados (_MEIPASS en el .exe)."""
    if is_frozen():
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_config_path():
    return os.path.join(get_app_dir(), CONFIG_FILENAME)


def get_bundled_config_path():
    return os.path.join(get_bundle_dir(), CONFIG_FILENAME)


def load_config():
    config = deepcopy(DEFAULT_CONFIG)

    bundled_path = get_bundled_config_path()
    if os.path.isfile(bundled_path):
        try:
            with open(bundled_path, encoding="utf-8") as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    user_path = get_config_path()
    if os.path.normpath(user_path) != os.path.normpath(bundled_path) and os.path.isfile(user_path):
        try:
            with open(user_path, encoding="utf-8") as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass

    return config


def save_config(updates):
    config = load_config()
    config.update(updates)
    path = get_config_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4)
    return config
