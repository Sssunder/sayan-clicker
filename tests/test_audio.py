"""Verification tests for generated WAV assets and stdlib SoundEngine."""

from __future__ import annotations

import ast
import math
import struct
import sys
import time
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.audio import SoundEngine  # noqa: E402

EXPECTED_WAVS = {
    "tap1.wav": 0.10,
    "tap2.wav": 0.09,
    "tap3.wav": 0.08,
    "meow.wav": 0.42,
    "meow2.wav": 0.30,
    "treat.wav": 0.24,
    "levelup.wav": 0.58,
    "zoomies.wav": 0.36,
}


class AudioSubsystemTests(unittest.TestCase):
    """Verify WAV synthesis integrity, stdlib-only imports, and SoundEngine behavior."""

    sounds_dir = PROJECT_ROOT / "assets" / "sounds"

    def test_audio_module_uses_stdlib_only(self) -> None:
        audio_src = (PROJECT_ROOT / "src" / "audio.py").read_text(encoding="utf-8")
        tree = ast.parse(audio_src)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertNotIn("numpy", imported)
        self.assertNotIn("scipy", imported)

    def test_wav_assets_valid_and_unclipped(self) -> None:
        for filename, expected_sec in EXPECTED_WAVS.items():
            wav_path = self.sounds_dir / filename
            self.assertTrue(wav_path.is_file(), f"Missing WAV file: {wav_path}")

            with wave.open(str(wav_path), "rb") as wf:
                channels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                nframes = wf.getnframes()
                raw = wf.readframes(nframes)

            self.assertEqual(channels, 1, filename)
            self.assertEqual(sampwidth, 2, filename)
            self.assertEqual(framerate, 44100, filename)
            self.assertGreater(nframes, 0, filename)
            self.assertAlmostEqual(nframes / framerate, expected_sec, delta=0.02, msg=filename)

            samples = struct.unpack(f"<{nframes}h", raw)
            peak = max(abs(s) for s in samples)
            rms = math.sqrt(sum(s * s for s in samples) / nframes)
            self.assertLessEqual(peak, 32767, f"Clipping detected in {filename}")
            self.assertGreater(rms, 100.0, f"Unexpectedly silent WAV: {filename}")
            self.assertLessEqual(abs(samples[0]), 64, f"Non-zero start click in {filename}")
            self.assertLessEqual(abs(samples[-1]), 64, f"Non-zero end click in {filename}")
            print(
                f"PASS {filename}: frames={nframes} ({nframes / framerate:.2f}s), "
                f"rate={framerate}, peak={peak}/32767 ({peak / 32767:.2f}), rms={rms:.1f}"
            )

    def test_sound_engine_preload_cooldown_and_mute(self) -> None:
        engine = SoundEngine(self.sounds_dir, enabled=True)
        expected_names = sorted(Path(name).stem for name in EXPECTED_WAVS)
        self.assertEqual(sorted(engine._sounds.keys()), expected_names)
        for name, data in engine._sounds.items():
            self.assertTrue(data.startswith(b"RIFF"), f"{name} missing RIFF header")

        # Play all 6 sounds safely with zero cooldown error.
        for name in expected_names:
            played = engine.play(name, cooldown_ms=0)
            self.assertIsInstance(played, bool)
            self.assertTrue(played, f"Expected playback to succeed for {name}")
            time.sleep(0.02)

        # Cooldown check on a fresh engine: immediate retrigger is suppressed, after 95ms succeeds.
        cooldown_engine = SoundEngine(self.sounds_dir, enabled=True)
        self.assertTrue(cooldown_engine.play("treat", cooldown_ms=80))
        self.assertFalse(cooldown_engine.play("treat", cooldown_ms=80))
        time.sleep(0.095)
        self.assertTrue(cooldown_engine.play("treat", cooldown_ms=80))
        cooldown_engine.stop()

        # Mute / unmute check.
        engine.set_enabled(False)
        self.assertFalse(engine.enabled)
        self.assertFalse(engine.play("meow", cooldown_ms=0))

        engine.set_enabled(True)
        self.assertTrue(engine.enabled)
        self.assertTrue(engine.play("meow", cooldown_ms=0))

        # Missing sound & missing directory resilience.
        self.assertFalse(engine.play("nonexistent_sound"))
        empty_engine = SoundEngine(PROJECT_ROOT / "assets" / "missing_dir", enabled=True)
        self.assertEqual(empty_engine._sounds, {})
        self.assertFalse(empty_engine.play("tap1"))
        engine.stop()

    def test_rapid_autoclick_and_device_failure_resilience(self) -> None:
        engine = SoundEngine(self.sounds_dir, enabled=True)
        t0 = time.monotonic()
        played_count = sum(1 for _ in range(20) if engine.play("tap1", cooldown_ms=80))
        elapsed = time.monotonic() - t0
        self.assertEqual(played_count, 1)
        self.assertLess(elapsed, 0.25, "play() must never stall the UI thread")

        # Simulate unavailable audio device / backend exceptions.
        with patch.object(engine, "_play_sound_w", side_effect=OSError("no device")), \
             patch("src.audio.winsound.PlaySound", side_effect=RuntimeError("no audio")):
            self.assertFalse(engine.play("meow", cooldown_ms=0))
            engine.set_enabled(False)
        engine.stop()


if __name__ == "__main__":
    unittest.main(verbosity=2)
