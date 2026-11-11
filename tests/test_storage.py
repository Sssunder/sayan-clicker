"""Unit tests for src.paths and src.storage."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from src import paths, storage


class PathsTests(unittest.TestCase):
    def test_get_resource_path_dev_and_frozen(self) -> None:
        dev_path = paths.get_resource_path("assets/cat_sayan.jpg")
        expected_root = Path(__file__).resolve().parent.parent
        self.assertEqual(dev_path, expected_root / "assets" / "cat_sayan.jpg")

        leading_slash = paths.get_resource_path("/assets/cat_sayan.jpg")
        self.assertEqual(leading_slash, expected_root / "assets" / "cat_sayan.jpg")

        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.object(sys, "_MEIPASS", tmp, create=True),
            ):
                frozen_path = paths.get_resource_path("assets/cat_sayan.jpg")
                self.assertEqual(frozen_path, Path(tmp) / "assets" / "cat_sayan.jpg")

    def test_app_data_dirs_use_appdata_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"APPDATA": tmp}):
                app_dir = paths.get_app_data_dir()
                self.assertEqual(app_dir, Path(tmp) / "SayanClicker")
                self.assertTrue(app_dir.is_dir())
                self.assertEqual(paths.get_save_path(), app_dir / "save.json")

                photos_dir = paths.get_custom_photos_dir()
                self.assertEqual(photos_dir, app_dir / "custom_photos")
                self.assertTrue(photos_dir.is_dir())

        with tempfile.TemporaryDirectory() as fake_home:
            with (
                patch.dict(os.environ, {"APPDATA": ""}),
                patch.object(Path, "home", return_value=Path(fake_home)),
            ):
                fallback_dir = paths.get_app_data_dir()
                self.assertEqual(
                    fallback_dir,
                    Path(fake_home) / "AppData" / "Roaming" / "SayanClicker",
                )
                self.assertTrue(fallback_dir.is_dir())


class StorageTests(unittest.TestCase):
    def test_missing_save_returns_fresh_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_file = Path(tmp) / "SayanClicker" / "save.json"
            cfg1 = storage.load_config(save_file)
            cfg2 = storage.load_config(save_file)

            self.assertEqual(cfg1["pets_count"], 0)
            self.assertEqual(cfg1["sound_enabled"], True)
            self.assertEqual(cfg1["always_on_top"], False)
            self.assertEqual(cfg1["compact_mode"], False)
            self.assertEqual(cfg1["theme"], "cozy")
            self.assertEqual(cfg1["active_photo_mode"], "auto")
            self.assertIsNone(cfg1["custom_photo_path"])
            self.assertEqual(cfg1["unlocked_milestones"], [])
            self.assertIsNone(cfg1["window_x"])
            self.assertIsNone(cfg1["window_y"])

            cfg1["unlocked_milestones"].append(5)
            self.assertEqual(cfg2["unlocked_milestones"], [])

    def test_atomic_save_and_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_file = Path(tmp) / "save.json"
            data = {
                "pets_count": 320,
                "best_combo": 28,
                "total_events_caught": 7,
                "quizzes_solved": 3,
                "sound_enabled": False,
                "always_on_top": True,
                "compact_mode": True,
                "theme": "cyber",
                "active_photo_mode": "custom",
                "custom_photo_path": "C:/temp/user_photo.png",
                "unlocked_milestones": [25, 1, 314, 25],
                "window_x": -120,
                "window_y": 80,
            }
            written_path = storage.save_config(data, save_file)
            self.assertEqual(written_path, save_file)
            self.assertFalse(save_file.with_name("save.json.tmp").exists())

            loaded = storage.load_config(save_file)
            self.assertEqual(loaded["pets_count"], 320)
            self.assertEqual(loaded["best_combo"], 28)
            self.assertEqual(loaded["total_events_caught"], 7)
            self.assertEqual(loaded["quizzes_solved"], 3)
            self.assertFalse(loaded["sound_enabled"])
            self.assertTrue(loaded["always_on_top"])
            self.assertTrue(loaded["compact_mode"])
            self.assertEqual(loaded["theme"], "cyber")
            self.assertEqual(loaded["active_photo_mode"], "custom")
            self.assertEqual(loaded["custom_photo_path"], "C:/temp/user_photo.png")
            self.assertEqual(loaded["unlocked_milestones"], [1, 25, 314])
            self.assertEqual(loaded["window_x"], -120)
            self.assertEqual(loaded["window_y"], 80)

    def test_corrupted_json_and_bad_types_graceful_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            save_file = Path(tmp) / "save.json"
            save_file.write_text("{corrupt json !!!", encoding="utf-8")
            self.assertEqual(storage.load_config(save_file), storage.get_default_config())

            save_file.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            self.assertEqual(storage.load_config(save_file), storage.get_default_config())

            bad_payload = {
                "pets_count": True,
                "best_combo": -10,
                "total_events_caught": "42",
                "quizzes_solved": 2,
                "sound_enabled": "nope",
                "theme": "neon-slop",
                "active_photo_mode": "invalid",
                "custom_photo_path": "   ",
                "unlocked_milestones": [True, -5, "100", 5, 100],
                "window_x": "bad",
                "window_y": False,
            }
            save_file.write_text(json.dumps(bad_payload), encoding="utf-8")
            loaded = storage.load_config(save_file)
            self.assertEqual(loaded["pets_count"], 0)
            self.assertEqual(loaded["best_combo"], 0)
            self.assertEqual(loaded["total_events_caught"], 0)
            self.assertEqual(loaded["quizzes_solved"], 2)
            self.assertTrue(loaded["sound_enabled"])
            self.assertEqual(loaded["theme"], "cozy")
            self.assertEqual(loaded["active_photo_mode"], "auto")
            self.assertIsNone(loaded["custom_photo_path"])
            self.assertEqual(loaded["unlocked_milestones"], [5, 100])
            self.assertIsNone(loaded["window_x"])
            self.assertIsNone(loaded["window_y"])

    def test_import_custom_photo_resizes_preserves_alpha_and_exif(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            dest_dir = tmp_path / "custom_photos"

            # 1. Large RGB image -> resized to max edge 900px
            big_src = tmp_path / "big.jpg"
            Image.new("RGB", (1800, 1200), (240, 120, 80)).save(big_src, format="JPEG")
            saved_big = storage.import_custom_photo(str(big_src), dest_dir=dest_dir)
            self.assertTrue(saved_big.endswith("user_photo.png"))
            with Image.open(saved_big) as out_big:
                self.assertEqual(out_big.format, "PNG")
                self.assertEqual(out_big.size, (900, 600))

            # 2. RGBA image with transparency -> alpha preserved, not upscaled
            alpha_src = tmp_path / "alpha.png"
            alpha_img = Image.new("RGBA", (320, 240), (10, 20, 30, 128))
            alpha_img.save(alpha_src, format="PNG")
            saved_alpha = storage.import_custom_photo(str(alpha_src), dest_dir=dest_dir)
            with Image.open(saved_alpha) as out_alpha:
                self.assertEqual(out_alpha.mode, "RGBA")
                self.assertEqual(out_alpha.size, (320, 240))
                self.assertEqual(out_alpha.getpixel((10, 10))[3], 128)

            # 3. EXIF Orientation=6 rotates 400x200 image to 200x400
            exif_src = tmp_path / "rotated.jpg"
            rot_img = Image.new("RGB", (400, 200), (50, 150, 200))
            exif = rot_img.getexif()
            exif[0x0112] = 6  # Rotate 90 CW
            rot_img.save(exif_src, format="JPEG", exif=exif)
            saved_rot = storage.import_custom_photo(str(exif_src), dest_dir=dest_dir)
            with Image.open(saved_rot) as out_rot:
                self.assertEqual(out_rot.size, (200, 400))

            # 4. Invalid/non-image file raises cleanly without leaving .tmp
            bad_src = tmp_path / "not_an_image.png"
            bad_src.write_text("hello cat", encoding="utf-8")
            with self.assertRaises(Exception):
                storage.import_custom_photo(str(bad_src), dest_dir=dest_dir)
            self.assertFalse((dest_dir / "user_photo.png.tmp").exists())


if __name__ == "__main__":
    unittest.main()
