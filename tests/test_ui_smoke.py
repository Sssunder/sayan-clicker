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
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QMessageBox

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

    def test_wrong_answer_shows_correct_and_explanation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                app = SayanClickerApp()
                try:
                    quiz = app.state.spawn_quiz(0)
                    app._sync_quiz_banner()
                    wrong = (quiz.correct_index + 1) % 3
                    app._answer_quiz(wrong)
                    self.assertIsNone(app.state.active_quiz)
                    self.assertFalse(app.quiz_feedback.isHidden())
                    self.assertIn("✓", app.quiz_btns[quiz.correct_index].text())
                    self.assertIn("✗", app.quiz_btns[wrong].text())
                    self.assertFalse(app.quiz_btns[wrong].isEnabled())
                    self.assertTrue(app._quiz_review_timer.isActive())
                    app._dismiss_quiz()
                    self.assertTrue(app.quiz_feedback.isHidden())
                    self.assertTrue(app.quiz_btns[wrong].isEnabled())
                    self.assertFalse(app._quiz_review_timer.isActive())
                finally:
                    app.on_close()

    def test_request_quiz_button_spawns_once_and_hides_in_compact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                app = SayanClickerApp()
                try:
                    self.assertIsNone(app.state.active_quiz)
                    self.assertFalse(app.quiz_request_btn.isHidden())
                    app.quiz_request_btn.clicked.emit()
                    quiz = app.state.active_quiz
                    self.assertIsNotNone(quiz)
                    self.assertFalse(app.quiz_card.isHidden())
                    app.quiz_request_btn.clicked.emit()
                    self.assertIs(app.state.active_quiz, quiz)
                    app.toggle_compact_mode()
                    self.assertFalse(app.quiz_request_btn.isHidden())
                    self.assertEqual(app.quiz_request_btn.text(), "📐")
                    app._request_quiz()
                    self.assertIs(app.state.active_quiz, quiz)
                    app.toggle_compact_mode()
                    self.assertEqual(app.quiz_request_btn.text(), "📐 Задачка")
                finally:
                    app.on_close()

    def test_compact_quiz_request_answer_and_fit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                app = SayanClickerApp()
                try:
                    app.toggle_compact_mode()
                    self.assertFalse(app.bubble_card.isHidden())
                    app._request_quiz()
                    quiz = app.state.active_quiz
                    self.assertIsNotNone(quiz)
                    self.assertFalse(app.quiz_card.isHidden())
                    self.assertTrue(app.bubble_card.isHidden())
                    app.grab()
                    self.assertTrue(app.stage.height() > 40)
                    self.assertGreaterEqual(app._header.geometry().y(), 0)
                    self.assertLessEqual(app.quiz_card.geometry().bottom(), app.height())
                    wrong = (quiz.correct_index + 1) % 3
                    app._answer_quiz(wrong)
                    self.assertFalse(app.quiz_feedback.isHidden())
                    app.grab()
                    self.assertGreaterEqual(app._header.geometry().y(), 0)
                    self.assertLessEqual(app.quiz_card.geometry().bottom(), app.height())
                    app._dismiss_quiz()
                    self.assertTrue(app.quiz_card.isHidden())
                    self.assertFalse(app.bubble_card.isHidden())
                finally:
                    app.on_close()

    def test_quiz_answer_hotkeys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                app = SayanClickerApp()
                try:
                    app.show()
                    app.activateWindow()
                    QApplication.processEvents()
                    quiz = app.state.spawn_quiz(0)
                    app._sync_quiz_banner()
                    QTest.keyClick(app, Qt.Key_1 + quiz.correct_index)
                    self.assertIsNone(app.state.active_quiz)
                    self.assertEqual(app.state.quizzes_solved, 1)
                    QTest.keyClick(app, Qt.Key_1)
                    self.assertEqual(app.state.quizzes_solved, 1)
                finally:
                    app.on_close()

    def test_solved_quiz_counter_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                app = SayanClickerApp()
                try:
                    self.assertEqual(app.solved_lbl.text(), "📐 0")
                    quiz = app.state.spawn_quiz(0)
                    app._answer_quiz(quiz.correct_index)
                    self.assertEqual(app.solved_lbl.text(), "📐 1")
                finally:
                    app.on_close()

    def test_reset_progress_keeps_name_and_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                app = SayanClickerApp()
                try:
                    for _ in range(5):
                        app._perform_pet(150.0, 140.0)
                    app.state.spawn_quiz(0)
                    app.config["player_name"] = "Аня"
                    with mock.patch(
                        "src.ui_qt.QMessageBox.question", return_value=QMessageBox.No
                    ):
                        app._confirm_reset()
                    self.assertGreater(app.state.pets_count, 0)
                    with mock.patch(
                        "src.ui_qt.QMessageBox.question", return_value=QMessageBox.Yes
                    ):
                        app._confirm_reset()
                    self.assertEqual(app.state.pets_count, 0)
                    self.assertEqual(app.state.quizzes_solved, 0)
                    self.assertIsNone(app.state.active_quiz)
                    self.assertEqual(app.config.get("player_name"), "Аня")
                    self.assertEqual(app.score_label.text(), "0")
                finally:
                    app.on_close()

    def test_rename_player_persists_and_signs_card(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                app = SayanClickerApp()
                try:
                    with mock.patch(
                        "src.ui_qt.QInputDialog.getText", return_value=("Аня", True)
                    ):
                        app._rename_player()
                    self.assertEqual(app.config.get("player_name"), "Аня")
                    self.assertIn("Аня", app.state.current_quote)
                    with mock.patch(
                        "src.ui_qt.QInputDialog.getText", return_value=("", False)
                    ):
                        app._rename_player()
                    self.assertEqual(app.config.get("player_name"), "Аня")
                    out = Path(tmp) / "cards"
                    path = app.export_card(out_dir=out, open_folder=False)
                    self.assertTrue(path.is_file())
                finally:
                    app.on_close()
                import json

                save = json.loads(
                    (Path(tmp) / "SayanClicker" / "save.json").read_text("utf-8")
                )
                self.assertEqual(save.get("player_name"), "Аня")

    def test_export_card_writes_shareable_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.dict(os.environ, {"APPDATA": tmp}):
                app = SayanClickerApp()
                try:
                    for _ in range(7):
                        app._perform_pet(150.0, 140.0)
                    out = Path(tmp) / "cards"
                    path = app.export_card(out_dir=out, open_folder=False)
                    self.assertTrue(path.is_file())
                    self.assertEqual(path.suffix, ".png")
                    self.assertGreater(path.stat().st_size, 10_000)
                    with Image.open(path) as im:
                        self.assertEqual(im.size, (1080, 1350))
                        self.assertEqual(im.format, "PNG")
                    # header share button present in both modes
                    self.assertIsNotNone(app.share_btn)
                    app.toggle_compact_mode()
                    self.assertIsNotNone(app.share_btn)
                finally:
                    app.on_close()


if __name__ == "__main__":
    unittest.main()