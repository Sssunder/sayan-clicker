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
    """Return a writable %APPDATA%\\SayanClicker-style dir, falling back when the
    OS/security software denies folder creation under the user profile."""
    candidates: list[Path] = []
    appdata = os.environ.get("APPDATA", "").strip()
    if appdata:
        candidates.append(Path(appdata))
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if local:
        candidates.append(Path(local))
    candidates.append(Path.home() / "AppData" / "Roaming")
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent.parent)
    candidates.append(get_project_root())
    for base in candidates:
        app_dir = base / APP_FOLDER_NAME
        try:
            app_dir.mkdir(parents=True, exist_ok=True)
            probe = app_dir / ".write_probe"
            probe.write_bytes(b"sayan")
            probe.unlink()
            return app_dir
        except OSError:
            continue
    return candidates[0] / APP_FOLDER_NAME


def get_save_path() -> Path:
    """Return the path to %APPDATA%\\SayanClicker\\save.json."""
    return get_app_data_dir() / "save.json"


def get_custom_photos_dir() -> Path:
    """Return %APPDATA%\\SayanClicker\\custom_photos (creating it if missing)."""
    photos_dir = get_app_data_dir() / "custom_photos"
    photos_dir.mkdir(parents=True, exist_ok=True)
    return photos_dir


def get_cards_dir() -> Path:
    """Return %APPDATA%\\SayanClicker\\cards (creating it if missing)."""
    cards_dir = get_app_data_dir() / "cards"
    cards_dir.mkdir(parents=True, exist_ok=True)
    return cards_dir
