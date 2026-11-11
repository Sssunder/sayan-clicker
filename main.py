"""Entry point for Sayan Clicker standalone Windows desktop app."""

from __future__ import annotations

import ctypes
import sys

from PySide6.QtWidgets import QApplication

from src.ui_qt import SayanClickerApp


def _enable_windows_appid() -> None:
    """Group the app under its own taskbar icon on Windows."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "MariaMath.SayanClicker.Desktop.1"
        )
    except Exception:
        pass


def main() -> None:
    _enable_windows_appid()
    app = QApplication(sys.argv)
    app.setApplicationName("Кот Саян")
    window = SayanClickerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()