"""Headless-safe Qt UI smoke tests for SayanClickerApp (offscreen platform)."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PIL import Image
from PySide6.QtWidgets import QApplication

from src.ui_qt import SayanClickerApp


class SayanClickerUISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(sys.argv)

    def test_app_lifecycle_interactions_and_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                app = SayanClickerApp()
                try:
                    self.assertEqual(app.state.pets_count, 0)

                    # Pet Sayan and verify counter + inscriptions update
                    app._perform_pet(150.0, 140.0)
                    self.assertGreaterEqual(app.state.pets_count, 1)
                    self.assertGreater(len(app._particles), 0)

                    # Toggle compact mode, always-on-top, theme, sound, pose
                    app.toggle_compact_mode()
                    self.assertTrue(app.compact_mode)
                    app.toggle_compact_mode()
                    self.assertFalse(app.compact_mode)

                    app.toggle_always_on_top()
                    self.assertTrue(app.always_on_top)
                    app.toggle_always_on_top()
                    self.assertFalse(app.always_on_top)

                    app.toggle_theme()
                    self.assertEqual(app.theme.key, "cyber")
                    app.toggle_theme()
                    self.assertEqual(app.theme.key, "cozy")

                    app.toggle_sound()
                    self.assertFalse(app.sound.enabled)
                    app.toggle_sound()
                    self.assertTrue(app.sound.enabled)

                    prev_mood = app.state.mood
                    app.cycle_pose_or_mode()
                    self.assertNotEqual(app.state.mood, prev_mood)

                    # Spawn and claim treat
                    treat = app.state.spawn_treat("five")
                    app._claim_treat(100.0, 80.0)
                    self.assertIsNone(app.state.active_treat)
                    self.assertGreaterEqual(app.state.pets_count, 1 + treat.bonus)

                    # Spawn and answer math micro-quiz
                    quiz = app.state.spawn_quiz(0)
                    app._sync_quiz_banner()
                    app._answer_quiz(quiz.correct_index)
                    self.assertIsNone(app.state.active_quiz)
                    self.assertEqual(app.state.quizzes_solved, 1)

                    # Custom photo import + fallback back to Sayan poses
                    sample_img = Path(tmp) / "custom.jpg"
                    Image.new("RGB", (320, 240), (200, 140, 110)).save(sample_img)
                    with mock.patch(
                        "src.ui_qt.QFileDialog.getOpenFileName",
                        return_value=(str(sample_img), "Изображения"),
                    ):
                        app.choose_custom_photo()
                    self.assertEqual(app.state.active_photo_mode, "custom")
                    self.assertIsNotNone(app.state.custom_photo_path)

                    app.cycle_pose_or_mode()
                    self.assertEqual(app.state.active_photo_mode, "auto")

                    # Render passes should succeed without errors
                    app.resize(460, 720)
                    app.stage.resize(380, 280)
                    self.assertFalse(app.grab().isNull())
                    self.assertFalse(app.stage.grab().isNull())
                finally:
                    app.on_close()

                save_file = Path(tmp) / "SayanClicker" / "save.json"
                self.assertTrue(save_file.is_file())


if __name__ == "__main__":
    unittest.main()