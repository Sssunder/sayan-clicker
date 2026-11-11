"""Lightweight stdlib-only WAV preloader and async audio playback engine."""

from __future__ import annotations

import ctypes
import threading
import time
from pathlib import Path
from typing import Any

try:
    import winsound
except ImportError:  # pragma: no cover - non-Windows fallback
    winsound = None  # type: ignore[assignment]


_SND_ASYNC = getattr(winsound, "SND_ASYNC", 0x0001)
_SND_NODEFAULT = getattr(winsound, "SND_NODEFAULT", 0x0002)
_SND_MEMORY = getattr(winsound, "SND_MEMORY", 0x0004)
_SND_FILENAME = getattr(winsound, "SND_FILENAME", 0x00020000)
_ASYNC_MEMORY_FLAGS = _SND_MEMORY | _SND_ASYNC | _SND_NODEFAULT
_ASYNC_FILE_FLAGS = _SND_FILENAME | _SND_ASYNC | _SND_NODEFAULT


def _load_winmm_playsound() -> Any | None:
    """Bind a private Win32 PlaySoundW handle so global ctypes.windll is untouched."""
    if winsound is None:
        return None
    try:
        winmm = ctypes.WinDLL("winmm")
        play_fn = winmm.PlaySoundW
        play_fn.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint]
        play_fn.restype = ctypes.c_int
        return play_fn
    except Exception:
        return None


class SoundEngine:
    """Zero-I/O in-memory WAV sound effects player with per-sound cooldowns."""

    def __init__(self, sounds_dir: Path, enabled: bool = True) -> None:
        self.sounds_dir = Path(sounds_dir)
        self._enabled = bool(enabled)
        self._lock = threading.RLock()
        self._sounds: dict[str, bytes] = {}
        self._paths: dict[str, Path] = {}
        # Pin raw C buffers for the lifetime of SoundEngine so Win32 async audio
        # never reads freed memory after play() returns.
        self._buffers: dict[str, ctypes.Array[ctypes.c_char]] = {}
        self._last_played: dict[str, float] = {}
        self._play_sound_w = _load_winmm_playsound()
        self._preload_sounds()

    def _preload_sounds(self) -> None:
        """Read all .wav files from sounds_dir into memory once on startup."""
        if not self.sounds_dir.is_dir():
            return
        for wav_path in sorted(self.sounds_dir.glob("*.wav")):
            try:
                wav_bytes = wav_path.read_bytes()
            except OSError:
                continue
            if not wav_bytes:
                continue
            stem = wav_path.stem
            self._sounds[stem] = wav_bytes
            self._paths[stem] = wav_path
            self._buffers[stem] = ctypes.create_string_buffer(wav_bytes, len(wav_bytes))

    @property
    def enabled(self) -> bool:
        """Return whether sound playback is currently enabled."""
        with self._lock:
            return self._enabled

    @property
    def loaded_sounds(self) -> tuple[str, ...]:
        """Return names of all preloaded WAV assets."""
        return tuple(self._sounds.keys())

    def set_enabled(self, enabled: bool) -> None:
        """Enable or mute audio; stops any active async sound when muted."""
        with self._lock:
            self._enabled = bool(enabled)
            if not self._enabled:
                self.stop()

    def stop(self) -> None:
        """Stop any currently playing asynchronous sound safely."""
        if winsound is None:
            return
        try:
            winsound.PlaySound(None, 0)
        except Exception:
            pass

    def play(self, name: str, cooldown_ms: int = 80) -> bool:
        """Play a preloaded sound asynchronously if enabled and past cooldown."""
        with self._lock:
            if not self._enabled:
                return False
            wav_bytes = self._sounds.get(name)
            if not wav_bytes:
                return False

            now = time.monotonic()
            last = self._last_played.get(name)
            if cooldown_ms > 0 and last is not None and (now - last) * 1000.0 < cooldown_ms:
                return False
            self._last_played[name] = now

            c_buf = self._buffers.get(name)
            wav_path = self._paths.get(name)
            return self._dispatch_async_playback(wav_bytes, c_buf, wav_path)

    def _dispatch_async_playback(
        self,
        wav_bytes: bytes,
        c_buf: ctypes.Array[ctypes.c_char] | None,
        wav_path: Path | None,
    ) -> bool:
        """Start non-blocking playback from memory, falling back safely if needed."""
        # CPython's winsound.PlaySound rejects SND_MEMORY | SND_ASYNC with RuntimeError,
        # so prefer winmm.PlaySoundW on our pinned buffer, then fallback to winsound.
        if self._play_sound_w is not None and c_buf is not None:
            try:
                if bool(self._play_sound_w(c_buf, None, _ASYNC_MEMORY_FLAGS)):
                    return True
            except Exception:
                pass

        if winsound is None:
            return False

        try:
            winsound.PlaySound(wav_bytes, _ASYNC_MEMORY_FLAGS)
            return True
        except RuntimeError:
            if wav_path is not None and wav_path.is_file():
                try:
                    winsound.PlaySound(str(wav_path), _ASYNC_FILE_FLAGS)
                    return True
                except Exception:
                    return False
            return False
        except Exception:
            return False

    def __del__(self) -> None:
        try:
            self.stop()
        except Exception:
            pass
