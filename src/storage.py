"""Atomic JSON persistence and safe custom photo import for Sayan Clicker."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .paths import get_custom_photos_dir, get_save_path

VALID_THEMES: tuple[str, ...] = ("cozy", "cyber")
VALID_PHOTO_MODES: tuple[str, ...] = ("auto", "custom")
MAX_CUSTOM_PHOTO_EDGE: int = 900
CUSTOM_PHOTO_FILENAME: str = "user_photo.png"

DEFAULT_CONFIG: dict[str, Any] = {
    "pets_count": 0,
    "best_combo": 0,
    "total_events_caught": 0,
    "quizzes_solved": 0,
    "sound_enabled": True,
    "always_on_top": False,
    "compact_mode": False,
    "theme": "cozy",
    "active_photo_mode": "auto",
    "custom_photo_path": None,
    "unlocked_milestones": [],
    "window_x": None,
    "window_y": None,
}


def _is_strict_int(value: Any) -> bool:
    """Return True if value is an int and not a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def get_default_config() -> dict[str, Any]:
    """Return a fresh deep-enough copy of the default configuration schema."""
    config = dict(DEFAULT_CONFIG)
    config["unlocked_milestones"] = []
    return config


def sanitize_config(raw: Any) -> dict[str, Any]:
    """Normalize arbitrary parsed data into a valid config dictionary."""
    clean = get_default_config()
    if not isinstance(raw, Mapping):
        return clean

    for counter_key in (
        "pets_count",
        "best_combo",
        "total_events_caught",
        "quizzes_solved",
    ):
        val = raw.get(counter_key)
        if _is_strict_int(val):
            clean[counter_key] = max(0, val)

    for bool_key in ("sound_enabled", "always_on_top", "compact_mode"):
        val = raw.get(bool_key)
        if isinstance(val, bool):
            clean[bool_key] = val

    theme = raw.get("theme")
    if isinstance(theme, str) and theme in VALID_THEMES:
        clean["theme"] = theme

    photo_mode = raw.get("active_photo_mode")
    if isinstance(photo_mode, str) and photo_mode in VALID_PHOTO_MODES:
        clean["active_photo_mode"] = photo_mode

    custom_path = raw.get("custom_photo_path")
    if custom_path is None:
        clean["custom_photo_path"] = None
    elif isinstance(custom_path, str):
        stripped = custom_path.strip()
        clean["custom_photo_path"] = stripped or None

    player_name = raw.get("player_name")
    if isinstance(player_name, str):
        clean["player_name"] = player_name.strip()[:40] or None

    milestones = raw.get("unlocked_milestones")
    if isinstance(milestones, list):
        clean["unlocked_milestones"] = sorted(
            {m for m in milestones if _is_strict_int(m) and m > 0}
        )

    for coord_key in ("window_x", "window_y"):
        val = raw.get(coord_key)
        if val is None or _is_strict_int(val):
            clean[coord_key] = val

    return clean


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load config from save.json with graceful fallback on missing or corrupt files."""
    target = path if path is not None else get_save_path()
    if not target.is_file():
        return get_default_config()

    try:
        raw_text = target.read_text(encoding="utf-8")
        parsed = json.loads(raw_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return get_default_config()

    return sanitize_config(parsed)


def save_config(config: Mapping[str, Any], path: Path | None = None) -> Path:
    """Atomically persist config to save.json via a .tmp file and os.replace."""
    target = path if path is not None else get_save_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    clean = sanitize_config(config)
    tmp_path = target.with_name(f"{target.name}.tmp")

    try:
        payload = json.dumps(clean, ensure_ascii=False, indent=2)
        with tmp_path.open("w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return target


def import_custom_photo(
    source_path: str | Path,
    dest_dir: Path | None = None,
) -> str:
    """Validate, EXIF-orient, resize (<=900px), and save a custom photo as PNG."""
    source = Path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"Custom photo source does not exist: {source}")

    target_dir = dest_dir if dest_dir is not None else get_custom_photos_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    dest_path = target_dir / CUSTOM_PHOTO_FILENAME
    tmp_path = target_dir / f"{CUSTOM_PHOTO_FILENAME}.tmp"

    with Image.open(source) as opened:
        opened.load()
        oriented = ImageOps.exif_transpose(opened)
        has_alpha = oriented.mode in ("RGBA", "LA", "PA") or "transparency" in oriented.info
        target_mode = "RGBA" if has_alpha else "RGB"
        if oriented.mode != target_mode:
            processed = oriented.convert(target_mode)
        else:
            processed = oriented.copy()

    if max(processed.size) > MAX_CUSTOM_PHOTO_EDGE:
        processed.thumbnail(
            (MAX_CUSTOM_PHOTO_EDGE, MAX_CUSTOM_PHOTO_EDGE),
            Image.Resampling.LANCZOS,
        )

    try:
        processed.save(tmp_path, format="PNG", optimize=True)
        os.replace(tmp_path, dest_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return str(dest_path)
