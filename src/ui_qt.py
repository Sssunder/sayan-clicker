"""Apple-style Qt UI for Sayan Clicker: 60 FPS stage, spring motion, soft cards."""

from __future__ import annotations

import math
import random
import sys
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QSize, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QImage,
    QPainter,
    QPixmap,
    QTransform,
    QShortcut,
    QKeySequence,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .audio import SoundEngine
from .game_state import (
    CUSTOM_MOOD,
    SPRITE_MOODS,
    EventClaimResult,
    PetResult,
    QuizAnswerResult,
    SayanGameState,
)
from .paths import get_resource_path
from .sprites import create_soft_shadow, prepare_sprite_rgba
from .storage import import_custom_photo, load_config, save_config
from .theme import ThemePalette, get_theme

BASE_NORMAL_WIDTH = 460
BASE_NORMAL_HEIGHT = 720
BASE_COMPACT_WIDTH = 300
BASE_COMPACT_HEIGHT = 400
SPRITE_BOX = 560
TICK_MS = 16
SAVE_DEBOUNCE_SECONDS = 2.0


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    rgba = img.convert("RGBA")
    data = rgba.tobytes()
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


class Spring:
    """Interruptible, velocity-aware spring (Apple damping/response parameters)."""

    __slots__ = ("value", "velocity", "target", "omega", "zeta")

    def __init__(self, value: float = 0.0, response: float = 0.35, damping: float = 1.0):
        self.value = value
        self.velocity = 0.0
        self.target = value
        self.omega = 2.0 * math.pi / response
        self.zeta = damping

    def kick(self, velocity: float) -> None:
        self.velocity += velocity

    def step(self, dt: float) -> None:
        accel = -self.omega * self.omega * (self.value - self.target)
        accel -= 2.0 * self.zeta * self.omega * self.velocity
        self.velocity += accel * dt
        self.value += self.velocity * dt


@dataclass
class FloatingText:
    x: float
    y: float
    vy: float
    text: str
    color: str
    size: int
    born_at: float
    lifetime: float


class PillButton(QWidget):
    """Rounded pill with instant press-down spring feedback."""

    clicked = Signal()

    def __init__(self, app: "SayanClickerApp", text: str, role: str = "neutral", checkable: bool = False):
        super().__init__()
        self._app = app
        self._text = text
        self._role = role
        self._checkable = checkable
        self._checked = False
        self._hover = False
        self._press = Spring(response=0.22, damping=1.0)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)
        app._buttons.append(self)

    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        if text != self._text:
            self._text = text
            self.updateGeometry()
            self.update()

    def set_checked(self, on: bool) -> None:
        self._checked = on
        self.update()

    def isChecked(self) -> bool:
        return self._checked

    def sizeHint(self):
        fm = QFontMetrics(self._app.ui_font(10, "demibold"))
        return QSize(fm.horizontalAdvance(self._text) + 26, 30)

    def enterEvent(self, ev) -> None:
        self._hover = True
        self.update()

    def leaveEvent(self, ev) -> None:
        self._hover = False
        self.update()

    def mousePressEvent(self, ev) -> None:
        self._press.target = 1.0
        self.update()

    def mouseReleaseEvent(self, ev) -> None:
        self._press.target = 0.0
        if self.rect().contains(ev.position().toPoint()):
            if self._checkable:
                self._checked = not self._checked
            self.clicked.emit()
        self.update()

    def paintEvent(self, ev) -> None:
        t = self._app.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = 1.0 - 0.05 * min(1.0, max(0.0, self._press.value))
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(s, s)
        p.translate(-self.width() / 2, -self.height() / 2)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self._checked:
            fill, fg = t.accent, t.accent_text
        elif self._role == "accent":
            fill = t.bg_pill_hover if self._hover else t.bg_pill
            fg = t.accent
        else:
            fill = t.bg_control_hover if self._hover else t.bg_control
            fg = t.text_heading
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(fill))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(QColor(fg))
        p.setFont(self._app.ui_font(10, "demibold"))
        p.drawText(r, Qt.AlignCenter, self._text)


class Card(QFrame):
    """Soft rounded card with hairline border and ambient shadow."""

    def __init__(self, app: "SayanClickerApp", radius: int = 16, shadow: bool = True):
        super().__init__()
        self._app = app
        self._radius = radius
        # QGraphicsDropShadowEffect crashes the offscreen QPA plugin (headless tests).
        # The stats card repaints every tick (animated score), so a live blur there
        # costs a re-blur per frame; give it a flat hairline card instead.
        if shadow and QApplication.platformName() != "offscreen":
            shadow_eff = QGraphicsDropShadowEffect(self)
            shadow_eff.setBlurRadius(22)
            shadow_eff.setOffset(0, 5)
            shadow_eff.setColor(QColor(0, 0, 0, 26))
            self.setGraphicsEffect(shadow_eff)

    def paintEvent(self, ev) -> None:
        t = self._app.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        p.setPen(QColor(t.border))
        p.setBrush(QColor(t.bg_card))
        p.drawRoundedRect(r, self._radius, self._radius)


class BarWidget(QWidget):
    def __init__(self, app: "SayanClickerApp"):
        super().__init__()
        self._app = app
        self.ratio = 0.0
        self._shown = 0.0
        self.setFixedHeight(6)

    def step(self, dt: float) -> None:
        self._shown += (self.ratio - self._shown) * min(1.0, dt * 10)
        self.update()

    def paintEvent(self, ev) -> None:
        t = self._app.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t.bg_control))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 3, 3)
        w = max(6.0 if self._shown > 0 else 0.0, self.width() * min(1.0, self._shown))
        if w > 0:
            color = t.gold if self._app.state.is_zoomies_active() else t.accent
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(0, 0, w, self.height()), 3, 3)


class ComboPill(QWidget):
    def __init__(self, app: "SayanClickerApp"):
        super().__init__()
        self._app = app
        self._text = "Комбо x1"
        self._mode = "idle"
        self.pulse = Spring(response=0.3, damping=0.6)
        self.setFixedHeight(26)

    def set_state(self, text: str, mode: str) -> None:
        if text != self._text or mode != self._mode:
            self._text = text
            self._mode = mode
            self.pulse.kick(3.0)
            self.update()

    def sizeHint(self):
        fm = QFontMetrics(self._app.ui_font(9, "demibold"))
        return QSize(fm.horizontalAdvance(self._text) + 20, 26)

    def paintEvent(self, ev) -> None:
        t = self._app.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = 1.0 + 0.06 * max(0.0, self.pulse.value)
        p.translate(self.width() / 2, self.height() / 2)
        p.scale(s, s)
        p.translate(-self.width() / 2, -self.height() / 2)
        r = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        if self._mode == "zoomies":
            fill, fg = t.gold_light, t.gold
        elif self._mode == "combo":
            fill, fg = t.bg_pill, t.accent
        else:
            fill, fg = t.bg_control, t.text_muted
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(fill))
        p.drawRoundedRect(r, r.height() / 2, r.height() / 2)
        p.setPen(QColor(fg))
        p.setFont(self._app.ui_font(9, "demibold"))
        p.drawText(r, Qt.AlignCenter, self._text)


class Stage(QWidget):
    """60 FPS painted stage: halo, shadow, spring-squashed sprite, inscriptions."""

    def __init__(self, app: "SayanClickerApp"):
        super().__init__()
        self._app = app
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumHeight(180)
        self.setCursor(Qt.PointingHandCursor)
        self._shadow_pix: QPixmap | None = None
        self._shadow_key: tuple[int, int, str] | None = None
        self._treat_hitbox: tuple[float, float, float] | None = None

    def mousePressEvent(self, ev) -> None:
        pos = ev.position()
        if self._treat_hitbox is not None and self._app.state.active_treat is not None:
            tx, ty, r = self._treat_hitbox
            if math.hypot(pos.x() - tx, pos.y() - ty) <= r + 10:
                self._app._claim_treat(pos.x(), pos.y())
                return
        self._app._perform_pet(pos.x(), pos.y())

    def paintEvent(self, ev) -> None:
        app = self._app
        w, h = self.width(), self.height()
        if w < 40 or h < 40:
            return
        now = time.monotonic()
        t = app.theme
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing | QPainter.SmoothPixmapTransform | QPainter.TextAntialiasing)

        base = min(w, h) * (0.84 if app.compact_mode else 0.86)
        cx, cy = w / 2.0, h / 2.0 + 4.0
        q = max(-1.2, min(1.2, app._squash.value))
        zoomies = app.state.is_zoomies_active(now)
        if zoomies:
            angle = 6.0 * math.sin(now * 5.0)
            bob = -5.0 * abs(math.sin(now * 11.0))
            margin = base * 0.5 + 8.0
            usable = w - 2.0 * margin
            if usable > 40.0:
                cx = margin + usable * (0.5 + 0.5 * math.sin(now * 2.2))
            sx, sy = 1.0, 1.0
        elif app.state.is_sleeping():
            breath = math.sin(now * 1.4)
            angle = 0.0
            bob = 2.0 * breath
            sx, sy = 1.0 + 0.012 * breath + 0.14 * q, 1.0 - 0.010 * breath - 0.13 * q
        else:
            breath = math.sin(now * 2.4)
            angle = 0.0
            bob = -3.0 * breath
            sx, sy = 1.0 + 0.012 * breath + 0.14 * q, 1.0 + 0.016 * breath - 0.13 * q

        halo_r = min(w, h) * 0.42
        grad = QRadialGradient(QPointF(cx, cy), halo_r)
        c0 = QColor(t.stage_halo)
        c1 = QColor(t.stage_halo)
        c1.setAlpha(0)
        grad.setColorAt(0.0, c0)
        grad.setColorAt(0.75, c0)
        grad.setColorAt(1.0, c1)
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QPointF(cx, cy), halo_r, halo_r * 0.92)
        ring = QColor(t.stage_ring)
        ring.setAlpha(140)
        p.setPen(ring)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(cx, cy), halo_r * 0.98, halo_r * 0.90)

        shadow_w = max(80, int(min(w, h) * 0.54))
        shadow_w -= shadow_w % 8
        shadow_h = max(18, int(shadow_w * 0.22))
        shadow_key = (shadow_w, shadow_h, t.key)
        if self._shadow_key != shadow_key or self._shadow_pix is None:
            self._shadow_pix = pil_to_pixmap(
                create_soft_shadow(shadow_w, shadow_h, alpha_max=40 if t.key == "cozy" else 75)
            )
            self._shadow_key = shadow_key
        p.drawPixmap(QPointF(cx - shadow_w / 2, cy + min(w, h) * 0.34 - shadow_h / 2), self._shadow_pix)

        pix = app._sprite_pixmap()
        kx = base * sx / SPRITE_BOX
        ky = base * sy / SPRITE_BOX
        tr = QTransform().translate(cx, cy - 4 + bob).rotate(angle).scale(kx, ky).translate(-SPRITE_BOX / 2, -SPRITE_BOX / 2)
        p.setTransform(tr)
        p.drawPixmap(0, 0, pix)
        p.resetTransform()

        treat = app.state.active_treat
        if treat is not None and not treat.is_expired(now):
            age = now - treat.spawned_at
            tx = cx + math.sin(age * 2.4) * (w * 0.28)
            ty = cy - halo_r * 0.56 + math.cos(age * 3.1) * 14.0
            r = 24 if app.compact_mode else 28
            self._treat_hitbox = (tx, ty, float(r))
            g2 = QRadialGradient(QPointF(tx - r * 0.3, ty - r * 0.3), r * 1.6)
            g2.setColorAt(0.0, QColor("#FFFFFF"))
            g2.setColorAt(1.0, QColor(t.gold_light))
            p.setPen(QColor(t.gold))
            p.setBrush(g2)
            p.drawEllipse(QPointF(tx, ty), r + 3, r + 3)
            p.setFont(app.emoji_font(14 if app.compact_mode else 16))
            p.setPen(QColor(t.text_heading))
            p.drawText(QRectF(tx - r, ty - r - 4, 2 * r, 2 * r), Qt.AlignCenter, treat.emoji)
            p.setFont(app.ui_font(9, "demibold"))
            p.setPen(QColor(t.gold))
            p.drawText(QRectF(tx - r, ty + 8, 2 * r, 16), Qt.AlignCenter, f"+{treat.bonus}")
        else:
            self._treat_hitbox = None

        for ft in app._particles:
            age = now - ft.born_at
            if age >= ft.lifetime:
                continue
            k = age / ft.lifetime
            alpha = 1.0 - k * k
            p.setOpacity(alpha)
            p.setPen(QColor(ft.color))
            p.setFont(app.ui_font(ft.size, "bold"))
            y = ft.y + ft.vy * age
            p.drawText(QRectF(ft.x - 90, y - 14, 180, 28), Qt.AlignCenter, ft.text)
        p.setOpacity(1.0)

        caption = app._mood_russian_label()
        fm = app.ui_font(9, "demibold")
        cw_ = QFontMetrics(fm).horizontalAdvance(caption) + 24
        cr = QRectF(w / 2 - cw_ / 2, h - 30, cw_, 22)
        cap_fill = QColor(t.bg_card)
        cap_fill.setAlpha(210)
        p.setPen(Qt.NoPen)
        p.setBrush(cap_fill)
        p.drawRoundedRect(cr, 11, 11)
        p.setPen(QColor(t.text_muted))
        p.setFont(fm)
        p.drawText(cr, Qt.AlignCenter, caption)

        if app.state.session_clicks == 0 and not app.compact_mode:
            p.setPen(QColor(t.text_muted))
            p.setFont(app.ui_font(8))
            p.drawText(QRectF(0, 4, w, 18), Qt.AlignCenter, "Кликни по Саяну или нажми Пробел, чтобы погладить")


class SayanClickerApp(QWidget):
    def __init__(self) -> None:
        super().__init__()
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.winmm.timeBeginPeriod(1)
            except Exception:
                pass
        self.config = load_config()
        self.state = SayanGameState.from_config(self.config)
        self.theme: ThemePalette = get_theme(self.config.get("theme", "cozy"))
        self.always_on_top = bool(self.config.get("always_on_top", False))
        self.compact_mode = bool(self.config.get("compact_mode", False))

        self.sound = SoundEngine(
            sounds_dir=get_resource_path("assets/sounds"),
            enabled=bool(self.config.get("sound_enabled", True)),
        )

        self._sprites_rgba: dict[str, Image.Image] = {}
        self._sprite_pix: dict[str, QPixmap] = {}
        self._load_sprites()

        self._particles: list[FloatingText] = []
        self._squash = Spring(response=0.32, damping=0.55)
        self._buttons: list[PillButton] = []
        self._fonts: dict[tuple[int, str], QFont] = {}
        self._shown_score = float(self.state.pets_count)
        self._last_score_int = -1
        self._rng = random.Random()
        self._last_zzz_at = 0.0
        self._closing = False
        self._tick_errors = 0
        self._last_save_at = time.monotonic()
        self._dirty_save = False
        self._save_cond = threading.Condition()
        self._save_pending: dict[str, Any] | None = None
        self._save_stop = False
        self._save_thread = threading.Thread(target=self._save_worker, daemon=True)
        self._save_thread.start()
        self._drag_offset = None

        self._build_ui()
        self._apply_mode_layout()
        self._refresh_all_labels()
        self._restore_window_placement()

        QShortcut(QKeySequence(Qt.Key_Space), self, activated=self._hotkey_pet)
        QShortcut(QKeySequence(Qt.Key_Return), self, activated=self._hotkey_pet)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(TICK_MS)

    # --- fonts / sprites ---

    def ui_font(self, size: int, weight: str = "regular") -> QFont:
        key = (size, weight)
        f = self._fonts.get(key)
        if f is None:
            primary = "Segoe UI Variable Text" if weight == "regular" else "Segoe UI"
            f = QFont(primary, size)
            f.setFamilies([primary, "Segoe UI Emoji"])
            if weight == "bold":
                f.setWeight(QFont.Bold)
            elif weight == "demibold":
                f.setWeight(QFont.DemiBold)
            if size >= 20:
                f.setLetterSpacing(QFont.AbsoluteSpacing, -0.6)
            self._fonts[key] = f
        return f

    def emoji_font(self, size: int) -> QFont:
        return QFont("Segoe UI Emoji", size)

    def _load_sprites(self) -> None:
        for mood in SPRITE_MOODS:
            path = get_resource_path(f"assets/sprites/{mood}.png")
            if path.is_file():
                try:
                    self._sprites_rgba[mood] = prepare_sprite_rgba(path, box_size=SPRITE_BOX)
                except Exception:
                    continue
        if "curious" not in self._sprites_rgba:
            self._sprites_rgba["curious"] = Image.new("RGBA", (SPRITE_BOX, SPRITE_BOX), (255, 122, 80, 200))
        custom = self.state.custom_photo_path
        if custom and Path(custom).is_file():
            try:
                self._sprites_rgba[CUSTOM_MOOD] = prepare_sprite_rgba(Path(custom), box_size=SPRITE_BOX)
            except Exception:
                pass
        elif self.state.active_photo_mode == "custom":
            self.state.set_photo_mode("auto")
        for key, rgba in self._sprites_rgba.items():
            self._sprite_pix[key] = pil_to_pixmap(rgba)

    def _sprite_pixmap(self) -> QPixmap:
        key = self.state.get_effective_sprite()
        if key not in self._sprite_pix:
            rgba = self._sprites_rgba.get(key) or self._sprites_rgba["curious"]
            self._sprite_pix[key] = pil_to_pixmap(rgba)
        return self._sprite_pix[key]

    # --- UI construction ---

    def _build_ui(self) -> None:
        self.setWindowTitle("Кот Саян — Уютный кликер")
        ico = get_resource_path("assets/sayan_icon.ico")
        if ico.is_file():
            self.setWindowIcon(QIcon(str(ico)))

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 10, 14, 12)
        root.setSpacing(10)

        header = QWidget()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(2, 0, 2, 0)
        hl.setSpacing(6)
        self.title_label = QLabel("🐾 Кот Саян")
        self.title_label.setFont(self.ui_font(13, "demibold"))
        hl.addWidget(self.title_label)
        hl.addStretch(1)
        self.sound_btn = PillButton(self, "🔊", checkable=True)
        self.sound_btn.clicked.connect(self.toggle_sound)
        self.topmost_btn = PillButton(self, "📌 Поверх", checkable=True)
        self.topmost_btn.clicked.connect(self.toggle_always_on_top)
        self.compact_btn = PillButton(self, "🪟 Компакт")
        self.compact_btn.clicked.connect(self.toggle_compact_mode)
        for b in (self.sound_btn, self.topmost_btn, self.compact_btn):
            hl.addWidget(b)
        header.mousePressEvent = self._header_press
        header.mouseMoveEvent = self._header_move
        root.addWidget(header)
        self._header = header

        self.bubble_card = Card(self)
        bl = QVBoxLayout(self.bubble_card)
        bl.setContentsMargins(14, 10, 14, 10)
        self.bubble_label = QLabel(self.state.current_quote)
        self.bubble_label.setWordWrap(True)
        self.bubble_label.setFont(self.ui_font(10, "demibold"))
        bl.addWidget(self.bubble_label)
        root.addWidget(self.bubble_card)

        self.stage = Stage(self)
        root.addWidget(self.stage, 1)

        self.quiz_card = Card(self)
        ql = QVBoxLayout(self.quiz_card)
        ql.setContentsMargins(14, 10, 14, 12)
        ql.setSpacing(8)
        qhead = QHBoxLayout()
        self.quiz_title = QLabel("📐 Быстрая задачка на +30 лапок")
        self.quiz_title.setFont(self.ui_font(9, "demibold"))
        qhead.addWidget(self.quiz_title)
        qhead.addStretch(1)
        self.quiz_close = PillButton(self, "✕")
        self.quiz_close.clicked.connect(self._dismiss_quiz)
        qhead.addWidget(self.quiz_close)
        ql.addLayout(qhead)
        self.quiz_question = QLabel("")
        self.quiz_question.setWordWrap(True)
        self.quiz_question.setFont(self.ui_font(11, "bold"))
        ql.addWidget(self.quiz_question)
        qrow = QHBoxLayout()
        qrow.setSpacing(6)
        self.quiz_btns = []
        for i in range(3):
            b = PillButton(self, "", role="accent")
            b.clicked.connect(lambda i=i: self._answer_quiz(i))
            qrow.addWidget(b, 1)
            self.quiz_btns.append(b)
        ql.addLayout(qrow)
        root.addWidget(self.quiz_card)
        self.quiz_card.hide()

        self.stats_card = Card(self, shadow=False)
        sl = QVBoxLayout(self.stats_card)
        sl.setContentsMargins(14, 12, 14, 12)
        sl.setSpacing(8)
        score_row = QHBoxLayout()
        self.score_label = QLabel("0")
        self.score_label.setFont(self.ui_font(26, "bold"))
        score_row.addWidget(self.score_label)
        self.paws_caption = QLabel("лапок")
        self.paws_caption.setFont(self.ui_font(10, "demibold"))
        score_row.addWidget(self.paws_caption)
        score_row.addStretch(1)
        self.combo_pill = ComboPill(self)
        score_row.addWidget(self.combo_pill)
        sl.addLayout(score_row)

        self.details = QWidget()
        dl = QVBoxLayout(self.details)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(6)
        lvl_row = QHBoxLayout()
        self.level_lbl = QLabel("Ур. 1 • Котёнок-первоклассник")
        self.level_lbl.setFont(self.ui_font(9, "demibold"))
        lvl_row.addWidget(self.level_lbl)
        lvl_row.addStretch(1)
        self.level_next_lbl = QLabel("0 / 25")
        self.level_next_lbl.setFont(self.ui_font(8, "demibold"))
        lvl_row.addWidget(self.level_next_lbl)
        dl.addLayout(lvl_row)
        self.level_bar = BarWidget(self)
        dl.addWidget(self.level_bar)
        energy_row = QHBoxLayout()
        self.energy_lbl = QLabel("⚡ Тыгыдык: 0%")
        self.energy_lbl.setFont(self.ui_font(8, "demibold"))
        energy_row.addWidget(self.energy_lbl)
        energy_row.addStretch(1)
        self.mood_lbl = QLabel("")
        self.mood_lbl.setFont(self.ui_font(8))
        energy_row.addWidget(self.mood_lbl)
        dl.addLayout(energy_row)
        sl.addWidget(self.details)
        root.addWidget(self.stats_card)

        footer = QHBoxLayout()
        footer.setSpacing(6)
        self.photo_btn = PillButton(self, "📷 Своё фото")
        self.photo_btn.clicked.connect(self.choose_custom_photo)
        self.pose_btn = PillButton(self, "🎭 Сменить позу")
        self.pose_btn.clicked.connect(self.cycle_pose_or_mode)
        self.theme_btn = PillButton(self, "🌙 Кибер-Кот")
        self.theme_btn.clicked.connect(self.toggle_theme)
        for b in (self.photo_btn, self.pose_btn, self.theme_btn):
            footer.addWidget(b, 1)
        root.addLayout(footer)
        self._footer = footer

    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(self.theme.bg_page))

    def _header_press(self, ev) -> None:
        self._drag_offset = ev.globalPosition().toPoint() - self.pos()

    def _header_move(self, ev) -> None:
        if self._drag_offset is not None:
            self.move(ev.globalPosition().toPoint() - self._drag_offset)
            self._dirty_save = True

    def _restore_window_placement(self) -> None:
        if self.always_on_top:
            self._apply_topmost()
        x, y = self.config.get("window_x"), self.config.get("window_y")
        if not (isinstance(x, int) and isinstance(y, int)):
            return
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        avail = screen.availableGeometry()
        x = max(avail.x(), min(x, avail.right() - self.width()))
        y = max(avail.y(), min(y, avail.bottom() - self.height()))
        self.move(x, y)

    # --- layout / theme ---

    def _apply_mode_layout(self) -> None:
        if self.compact_mode:
            self.setFixedSize(BASE_COMPACT_WIDTH, BASE_COMPACT_HEIGHT)
            self.title_label.hide()
            self.details.hide()
            for i in range(self._footer.count()):
                w = self._footer.itemAt(i).widget()
                if w:
                    w.hide()
            self.bubble_label.setFont(self.ui_font(8, "demibold"))
            self.score_label.setFont(self.ui_font(18, "bold"))
            self.compact_btn.set_text("⛶")
            self.topmost_btn.set_text("📌")
        else:
            self.setFixedSize(BASE_NORMAL_WIDTH, BASE_NORMAL_HEIGHT)
            self.title_label.show()
            self.details.show()
            for i in range(self._footer.count()):
                w = self._footer.itemAt(i).widget()
                if w:
                    w.show()
            self.bubble_label.setFont(self.ui_font(10, "demibold"))
            self.score_label.setFont(self.ui_font(26, "bold"))
            self.compact_btn.set_text("🪟 Компакт")
            self.topmost_btn.set_text("📌 Поверх")
        self._sync_quiz_banner()
        self._apply_theme_colors()

    def _apply_theme_colors(self) -> None:
        t = self.theme
        self.title_label.setStyleSheet(f"color:{t.text_heading};")
        self.bubble_label.setStyleSheet(f"color:{t.text_heading};")
        self.score_label.setStyleSheet(f"color:{t.text_heading};")
        self.paws_caption.setStyleSheet(f"color:{t.text_muted};")
        self.level_lbl.setStyleSheet(f"color:{t.sage};")
        self.level_next_lbl.setStyleSheet(f"color:{t.text_muted};")
        self.energy_lbl.setStyleSheet(f"color:{t.gold};")
        self.mood_lbl.setStyleSheet(f"color:{t.text_muted};")
        self.quiz_title.setStyleSheet(f"color:{t.sage};")
        self.quiz_question.setStyleSheet(f"color:{t.text_heading};")
        self.theme_btn.set_text("☀️ Уютный" if t.key == "cyber" else "🌙 Кибер-Кот")
        self.sound_btn.set_checked(self.sound.enabled)
        self.topmost_btn.set_checked(self.always_on_top)
        self.update()
        for w in self.findChildren(QWidget):
            w.update()

    # --- labels ---

    def _mood_russian_label(self) -> str:
        if self.state.active_photo_mode == "custom" and self.state.custom_photo_path:
            return "Своё фото 📷"
        mapping = {
            "curious": "Любопытный 👀",
            "window": "Наблюдатель 🌤️",
            "stretch": "Довольный «Усям!» 😻",
            "ambush": "Хитрый контролёр 🐾",
            "sleep_sunset": "Дремлет на закате 💤",
            "sleep_rug": "Спит на коврике 💤",
            "sleep_chair": "Спит в кресле 🐾💤",
            "sleep_cozy": "Сладкий сон 😴",
            "zoomies": "ТЫГЫДЫК-ТУРБО! ⚡",
            "photo_window": "На подоконнике 📷",
            "photo_cuddle": "Обнимашки 📷💖",
            "photo_sink": "В раковине 📷",
            "photo_chair": "Спит на кресле 📷💤",
            "photo_armchair": "Спит в кресле 📷💤",
            "photo_nap": "Дремлет на коврике 📷💤",
            "photo_sofa": "Спит на диване 📷💤",
            "photo_sill_nap": "Спит на подоконнике 📷💤",
            "photo_stretch_nap": "Спит потянувшись 📷💤",
            "photo_sprawl": "Разморился во сне 📷💤",
        }
        return mapping.get(self.state.mood, "Уютный Саян")

    @staticmethod
    def _plural_paws(n: int) -> str:
        mod100, mod10 = n % 100, n % 10
        if 11 <= mod100 <= 14:
            return "лапок"
        if mod10 == 1:
            return "лапка"
        if 2 <= mod10 <= 4:
            return "лапки"
        return "лапок"

    def _refresh_all_labels(self) -> None:
        count = self.state.pets_count
        self.paws_caption.setText(self._plural_paws(count))
        zoomies = self.state.is_zoomies_active()
        mult = max(1, 3 if zoomies else (5 if self.state.combo_streak >= 25 else 3 if self.state.combo_streak >= 12 else 2 if self.state.combo_streak >= 5 else 1))
        if zoomies:
            rem = max(1, int(math.ceil(self.state.zoomies_remaining())))
            self.combo_pill.set_state(f"⚡ x{mult} ({rem}с)", "zoomies")
        elif self.state.combo_streak >= 5:
            self.combo_pill.set_state(f"🔥 x{mult} ({self.state.combo_streak})", "combo")
        else:
            self.combo_pill.set_state(f"Комбо x{mult}", "idle")
        lvl = self.state.get_level_info()
        self.level_lbl.setText(f"Ур. {lvl.index} • {lvl.title}")
        self.level_next_lbl.setText(f"{count} / {lvl.next_threshold}" if lvl.next_threshold is not None else "МАКС ★")
        self.level_bar.ratio = lvl.progress_ratio
        self.energy_lbl.setText("⚡ ТЫГЫДЫК АКТИВЕН!" if zoomies else f"⚡ Тыгыдык: {self.state.purr_energy}%")
        self.mood_lbl.setText(self._mood_russian_label())
        self.bubble_label.setText(self.state.current_quote)
        self.pose_btn.set_text("🐱 Вернуть Саяна" if self.state.active_photo_mode == "custom" else "🎭 Сменить позу")
        self.sound_btn.set_text("🔊" if self.sound.enabled else "🔇")

    def _sync_quiz_banner(self) -> None:
        quiz = self.state.active_quiz
        if quiz is None or self.compact_mode:
            self.quiz_card.hide()
            return
        self.quiz_question.setText(quiz.question)
        for i, b in enumerate(self.quiz_btns):
            b.set_text(quiz.options[i])
        self.quiz_card.show()

    # --- interactions ---

    def _hotkey_pet(self) -> None:
        self._perform_pet(self.stage.width() / 2, self.stage.height() / 2)

    def _perform_pet(self, x: float, y: float) -> None:
        now = time.monotonic()
        res: PetResult = self.state.pet(now=now)
        self._squash.kick(4.5)
        self._dirty_save = True

        if res.zoomies_started:
            self.sound.play("zoomies", cooldown_ms=120)
        elif res.level_up is not None or res.new_milestones:
            self.sound.play("levelup", cooldown_ms=150)
        elif res.woke_up or res.combo_streak % 8 == 0:
            self.sound.play(random.choice(("meow", "meow2")), cooldown_ms=180)
        elif res.combo_streak >= 6:
            self.sound.play(random.choice(("meow", "meow2")), cooldown_ms=200)
        else:
            # Quiet paw taps dominate; a soft mew now and then keeps it alive.
            if random.random() < 0.14:
                self.sound.play(random.choice(("meow", "meow2")), cooldown_ms=160)
            else:
                self.sound.play(random.choice(("tap1", "tap2", "tap3")), cooldown_ms=70)

        self._spawn_pet_texts(x, y, res)
        self._sync_quiz_banner()
        self._refresh_all_labels()

    def _claim_treat(self, x: float, y: float) -> None:
        res: EventClaimResult = self.state.claim_treat()
        if not res.claimed:
            return
        self._squash.kick(3.5)
        self._dirty_save = True
        if res.level_up is not None or res.new_milestones:
            self.sound.play("levelup", cooldown_ms=100)
        else:
            self.sound.play("treat", cooldown_ms=80)
        self._spawn_burst(x, y, f"+{res.points_gained}", "ням!")
        self._refresh_all_labels()

    def _answer_quiz(self, i: int) -> None:
        if self.state.active_quiz is None:
            return
        res: QuizAnswerResult = self.state.answer_quiz(i)
        self._dirty_save = True
        if res.correct:
            self.sound.play("levelup", cooldown_ms=80)
            self._spawn_burst(self.stage.width() / 2, self.stage.height() * 0.45, f"+{res.points_gained}", "пятёрка!")
        else:
            self.sound.play("meow", cooldown_ms=80)
        self._sync_quiz_banner()
        self._refresh_all_labels()

    def _dismiss_quiz(self) -> None:
        self.state.dismiss_quiz()
        self._sync_quiz_banner()

    def _spawn_pet_texts(self, x: float, y: float, res: PetResult) -> None:
        now = time.monotonic()
        self._particles.append(FloatingText(
            x=x, y=y - 12, vy=-64.0, text=f"+{res.points_gained}",
            color=self.theme.gold if res.zoomies_active or res.multiplier >= 3 else self.theme.accent,
            size=16 if res.multiplier >= 3 else 14, born_at=now, lifetime=0.9,
        ))
        word = None
        if res.zoomies_started:
            word = "ТЫГЫДЫК!"
        elif res.level_up is not None:
            word = "НОВЫЙ УРОВЕНЬ!"
        elif res.woke_up:
            word = "ПРОСНУЛСЯ!"
        elif self._rng.random() < 0.3:
            word = self._rng.choice(("мяу!", "мур-р-р!", "ещё!", "кайф!", "усям!"))
        if word:
            self._particles.append(FloatingText(
                x=x, y=y - 34, vy=-46.0, text=word, color=self.theme.text_heading,
                size=13, born_at=now, lifetime=1.0,
            ))
        self._particles = self._particles[-10:]

    def _spawn_burst(self, x: float, y: float, headline: str, word: str | None = None) -> None:
        now = time.monotonic()
        self._particles.append(FloatingText(x=x, y=y - 10, vy=-70.0, text=headline, color=self.theme.gold, size=16, born_at=now, lifetime=1.1))
        if word:
            self._particles.append(FloatingText(x=x, y=y - 32, vy=-50.0, text=word, color=self.theme.text_heading, size=13, born_at=now, lifetime=1.1))
        self._particles = self._particles[-10:]

    # --- toggles ---

    def toggle_sound(self) -> None:
        self.sound.set_enabled(not self.sound.enabled)
        if self.sound.enabled:
            self.sound.play("treat", cooldown_ms=50)
        self._dirty_save = True
        self._refresh_all_labels()

    def toggle_always_on_top(self) -> None:
        self.always_on_top = not self.always_on_top
        self._apply_topmost()
        self._dirty_save = True
        self._apply_theme_colors()

    def _apply_topmost(self) -> None:
        if QApplication.platformName() == "offscreen":
            return
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = int(self.winId())
                insert_after = -1 if self.always_on_top else -2
                flags = 0x2 | 0x1 | 0x10  # NOMOVE | NOSIZE | NOACTIVATE
                if ctypes.windll.user32.SetWindowPos(hwnd, insert_after, 0, 0, 0, 0, flags):
                    return
            except Exception:
                pass
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.always_on_top)
        self.show()

    def toggle_compact_mode(self) -> None:
        self.compact_mode = not self.compact_mode
        self._dirty_save = True
        self._apply_mode_layout()
        self._refresh_all_labels()

    def toggle_theme(self) -> None:
        self.theme = get_theme("cyber" if self.theme.key == "cozy" else "cozy")
        self._dirty_save = True
        self._apply_theme_colors()
        self._refresh_all_labels()

    def choose_custom_photo(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выбери фото Саяна или своего котика", "",
            "Изображения (*.png *.jpg *.jpeg *.webp *.bmp);;Все файлы (*.*)",
        )
        if not file_path:
            return
        try:
            saved = import_custom_photo(file_path)
            self._sprites_rgba[CUSTOM_MOOD] = prepare_sprite_rgba(Path(saved), box_size=SPRITE_BOX)
            self._sprite_pix.pop(CUSTOM_MOOD, None)
            self.state.set_photo_mode("custom", custom_photo_path=saved)
            self.state.current_quote = "Новое фото загружено! Погладь меня скорей! 📷"
            self.sound.play("meow", cooldown_ms=80)
            self._dirty_save = True
            self._refresh_all_labels()
            self._persist_now()
        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Не удалось загрузить фото", f"Выбери корректный файл изображения.\n\nДетали: {exc}")

    def cycle_pose_or_mode(self) -> None:
        if self.state.active_photo_mode == "custom":
            self.state.set_photo_mode("auto")
            self.state.mood = "curious"
            self.state.current_quote = "Саян снова в деле со всеми позами и настроениями! 🐾"
        else:
            available = [m for m in SPRITE_MOODS if m in self._sprites_rgba] or ["curious"]
            try:
                idx = available.index(self.state.mood)
            except ValueError:
                idx = -1
            self.state.mood = available[(idx + 1) % len(available)]
            self.state._idle_anchor_at = time.monotonic()
            self.state.current_quote = f"Поза переключена: {self._mood_russian_label()}"
        self.sound.play(random.choice(("tap1", "tap2", "tap3")), cooldown_ms=100)
        self._squash.kick(3.0)
        self._dirty_save = True
        self._refresh_all_labels()

    # --- loop ---

    def _tick(self) -> None:
        if self._closing:
            return
        try:
            self._tick_body(time.monotonic())
        except Exception:
            self._tick_errors += 1
            if self._tick_errors <= 3:
                traceback.print_exc()

    def _tick_body(self, now: float) -> None:
        dt = 1.0 / 60.0
        tick_res = self.state.tick(now=now)
        if tick_res.entered_sleep or tick_res.zoomies_ended or tick_res.treat_expired or tick_res.spawned_treat:
            self._refresh_all_labels()
            if tick_res.entered_sleep:
                self._dirty_save = True

        if self.state.is_sleeping() and (now - self._last_zzz_at) >= 2.2:
            self._last_zzz_at = now
            self._particles.append(FloatingText(
                x=self.stage.width() * 0.62, y=self.stage.height() * 0.28, vy=-28.0,
                text="Zzz", color=self.theme.text_muted, size=12, born_at=now, lifetime=1.6,
            ))

        self._squash.step(dt)
        for b in self._buttons:
            b._press.step(dt)
        self.combo_pill.pulse.step(dt)
        self.level_bar.step(dt)

        target = float(self.state.pets_count)
        self._shown_score += (target - self._shown_score) * min(1.0, dt * 12)
        shown = int(round(self._shown_score))
        if shown != self._last_score_int:
            self._last_score_int = shown
            self.score_label.setText(str(shown))

        self._particles = [ft for ft in self._particles if now - ft.born_at < ft.lifetime]
        self.stage.update()

        if self._dirty_save and (now - self._last_save_at) >= SAVE_DEBOUNCE_SECONDS:
            self._persist_now()

    # --- persistence ---

    def _persist_now(self) -> None:
        payload = dict(self.config)
        payload.update(self.state.to_config_updates())
        payload.update({
            "sound_enabled": self.sound.enabled,
            "always_on_top": self.always_on_top,
            "compact_mode": self.compact_mode,
            "theme": self.theme.key,
        })
        payload["window_x"] = int(self.x())
        payload["window_y"] = int(self.y())
        self.config = payload
        self._last_save_at = time.monotonic()
        self._dirty_save = False
        with self._save_cond:
            self._save_pending = payload
            self._save_cond.notify()

    def _save_worker(self) -> None:
        while True:
            with self._save_cond:
                while self._save_pending is None and not self._save_stop:
                    self._save_cond.wait()
                if self._save_stop and self._save_pending is None:
                    return
                payload = self._save_pending
                self._save_pending = None
            try:
                save_config(payload)
            except OSError:
                pass

    def _flush_save(self) -> None:
        with self._save_cond:
            self._save_stop = True
            self._save_cond.notify()
        self._save_thread.join(timeout=3.0)

    def closeEvent(self, ev) -> None:
        self.on_close()
        ev.accept()

    def on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._timer.stop()
        self._persist_now()
        self._flush_save()
        self.sound.stop()
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass
        self.close()