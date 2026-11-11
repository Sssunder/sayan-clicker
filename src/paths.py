"""Resource and user-data path resolution for Sayan Clicker."""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_FOLDER_NAME = "SayanClicker"


def get_project_root() -> Path:
    """Return the application root directory or PyInstaller bundle directory."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def get_resource_path(relative_path: str) -> Path:
    """Resolve an asset path relative to the project root or PyInstaller _MEIPASS."""
    clean_relative = relative_path.lstrip("/\\")
    return get_project_root() / clean_relative


def get_app_data_dir() -> Path:
    """Return %APPDATA%\\SayanClicker (creating it cleanly if missing)."""
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        base_dir = Path(appdata)
    else:
        base_dir = Path.home() / "AppData" / "Roaming"
    app_dir = base_dir / APP_FOLDER_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_save_path() -> Path:
    """Return the path to %APPDATA%\\SayanClicker\\save.json."""
    return get_app_data_dir() / "save.json"


def get_custom_photos_dir() -> Path:
    """Return %APPDATA%\\SayanClicker\\custom_photos (creating it if missing)."""
    photos_dir = get_app_data_dir() / "custom_photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    return photos_dir
