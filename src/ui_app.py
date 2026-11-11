"""Main desktop UI for Sayan Clicker built with Tkinter + Pillow Canvas."""

from __future__ import annotations

import ctypes
import math
import random
import sys
import threading
import time
import tkinter as tk
import traceback
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, font as tkfont, messagebox
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk

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
from .storage import import_custom_photo, load_config, save_config
from .theme import ThemePalette, get_theme

BASE_NORMAL_WIDTH = 456
BASE_NORMAL_HEIGHT = 710
BASE_COMPACT_WIDTH = 300
BASE_COMPACT_HEIGHT = 382

ANIM_INTERVAL_MS = 28  # ~35 FPS smooth canvas loop
SAVE_DEBOUNCE_SECONDS = 2.0
FRAME_CACHE_LIMIT = 32  # cached keyframe/rotation-strip PhotoImages
SPRITE_ANGLE_BUCKET = 2  # deg step for the zoomies rotation strip


@dataclass
class FloatingParticle:
    x: float
    y: float
    vx: float
    vy: float
    text: str
    color: str
    font_size: int
    born_at: float
    lifetime: float
    is_bold: bool = False


def _clamp_window_position(
    root: tk.Tk,
    width: int,
    height: int,
    x: int | None,
    y: int | None,
) -> tuple[int, int]:
    """Ensure restored window coordinates stay visible on screen."""
    screen_w = max(640, root.winfo_screenwidth())
    screen_h = max(480, root.winfo_screenheight())
    if x is None or y is None:
        return max(16, screen_w - width - 36), max(24, screen_h - height - 72)

    clamped_x = max(-width // 2, min(x, screen_w - max(120, width // 2)))
    clamped_y = max(0, min(y, screen_h - 90))
    return clamped_x, clamped_y


def _round_card_image(
    pil_img: Image.Image,
    target_box: int,
    radius: int = 28,
) -> Image.Image:
    """Fit an opaque user photo inside a crisp rounded square card with soft border."""
    contained = ImageOps.fit(
        pil_img.convert("RGBA"),
        (target_box, target_box),
        method=Image.Resampling.LANCZOS,
    )
    mask = Image.new("L", (target_box * 2, target_box * 2), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, target_box * 2 - 1, target_box * 2 - 1),
        radius=radius * 2,
        fill=255,
    )
    mask = mask.resize((target_box, target_box), Image.Resampling.LANCZOS)
    out = Image.new("RGBA", (target_box, target_box), (0, 0, 0, 0))
    out.paste(contained, (0, 0), mask)
    return out


def _prepare_sprite_rgba(path: Path, box_size: int = 320) -> Image.Image:
    """Load a sprite PNG/image; if opaque photo, apply clean rounded framing."""
    with Image.open(path) as raw:
        raw.load()
        oriented = ImageOps.exif_transpose(raw).convert("RGBA")

    alpha = oriented.getchannel("A")
    min_alpha, _ = alpha.getextrema()
    if min_alpha > 240:
        # User custom opaque photo: frame softly as a rounded sticker card
        inner = int(box_size * 0.84)
        framed = _round_card_image(oriented, inner, radius=32)
        canvas = Image.new("RGBA", (box_size, box_size), (0, 0, 0, 0))
        offset = (box_size - inner) // 2
        canvas.paste(framed, (offset, offset), framed)
        return canvas

    # Transparent cutout sprite: preserve alpha and normalize into box_size
    bbox = oriented.getbbox()
    if bbox:
        oriented = oriented.crop(bbox)
    max_inner = int(box_size * 0.90)
    w, h = oriented.size
    scale = min(max_inner / max(w, 1), max_inner / max(h, 1))
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = oriented.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (box_size, box_size), (0, 0, 0, 0))
    canvas.paste(resized, ((box_size - nw) // 2, (box_size - nh) // 2), resized)
    return canvas


def _create_soft_shadow(width: int, height: int, alpha_max: int = 44) -> Image.Image:
    """Generate a smooth elliptical floor shadow under Sayan."""
    scale = 2
    img = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pad_x = int(width * scale * 0.14)
    pad_y = int(height * scale * 0.20)
    draw.ellipse(
        (pad_x, pad_y, width * scale - pad_x, height * scale - pad_y),
        fill=(28, 22, 18, alpha_max),
    )
    img = img.filter(ImageFilter.GaussianBlur(radius=9))
    return img.resize((width, height), Image.Resampling.LANCZOS)


def _transform_sprite(
    src: Image.Image,
    target_w: int,
    target_h: int,
    angle_deg: float,
) -> Image.Image:
    """Scale and rotate a sprite in one resampling pass (resize+rotate is 3x slower)."""
    if abs(angle_deg) < 0.05:
        return src.resize((target_w, target_h), Image.Resampling.BILINEAR)

    iw, ih = src.size
    rad = math.radians(angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    out_w = max(1, int(round(abs(target_w * cos_a) + abs(target_h * sin_a))))
    out_h = max(1, int(round(abs(target_w * sin_a) + abs(target_h * cos_a))))

    sx = iw / target_w
    sy = ih / target_h
    a = cos_a * sx
    b = sin_a * sx
    d = -sin_a * sy
    e = cos_a * sy
    c = (iw - (a * out_w + b * out_h)) / 2.0
    f = (ih - (d * out_w + e * out_h)) / 2.0
    return src.transform(
        (out_w, out_h),
        Image.AFFINE,
        (a, b, c, d, e, f),
        Image.Resampling.BILINEAR,
    )


class SayanClickerApp:
    """Interactive cozy desktop clicker window for cat Sayan."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        if sys.platform == "win32":
            # 1ms timer resolution: without it after(28) fires in 16/32/48ms steps (judder)
            try:
                ctypes.windll.winmm.timeBeginPeriod(1)
            except Exception:
                pass
        self.dpi_scale: float = max(1.0, min(2.25, float(root.winfo_fpixels("1i")) / 96.0))
        self.config = load_config()
        self.state = SayanGameState.from_config(self.config)
        self.theme: ThemePalette = get_theme(self.config.get("theme", "cozy"))
        self.always_on_top: bool = bool(self.config.get("always_on_top", False))
        self.compact_mode: bool = bool(self.config.get("compact_mode", False))

        self.sound = SoundEngine(
            sounds_dir=get_resource_path("assets/sounds"),
            enabled=bool(self.config.get("sound_enabled", True)),
        )

        self._sprites_rgba: dict[str, Image.Image] = {}
        self._sprite_box_size: int = max(320, int(round(320 * self.dpi_scale)))
        self._load_builtin_sprites()
        self._load_custom_sprite_if_present()

        # Animation state
        self._particles: list[FloatingParticle] = []
        self._squash_started_at: float = -10.0
        self._last_warm_build_at: float = -10.0
        self._caption_sig: str | None = None
        self._cat_photo_ref: ImageTk.PhotoImage | None = None
        self._shadow_photo_ref: ImageTk.PhotoImage | None = None
        self._shadow_key: tuple[int, int, str] | None = None
        self._stage_bg_ref: ImageTk.PhotoImage | None = None
        self._window_icon_ref: ImageTk.PhotoImage | None = None
        self._frame_cache: OrderedDict[tuple[Any, ...], ImageTk.PhotoImage] = OrderedDict()
        self._fonts: dict[tuple[str, int, str], tkfont.Font] = {}
        self._stage_items: dict[str, int] | None = None
        self._particle_items: dict[int, int] = {}
        self._particle_free: list[int] = []
        self._treat_sig: tuple[Any, ...] | None = None
        self._treat_visible: bool = False
        self._hint_visible: bool = False
        self._style_dirty: bool = True
        self._tick_errors: int = 0
        self._last_save_at: float = time.monotonic()
        self._dirty_save: bool = False
        self._save_cond = threading.Condition()
        self._save_pending: dict[str, Any] | None = None
        self._save_stop: bool = False
        self._save_thread = threading.Thread(target=self._save_worker, daemon=True)
        self._save_thread.start()
        self._drag_origin: tuple[int, int] | None = None
        self._treat_hitbox: tuple[float, float, float] | None = None
        self._last_zzz_at: float = 0.0
        self._pose_toast_until: float = 0.0
        self._closing: bool = False
        self._rng = random.Random()

        self._configure_window()
        self._build_widgets()
        self._apply_theme()
        self._apply_mode_layout(initial=True)
        self._refresh_all_labels()

        self.root.bind("<space>", self._on_hotkey_pet)
        self.root.bind("<Return>", self._on_hotkey_pet)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self._schedule_tick()

    def _px(self, base_value: int) -> int:
        """Scale logical 96-DPI pixel size to current Windows monitor DPI."""
        return max(1, int(round(base_value * self.dpi_scale)))

    def _window_size_for_mode(self, compact: bool) -> tuple[int, int]:
        screen_w = max(640, self.root.winfo_screenwidth())
        screen_h = max(480, self.root.winfo_screenheight())
        base_w = BASE_COMPACT_WIDTH if compact else BASE_NORMAL_WIDTH
        base_h = BASE_COMPACT_HEIGHT if compact else BASE_NORMAL_HEIGHT
        w = min(screen_w - 32, self._px(base_w))
        h = min(screen_h - 64, self._px(base_h))
        return w, h

    def _configure_window(self) -> None:
        self.root.title("Кот Саян — Уютный кликер")
        self.root.resizable(False, False)

        ico_path = get_resource_path("assets/sayan_icon.ico")
        if ico_path.is_file():
            try:
                self.root.iconbitmap(str(ico_path))
                self.root.wm_iconbitmap(str(ico_path))
            except tk.TclError:
                pass

        w, h = self._window_size_for_mode(self.compact_mode)
        x, y = _clamp_window_position(
            self.root,
            w,
            h,
            self.config.get("window_x"),
            self.config.get("window_y"),
        )
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.attributes("-topmost", self.always_on_top)

    def _load_builtin_sprites(self) -> None:
        for mood in SPRITE_MOODS:
            sprite_path = get_resource_path(f"assets/sprites/{mood}.png")
            if sprite_path.is_file():
                try:
                    self._sprites_rgba[mood] = _prepare_sprite_rgba(
                        sprite_path, box_size=self._sprite_box_size
                    )
                except Exception:
                    continue

        if "curious" not in self._sprites_rgba:
            placeholder = Image.new(
                "RGBA", (self._sprite_box_size, self._sprite_box_size), (255, 122, 80, 200)
            )
            self._sprites_rgba["curious"] = placeholder

    def _load_custom_sprite_if_present(self) -> None:
        custom_path = self.state.custom_photo_path
        if custom_path and Path(custom_path).is_file():
            try:
                self._sprites_rgba[CUSTOM_MOOD] = _prepare_sprite_rgba(
                    Path(custom_path), box_size=self._sprite_box_size
                )
                return
            except Exception:
                pass
        if self.state.active_photo_mode == "custom":
            self.state.set_photo_mode("auto")

    def _get_current_sprite_rgba(self) -> Image.Image:
        key = self.state.get_effective_sprite()
        if key in self._sprites_rgba:
            return self._sprites_rgba[key]
        return self._sprites_rgba.get("curious") or next(iter(self._sprites_rgba.values()))

    def _build_widgets(self) -> None:
        self.main_frame = tk.Frame(self.root, bd=0, highlightthickness=0)
        self.main_frame.pack(fill="both", expand=True)

        # --- Top control bar ---
        self.header_frame = tk.Frame(self.main_frame, bd=0, highlightthickness=0)
        self.header_frame.pack(fill="x", padx=12, pady=(10, 6))

        self.title_label = tk.Label(
            self.header_frame,
            text="🐾 Кот Саян",
            font=("Segoe UI", 11, "bold"),
            cursor="fleur",
        )
        self.title_label.pack(side="left", padx=(2, 6))
        for drag_widget in (self.header_frame, self.title_label):
            drag_widget.bind("<ButtonPress-1>", self._start_drag)
            drag_widget.bind("<B1-Motion>", self._do_drag)

        self.controls_wrap = tk.Frame(self.header_frame, bd=0, highlightthickness=0)
        self.controls_wrap.pack(side="right")

        self.sound_btn = tk.Button(
            self.controls_wrap,
            text="🔊",
            font=("Segoe UI Emoji", 10),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=7,
            pady=3,
            command=self.toggle_sound,
        )
        self.sound_btn.pack(side="right", padx=(4, 0))

        self.compact_btn = tk.Button(
            self.controls_wrap,
            text="🪟 Компакт",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=4,
            command=self.toggle_compact_mode,
        )
        self.compact_btn.pack(side="right", padx=(4, 0))

        self.topmost_var = tk.BooleanVar(value=self.always_on_top)
        self.topmost_chk = tk.Checkbutton(
            self.controls_wrap,
            text="📌 Поверх",
            variable=self.topmost_var,
            indicatoron=False,
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=8,
            pady=4,
            command=self.toggle_always_on_top,
        )
        self.topmost_chk.pack(side="right", padx=(0, 0))

        # --- Speech bubble card ---
        self.bubble_outer = tk.Frame(self.main_frame, bd=0, highlightthickness=1)
        self.bubble_outer.pack(fill="x", padx=self._px(14), pady=(self._px(2), self._px(4)))

        self.bubble_label = tk.Label(
            self.bubble_outer,
            text=self.state.current_quote,
            font=("Segoe UI", 9, "bold"),
            justify="left",
            anchor="w",
            wraplength=self._px(360),
            padx=self._px(12),
            pady=self._px(8),
        )
        self.bubble_label.pack(fill="x")
        self.bubble_outer.bind("<Configure>", self._on_bubble_resize)

        # --- Interactive Sayan Stage Canvas ---
        self.stage_canvas = tk.Canvas(
            self.main_frame,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.stage_canvas.pack(fill="both", expand=True, padx=self._px(14), pady=(self._px(2), self._px(4)))
        self.stage_canvas.bind("<Button-1>", self._on_canvas_click)

        # --- Micro-Quiz Banner (hidden unless quiz active) ---
        self.quiz_frame = tk.Frame(self.main_frame, bd=0, highlightthickness=1)
        self.quiz_header = tk.Frame(self.quiz_frame, bd=0)
        self.quiz_header.pack(fill="x", padx=10, pady=(7, 3))

        self.quiz_title = tk.Label(
            self.quiz_header,
            text="📐 Быстрая задачка на +30 лапок:",
            font=("Segoe UI", 8, "bold"),
        )
        self.quiz_title.pack(side="left")

        self.quiz_close_btn = tk.Button(
            self.quiz_header,
            text="✕",
            font=("Segoe UI", 8, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=5,
            pady=1,
            command=self._dismiss_quiz,
        )
        self.quiz_close_btn.pack(side="right")

        self.quiz_question_lbl = tk.Label(
            self.quiz_frame,
            text="",
            font=("Segoe UI", 10, "bold"),
            anchor="w",
            justify="left",
            wraplength=360,
        )
        self.quiz_question_lbl.pack(fill="x", padx=10, pady=(0, 6))

        self.quiz_buttons_row = tk.Frame(self.quiz_frame, bd=0)
        self.quiz_buttons_row.pack(fill="x", padx=10, pady=(0, 8))
        self.quiz_opt_btns: list[tk.Button] = []
        for idx in range(3):
            btn = tk.Button(
                self.quiz_buttons_row,
                text="",
                font=("Segoe UI", 9, "bold"),
                bd=0,
                relief="flat",
                cursor="hand2",
                padx=10,
                pady=5,
                command=lambda i=idx: self._answer_quiz(i),
            )
            btn.pack(side="left", expand=True, fill="x", padx=(0 if idx == 0 else 5, 0))
            self.quiz_opt_btns.append(btn)

        # --- Stats & Progress Card ---
        self.stats_frame = tk.Frame(self.main_frame, bd=0, highlightthickness=1)
        self.stats_frame.pack(fill="x", padx=14, pady=(2, 6))

        self.score_row = tk.Frame(self.stats_frame, bd=0)
        self.score_row.pack(fill="x", padx=12, pady=(8, 4))

        self.pets_count_lbl = tk.Label(
            self.score_row,
            text="0 лапок",
            font=("Segoe UI", 17, "bold"),
            anchor="w",
        )
        self.pets_count_lbl.pack(side="left")

        self.combo_pill = tk.Label(
            self.score_row,
            text="x1",
            font=("Segoe UI", 9, "bold"),
            padx=9,
            pady=3,
        )
        self.combo_pill.pack(side="right")

        # Level & Energy bars (normal mode details)
        self.details_frame = tk.Frame(self.stats_frame, bd=0)
        self.details_frame.pack(fill="x", padx=12, pady=(0, 9))

        self.level_row = tk.Frame(self.details_frame, bd=0)
        self.level_row.pack(fill="x", pady=(0, 3))

        self.level_lbl = tk.Label(
            self.level_row,
            text="Ур. 1 • Котёнок-первоклассник",
            font=("Segoe UI", 9, "bold"),
            anchor="w",
        )
        self.level_lbl.pack(side="left")

        self.level_next_lbl = tk.Label(
            self.level_row,
            text="0 / 25",
            font=("Segoe UI", 8, "bold"),
            anchor="e",
        )
        self.level_next_lbl.pack(side="right")

        self.level_bar = tk.Canvas(
            self.details_frame,
            height=9,
            bd=0,
            highlightthickness=0,
        )
        self.level_bar.pack(fill="x", pady=(0, 6))

        self.energy_row = tk.Frame(self.details_frame, bd=0)
        self.energy_row.pack(fill="x")

        self.energy_lbl = tk.Label(
            self.energy_row,
            text="⚡ Тыгыдык: 0%",
            font=("Segoe UI", 8, "bold"),
            anchor="w",
        )
        self.energy_lbl.pack(side="left")

        self.mood_badge_lbl = tk.Label(
            self.energy_row,
            text="Настроение: Любопытный",
            font=("Segoe UI", 8),
            anchor="e",
        )
        self.mood_badge_lbl.pack(side="right")

        # --- Bottom Action Bar (hidden in compact mode) ---
        self.footer_frame = tk.Frame(self.main_frame, bd=0, highlightthickness=0)
        self.footer_frame.pack(fill="x", padx=14, pady=(0, 12))

        self.photo_btn = tk.Button(
            self.footer_frame,
            text="📷 Своё фото",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=9,
            pady=6,
            command=self.choose_custom_photo,
        )
        self.photo_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.pose_btn = tk.Button(
            self.footer_frame,
            text="🎭 Сменить позу",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=9,
            pady=6,
            command=self.cycle_pose_or_mode,
        )
        self.pose_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.theme_btn = tk.Button(
            self.footer_frame,
            text="🌙 Тема",
            font=("Segoe UI", 9, "bold"),
            bd=0,
            relief="flat",
            cursor="hand2",
            padx=9,
            pady=6,
            command=self.toggle_theme,
        )
        self.theme_btn.pack(side="left", expand=True, fill="x")

    def _apply_theme(self) -> None:
        t = self.theme
        self.root.configure(bg=t.bg_page)
        self.main_frame.configure(bg=t.bg_page)
        self.header_frame.configure(bg=t.bg_page)
        self.controls_wrap.configure(bg=t.bg_page)
        self.title_label.configure(bg=t.bg_page, fg=t.text_heading)

        self.sound_btn.configure(
            bg=t.bg_pill if self.sound.enabled else t.bg_control,
            fg=t.accent if self.sound.enabled else t.text_muted,
            activebackground=t.bg_pill_hover,
            activeforeground=t.accent,
        )
        self.compact_btn.configure(
            bg=t.bg_pill if self.compact_mode else t.bg_control,
            fg=t.accent if self.compact_mode else t.text_body,
            activebackground=t.bg_pill_hover,
            activeforeground=t.accent,
        )
        self.topmost_chk.configure(
            bg=t.bg_control,
            fg=t.text_body,
            selectcolor=t.accent,
            activebackground=t.bg_pill_hover,
            activeforeground=t.text_heading,
        )
        if self.always_on_top:
            self.topmost_chk.configure(fg=t.accent_text, bg=t.accent)

        self.bubble_outer.configure(
            bg=t.bubble_bg,
            highlightbackground=t.bubble_border,
            highlightcolor=t.bubble_border,
        )
        self.bubble_label.configure(bg=t.bubble_bg, fg=t.text_heading)

        self.stage_canvas.configure(bg=t.bg_page)

        self.quiz_frame.configure(
            bg=t.sage_light,
            highlightbackground=t.sage,
            highlightcolor=t.sage,
        )
        self.quiz_header.configure(bg=t.sage_light)
        self.quiz_title.configure(bg=t.sage_light, fg=t.sage)
        self.quiz_close_btn.configure(
            bg=t.sage_light,
            fg=t.text_muted,
            activebackground=t.bg_card,
        )
        self.quiz_question_lbl.configure(bg=t.sage_light, fg=t.text_heading)
        self.quiz_buttons_row.configure(bg=t.sage_light)
        for btn in self.quiz_opt_btns:
            btn.configure(
                bg=t.bg_card,
                fg=t.text_heading,
                activebackground=t.accent,
                activeforeground=t.accent_text,
            )

        self.stats_frame.configure(
            bg=t.bg_card,
            highlightbackground=t.border,
            highlightcolor=t.border,
        )
        self.score_row.configure(bg=t.bg_card)
        self.pets_count_lbl.configure(bg=t.bg_card, fg=t.text_heading)
        self.combo_pill.configure(bg=t.bg_pill, fg=t.accent)

        self.details_frame.configure(bg=t.bg_card)
        self.level_row.configure(bg=t.bg_card)
        self.level_lbl.configure(bg=t.bg_card, fg=t.sage)
        self.level_next_lbl.configure(bg=t.bg_card, fg=t.text_muted)
        self.level_bar.configure(bg=t.bg_card)
        self.energy_row.configure(bg=t.bg_card)
        self.energy_lbl.configure(bg=t.bg_card, fg=t.gold)
        self.mood_badge_lbl.configure(bg=t.bg_card, fg=t.text_muted)

        self.footer_frame.configure(bg=t.bg_page)
        for btn in (self.photo_btn, self.pose_btn, self.theme_btn):
            btn.configure(
                bg=t.bg_control,
                fg=t.text_heading,
                activebackground=t.bg_pill_hover,
                activeforeground=t.accent,
            )

        self.theme_btn.configure(
            text="☀️ Уютный" if self.theme.key == "cyber" else "🌙 Кибер-Кот"
        )
        self._shadow_key = None
        self._style_dirty = True

    def _on_bubble_resize(self, event: tk.Event[Any]) -> None:
        wrap = max(140, int(event.width) - self._px(28))
        self.bubble_label.configure(wraplength=wrap)
        if hasattr(self, "quiz_question_lbl"):
            self.quiz_question_lbl.configure(wraplength=wrap)

    def _apply_mode_layout(self, initial: bool = False) -> None:
        w, h = self._window_size_for_mode(self.compact_mode)
        if self.compact_mode:
            self.title_label.pack_forget()
            self.details_frame.pack_forget()
            self.footer_frame.pack_forget()
            self.bubble_label.configure(
                font=("Segoe UI", 8, "bold"),
                wraplength=max(160, w - self._px(52)),
                padx=self._px(8),
                pady=self._px(6),
            )
            self.pets_count_lbl.configure(font=("Segoe UI", 13, "bold"))
            self.compact_btn.configure(text="⛶ Полный")
            self.topmost_chk.configure(text="📌")
        else:
            if not self.title_label.winfo_ismapped():
                self.title_label.pack(side="left", padx=(2, 6))
            if not self.details_frame.winfo_ismapped():
                self.details_frame.pack(fill="x", padx=self._px(12), pady=(0, self._px(9)))
            if not self.footer_frame.winfo_ismapped():
                self.footer_frame.pack(fill="x", padx=self._px(14), pady=(0, self._px(12)))
            self.bubble_label.configure(
                font=("Segoe UI", 9, "bold"),
                wraplength=max(220, w - self._px(56)),
                padx=self._px(12),
                pady=self._px(8),
            )
            self.pets_count_lbl.configure(font=("Segoe UI", 17, "bold"))
            self.compact_btn.configure(text="🪟 Компакт")
            self.topmost_chk.configure(text="📌 Поверх")

        if not initial:
            cur_x = self.root.winfo_x()
            cur_y = self.root.winfo_y()
            x, y = _clamp_window_position(self.root, w, h, cur_x, cur_y)
            self.root.geometry(f"{w}x{h}+{x}+{y}")

        self._sync_quiz_banner()
        self._apply_theme()
        self._style_dirty = True

    def _sync_quiz_banner(self) -> None:
        quiz = self.state.active_quiz
        if quiz is None or self.compact_mode:
            if self.quiz_frame.winfo_ismapped():
                self.quiz_frame.pack_forget()
            return

        self.quiz_question_lbl.configure(text=quiz.question)
        for idx, btn in enumerate(self.quiz_opt_btns):
            btn.configure(text=quiz.options[idx])

        if not self.quiz_frame.winfo_ismapped():
            self.quiz_frame.pack(fill="x", padx=14, pady=(0, 6), before=self.stats_frame)

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

    def _refresh_all_labels(self) -> None:
        count = self.state.pets_count
        self.pets_count_lbl.configure(text=f"{count} {self._plural_paws(count)}")

        zoomies = self.state.is_zoomies_active()
        mult = max(
            1,
            3 if zoomies else (
                5 if self.state.combo_streak >= 25
                else 3 if self.state.combo_streak >= 12
                else 2 if self.state.combo_streak >= 5
                else 1
            ),
        )
        if zoomies:
            rem = max(1, int(math.ceil(self.state.zoomies_remaining())))
            combo_txt = f"⚡ x{mult} ({rem}с)"
            self.combo_pill.configure(bg=self.theme.gold_light, fg=self.theme.gold)
        elif self.state.combo_streak >= 5:
            combo_txt = f"🔥 x{mult} ({self.state.combo_streak})"
            self.combo_pill.configure(bg=self.theme.bg_pill, fg=self.theme.accent)
        else:
            combo_txt = f"Комбо x{mult}"
            self.combo_pill.configure(bg=self.theme.bg_control, fg=self.theme.text_muted)
        self.combo_pill.configure(text=combo_txt)

        lvl = self.state.get_level_info()
        self.level_lbl.configure(text=f"Ур. {lvl.index} • {lvl.title}")
        if lvl.next_threshold is not None:
            self.level_next_lbl.configure(text=f"{count} / {lvl.next_threshold}")
        else:
            self.level_next_lbl.configure(text="МАКС ★")

        self._draw_level_bar(lvl.progress_ratio)

        if zoomies:
            self.energy_lbl.configure(text="⚡ ТЫГЫДЫК АКТИВЕН!")
        else:
            self.energy_lbl.configure(text=f"⚡ Тыгыдык: {self.state.purr_energy}%")

        self.mood_badge_lbl.configure(text=self._mood_russian_label())
        self.bubble_label.configure(text=self.state.current_quote)

        if self.state.active_photo_mode == "custom" and self.state.custom_photo_path:
            self.pose_btn.configure(text="🐱 Вернуть Саяна")
        else:
            self.pose_btn.configure(text="🎭 Сменить позу")

        self.sound_btn.configure(text="🔊" if self.sound.enabled else "🔇")

    def _draw_level_bar(self, ratio: float) -> None:
        bar = self.level_bar
        bar.update_idletasks()
        w = max(80, bar.winfo_width() or 360)
        h = 9
        bar.delete("all")
        bar.create_rectangle(0, 1, w, h - 1, fill=self.theme.bg_control, outline="")
        fill_w = max(6 if ratio > 0 else 0, int(w * max(0.0, min(1.0, ratio))))
        if fill_w > 0:
            bar_color = self.theme.gold if self.state.is_zoomies_active() else self.theme.accent
            bar.create_rectangle(0, 1, fill_w, h - 1, fill=bar_color, outline="")

    @staticmethod
    def _plural_paws(n: int) -> str:
        mod100 = n % 100
        mod10 = n % 10
        if 11 <= mod100 <= 14:
            return "лапок"
        if mod10 == 1:
            return "лапка"
        if 2 <= mod10 <= 4:
            return "лапки"
        return "лапок"

    # --- Event Handlers ---

    def _start_drag(self, event: tk.Event[Any]) -> None:
        self._drag_origin = (event.x_root - self.root.winfo_x(), event.y_root - self.root.winfo_y())

    def _do_drag(self, event: tk.Event[Any]) -> None:
        if self._drag_origin is None:
            return
        dx, dy = self._drag_origin
        self.root.geometry(f"+{event.x_root - dx}+{event.y_root - dy}")
        self._dirty_save = True

    def _on_hotkey_pet(self, _event: tk.Event[Any]) -> None:
        w = self.stage_canvas.winfo_width() or 300
        h = self.stage_canvas.winfo_height() or 260
        self._perform_pet(w / 2, h / 2)

    def _on_canvas_click(self, event: tk.Event[Any]) -> None:
        if self._treat_hitbox is not None and self.state.active_treat is not None:
            tx, ty, radius = self._treat_hitbox
            if math.hypot(event.x - tx, event.y - ty) <= radius + 8:
                self._claim_treat(event.x, event.y)
                return

        self._perform_pet(event.x, event.y)

    def _perform_pet(self, click_x: float, click_y: float) -> None:
        now = time.monotonic()
        res: PetResult = self.state.pet(now=now)
        self._squash_started_at = now
        self._dirty_save = True

        # Sound feedback
        if res.zoomies_started:
            self.sound.play("zoomies", cooldown_ms=120)
        elif res.level_up is not None or res.new_milestones:
            self.sound.play("levelup", cooldown_ms=150)
        elif res.woke_up or res.combo_streak % 8 == 0:
            self.sound.play("meow", cooldown_ms=180)
        elif res.combo_streak >= 6:
            self.sound.play("purr_deep", cooldown_ms=260)
        else:
            self.sound.play("purr", cooldown_ms=220)

        # Spawn visual particles
        self._spawn_pet_particles(click_x, click_y, res)
        self._sync_quiz_banner()
        self._refresh_all_labels()

    def _claim_treat(self, x: float, y: float) -> None:
        res: EventClaimResult = self.state.claim_treat()
        if not res.claimed:
            return
        self._squash_started_at = time.monotonic()
        self._treat_hitbox = None
        self._dirty_save = True

        if res.level_up is not None or res.new_milestones:
            self.sound.play("levelup", cooldown_ms=100)
        else:
            self.sound.play("treat", cooldown_ms=80)

        self._spawn_burst(x, y, f"+{res.points_gained}", "ням!")
        self._refresh_all_labels()

    def _answer_quiz(self, option_index: int) -> None:
        if self.state.active_quiz is None:
            return
        res: QuizAnswerResult = self.state.answer_quiz(option_index)
        self._dirty_save = True
        if res.correct:
            self.sound.play("levelup", cooldown_ms=80)
            w = self.stage_canvas.winfo_width() or 300
            h = self.stage_canvas.winfo_height() or 260
            self._spawn_burst(w / 2, h * 0.45, f"+{res.points_gained}", "пятёрка!")
        else:
            self.sound.play("meow", cooldown_ms=80)
        self._sync_quiz_banner()
        self._refresh_all_labels()

    def _dismiss_quiz(self) -> None:
        self.state.dismiss_quiz()
        self._sync_quiz_banner()

    def _spawn_pet_particles(self, x: float, y: float, res: PetResult) -> None:
        now = time.monotonic()
        self._particles.append(
            FloatingParticle(
                x=x + self._rng.uniform(-8, 8),
                y=y - 12,
                vx=self._rng.uniform(-10, 10),
                vy=-64.0,
                text=f"+{res.points_gained}",
                color=self.theme.gold if res.zoomies_active or res.multiplier >= 3 else self.theme.accent,
                font_size=16 if res.multiplier >= 3 else 14,
                born_at=now,
                lifetime=0.9,
                is_bold=True,
            )
        )

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
            self._particles.append(
                FloatingParticle(
                    x=x + self._rng.uniform(-14, 14),
                    y=y - 30,
                    vx=0.0,
                    vy=-46.0,
                    text=word,
                    color=self.theme.text_heading,
                    font_size=13,
                    born_at=now,
                    lifetime=1.0,
                    is_bold=True,
                )
            )
        self._particles = self._particles[-10:]

    def _spawn_burst(self, x: float, y: float, headline: str, word: str | None = None) -> None:
        now = time.monotonic()
        self._particles.append(
            FloatingParticle(
                x=x,
                y=y - 10,
                vx=0.0,
                vy=-70.0,
                text=headline,
                color=self.theme.gold,
                font_size=16,
                born_at=now,
                lifetime=1.1,
                is_bold=True,
            )
        )
        if word:
            self._particles.append(
                FloatingParticle(
                    x=x,
                    y=y - 32,
                    vx=0.0,
                    vy=-50.0,
                    text=word,
                    color=self.theme.text_heading,
                    font_size=13,
                    born_at=now,
                    lifetime=1.1,
                    is_bold=True,
                )
            )
        self._particles = self._particles[-10:]

    # --- Toggles & Photo Picker ---

    def toggle_sound(self) -> None:
        new_val = not self.sound.enabled
        self.sound.set_enabled(new_val)
        if new_val:
            self.sound.play("treat", cooldown_ms=50)
        self._dirty_save = True
        self._apply_theme()
        self._refresh_all_labels()

    def toggle_always_on_top(self) -> None:
        self.always_on_top = bool(self.topmost_var.get())
        self.root.attributes("-topmost", self.always_on_top)
        self._dirty_save = True
        self._apply_theme()

    def toggle_compact_mode(self) -> None:
        self.compact_mode = not self.compact_mode
        self._dirty_save = True
        self._apply_mode_layout(initial=False)
        self._refresh_all_labels()

    def toggle_theme(self) -> None:
        next_key = "cyber" if self.theme.key == "cozy" else "cozy"
        self.theme = get_theme(next_key)
        self._dirty_save = True
        self._apply_theme()
        self._refresh_all_labels()

    def choose_custom_photo(self) -> None:
        file_path = filedialog.askopenfilename(
            parent=self.root,
            title="Выбери фото Саяна или своего котика",
            filetypes=[
                ("Изображения", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Все файлы", "*.*"),
            ],
        )
        if not file_path:
            return
        try:
            saved_path = import_custom_photo(file_path)
            self._sprites_rgba[CUSTOM_MOOD] = _prepare_sprite_rgba(
                Path(saved_path), box_size=self._sprite_box_size
            )
            self.state.set_photo_mode("custom", custom_photo_path=saved_path)
            self.state.current_quote = "Новое фото загружено! Погладь меня скорей! 📷🐾"
            self.sound.play("meow", cooldown_ms=80)
            self._dirty_save = True
            self._refresh_all_labels()
            self._persist_now()
        except Exception as exc:
            messagebox.showerror(
                "Не удалось загрузить фото",
                f"Выбери корректный файл изображения (PNG/JPG/WEBP).\n\nДетали: {exc}",
                parent=self.root,
            )

    def cycle_pose_or_mode(self) -> None:
        if self.state.active_photo_mode == "custom":
            self.state.set_photo_mode("auto")
            self.state.mood = "curious"
            self.state.current_quote = "Саян снова в деле со всеми позами и настроениями! 🐾"
        else:
            available = [m for m in SPRITE_MOODS if m in self._sprites_rgba] or ["curious"]
            try:
                cur_idx = available.index(self.state.mood)
            except ValueError:
                cur_idx = -1
            next_mood = available[(cur_idx + 1) % len(available)]
            self.state.mood = next_mood
            self.state._idle_anchor_at = time.monotonic()
            self.state.current_quote = f"Поза переключена: {self._mood_russian_label()}"

        self.sound.play("purr", cooldown_ms=100)
        self._squash_started_at = time.monotonic()
        self._dirty_save = True
        self._refresh_all_labels()

    # --- Main Animation & Game Loop ---

    def _schedule_tick(self) -> None:
        if self._closing:
            return
        try:
            self._tick_body(time.monotonic())
        except Exception:
            self._tick_errors += 1
            if self._tick_errors <= 3:
                traceback.print_exc()
        finally:
            self.root.after(ANIM_INTERVAL_MS, self._schedule_tick)

    def _tick_body(self, now: float) -> None:
        tick_res = self.state.tick(now=now)
        if tick_res.entered_sleep or tick_res.zoomies_ended or tick_res.treat_expired or tick_res.spawned_treat:
            self._refresh_all_labels()
            if tick_res.entered_sleep:
                self._dirty_save = True

        # Periodic soft Zzz particles while sleeping
        if self.state.is_sleeping() and (now - self._last_zzz_at) >= 2.2:
            self._last_zzz_at = now
            cw = self.stage_canvas.winfo_width() or 280
            ch = self.stage_canvas.winfo_height() or 220
            self._particles.append(
                FloatingParticle(
                    x=cw * 0.62 + self._rng.uniform(-10, 14),
                    y=ch * 0.28,
                    vx=12.0,
                    vy=-28.0,
                    text="Zzz",
                    color=self.theme.text_muted,
                    font_size=12,
                    born_at=now,
                    lifetime=1.6,
                    is_bold=True,
                )
            )

        self._render_stage(now)

        if self._dirty_save and (now - self._last_save_at) >= SAVE_DEBOUNCE_SECONDS:
            self._persist_now()

    def _font(self, family: str, size: int, weight: str = "normal") -> tkfont.Font:
        key = (family, size, weight)
        font = self._fonts.get(key)
        if font is None:
            font = tkfont.Font(family=family, size=size, weight=weight)
            self._fonts[key] = font
        return font

    def _create_stage_items(self, canvas: tk.Canvas) -> None:
        t = self.theme
        self._stage_items = {
            "halo": canvas.create_oval(0, 0, 0, 0, fill=t.stage_halo, outline=t.stage_ring, width=2),
            "shadow": canvas.create_image(0, 0),
            "sprite": canvas.create_image(0, 0),
            "treat_ring": canvas.create_oval(
                0, 0, 0, 0, fill=t.gold_light, outline=t.gold, width=2, state="hidden"
            ),
            "treat_emoji": canvas.create_text(0, 0, text="", state="hidden"),
            "treat_bonus": canvas.create_text(0, 0, text="", fill=t.gold, state="hidden"),
            "hint": canvas.create_text(
                0,
                0,
                text="Кликни по Саяну или нажми Пробел, чтобы погладить ✨",
                fill=t.text_muted,
                font=self._font("Segoe UI", 8),
                state="hidden",
            ),
            "caption": canvas.create_text(
                0, 0, text="", fill=t.text_muted, font=self._font("Segoe UI", 9, "bold")
            ),
        }
        # Pre-create the inscription pool and warm font objects so the first
        # burst does not hitch the animation loop.
        for _ in range(12):
            self._particle_free.append(canvas.create_text(0, 0, text="", state="hidden"))
        for size in (12, 13, 14, 16):
            for weight in ("normal", "bold"):
                self._font("Segoe UI", size, weight)
        self._style_dirty = True

    def _apply_stage_style(self, canvas: tk.Canvas, items: dict[str, int]) -> None:
        t = self.theme
        canvas.itemconfig(items["halo"], fill=t.stage_halo, outline=t.stage_ring)
        canvas.itemconfig(items["treat_ring"], fill=t.gold_light, outline=t.gold)
        canvas.itemconfig(items["treat_bonus"], fill=t.gold)
        canvas.itemconfig(items["hint"], fill=t.text_muted)
        canvas.itemconfig(items["caption"], fill=t.text_muted)

    def _build_sprite_photo(
        self,
        sprite_key: str,
        base_dim: int,
        kind: str,
        angle: float,
    ) -> ImageTk.PhotoImage:
        if kind == "wide":
            sx, sy = 1.12, 0.88
        elif kind == "tall":
            sx, sy = 0.90, 1.10
        else:
            sx, sy = 1.0, 1.0
        w = max(48, int(round(base_dim * sx)))
        h = max(48, int(round(base_dim * sy)))
        a = int(round(angle / SPRITE_ANGLE_BUCKET)) * SPRITE_ANGLE_BUCKET
        key = (sprite_key, base_dim, kind, a)
        src = self._sprites_rgba.get(sprite_key) or self._get_current_sprite_rgba()
        photo = ImageTk.PhotoImage(_transform_sprite(src, w, h, float(a)))
        self._frame_cache[key] = photo
        while len(self._frame_cache) > FRAME_CACHE_LIMIT:
            self._frame_cache.popitem(last=False)
        return photo

    def _warm_missing_frame(
        self, now: float, sprite_key: str, base_dim: int, zoomies: bool
    ) -> None:
        """Rasterize at most one missing keyframe per tick so animation never hitches."""
        if now - self._last_warm_build_at < 0.03:
            return
        if zoomies:
            wanted = [
                (sprite_key, base_dim, "rot", a)
                for a in range(-8, 9, SPRITE_ANGLE_BUCKET)
            ]
        else:
            wanted = [(sprite_key, base_dim, k, 0) for k in ("base", "wide", "tall")]
        for key in wanted:
            if key not in self._frame_cache:
                self._build_sprite_photo(sprite_key, base_dim, key[2], float(key[3]))
                self._last_warm_build_at = now
                return

    def _render_stage(self, now: float) -> None:
        canvas = self.stage_canvas
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        if cw < 40 or ch < 40:
            return
        if self._stage_items is None:
            self._create_stage_items(canvas)
        items = self._stage_items
        t = self.theme
        if self._style_dirty:
            self._apply_stage_style(canvas, items)
            self._style_dirty = False

        base_dim = int(min(cw, ch) * (0.84 if self.compact_mode else 0.86))
        sprite_key = self.state.get_effective_sprite()
        cx = cw / 2.0
        cy = ch / 2.0 + 4.0

        # Keyframe-based motion: scale/angle come only from cached frames,
        # per-frame work is coords() so the loop never hitches on rasterization.
        squash_age = now - self._squash_started_at
        zoomies = self.state.is_zoomies_active(now)
        if 0.0 <= squash_age < 0.36:
            kind = "wide" if (squash_age < 0.09 or squash_age >= 0.18) else "tall"
            angle = 0.0
            bob_y = -6.0 * math.exp(-6.0 * squash_age) * max(0.0, math.sin(14.0 * squash_age))
        elif zoomies:
            kind = "rot"
            angle = 7.0 * math.sin(now * 5.0)
            bob_y = -5.0 * abs(math.sin(now * 11.0))
            margin = base_dim * 0.5 + 8.0
            usable = cw - 2.0 * margin
            if usable > 40.0:
                cx = margin + usable * (0.5 + 0.5 * math.sin(now * 2.2))
        elif self.state.is_sleeping():
            kind = "base"
            angle = 0.0
            bob_y = 2.0 * math.sin(now * 1.4)
        else:
            kind = "base"
            angle = 0.0
            bob_y = -3.2 * math.sin(now * 2.4)

        # Subtle stage halo ring behind Sayan (follows the run during zoomies)
        halo_r = min(cw, ch) * 0.42
        canvas.coords(
            items["halo"],
            cx - halo_r,
            cy - halo_r * 0.92,
            cx + halo_r,
            cy + halo_r * 0.92,
        )

        # Soft ground shadow under Sayan (static size, regenerated only on resize/theme)
        shadow_w = max(80, int(min(cw, ch) * 0.54))
        shadow_w -= shadow_w % 8
        shadow_h = max(18, int(shadow_w * 0.22))
        shadow_y = cy + min(cw, ch) * 0.34
        shadow_key = (shadow_w, shadow_h, t.key)
        if self._shadow_key != shadow_key or self._shadow_photo_ref is None:
            self._shadow_photo_ref = ImageTk.PhotoImage(
                _create_soft_shadow(shadow_w, shadow_h, alpha_max=40 if t.key == "cozy" else 75)
            )
            self._shadow_key = shadow_key
            canvas.itemconfig(items["shadow"], image=self._shadow_photo_ref)
        canvas.coords(items["shadow"], cx, shadow_y)

        angle_q = int(round(angle / SPRITE_ANGLE_BUCKET)) * SPRITE_ANGLE_BUCKET
        render_key = (sprite_key, base_dim, kind, angle_q)
        photo = self._frame_cache.get(render_key)
        if photo is not None:
            self._frame_cache.move_to_end(render_key)
        else:
            photo = self._frame_cache.get((sprite_key, base_dim, "base", 0))
            if photo is None:
                photo = self._build_sprite_photo(sprite_key, base_dim, "base", 0.0)
        if photo is not self._cat_photo_ref:
            self._cat_photo_ref = photo
            canvas.itemconfig(items["sprite"], image=photo)
        canvas.coords(items["sprite"], cx, cy - 4 + bob_y)
        self._warm_missing_frame(now, sprite_key, base_dim, zoomies)

        # Render catchable treat mini-event orb
        treat = self.state.active_treat
        if treat is not None and not treat.is_expired(now):
            age = now - treat.spawned_at
            tx = cx + math.sin(age * 2.4) * (cw * 0.28)
            ty = cy - halo_r * 0.56 + math.cos(age * 3.1) * 14.0
            r = 24 if self.compact_mode else 28
            self._treat_hitbox = (tx, ty, float(r))
            canvas.coords(items["treat_ring"], tx - r - 3, ty - r - 3, tx + r + 3, ty + r + 3)
            canvas.coords(items["treat_emoji"], tx, ty - 4)
            canvas.coords(items["treat_bonus"], tx, ty + 13)
            treat_sig = (treat.emoji, treat.bonus, self.compact_mode)
            if treat_sig != self._treat_sig:
                self._treat_sig = treat_sig
                canvas.itemconfig(
                    items["treat_emoji"],
                    text=treat.emoji,
                    font=self._font("Segoe UI Emoji", 14 if self.compact_mode else 16),
                )
                canvas.itemconfig(items["treat_bonus"], text=f"+{treat.bonus}")
            if not self._treat_visible:
                self._treat_visible = True
                for name in ("treat_ring", "treat_emoji", "treat_bonus"):
                    canvas.itemconfig(items[name], state="normal")
        else:
            self._treat_hitbox = None
            self._treat_sig = None
            if self._treat_visible:
                self._treat_visible = False
                for name in ("treat_ring", "treat_emoji", "treat_bonus"):
                    canvas.itemconfig(items[name], state="hidden")

        # Render flying particles, reusing canvas text items
        alive: list[FloatingParticle] = []
        used: set[int] = set()
        for pt in self._particles:
            age = now - pt.born_at
            if age >= pt.lifetime:
                continue
            alive.append(pt)
            key = id(pt)
            used.add(key)
            item = self._particle_items.get(key)
            if item is None:
                if self._particle_free:
                    item = self._particle_free.pop()
                else:
                    item = canvas.create_text(0, 0, text="")
                self._particle_items[key] = item
                canvas.itemconfig(
                    item,
                    text=pt.text,
                    fill=pt.color,
                    font=self._font(
                        "Segoe UI", pt.font_size, "bold" if pt.is_bold else "normal"
                    ),
                    state="normal",
                )
            px = pt.x + pt.vx * age
            py = pt.y + pt.vy * age + 18.0 * (age * age)
            canvas.coords(item, px, py)
        for key in list(self._particle_items):
            if key not in used:
                item = self._particle_items.pop(key)
                canvas.itemconfig(item, state="hidden")
                self._particle_free.append(item)
        self._particles = alive

        # Pose caption at the bottom; quick hint at the top when idle
        caption = self._mood_russian_label()
        if caption != self._caption_sig:
            self._caption_sig = caption
            canvas.itemconfig(items["caption"], text=caption)
        canvas.coords(items["caption"], cw / 2.0, ch - 10)
        show_hint = self.state.session_clicks == 0 and not self.compact_mode
        if show_hint:
            canvas.coords(items["hint"], cw / 2.0, 12)
        if show_hint != self._hint_visible:
            self._hint_visible = show_hint
            canvas.itemconfig(items["hint"], state="normal" if show_hint else "hidden")

    def _persist_now(self) -> None:
        payload = dict(self.config)
        payload.update(self.state.to_config_updates())
        payload.update(
            {
                "sound_enabled": self.sound.enabled,
                "always_on_top": self.always_on_top,
                "compact_mode": self.compact_mode,
                "theme": self.theme.key,
            }
        )
        try:
            payload["window_x"] = int(self.root.winfo_x())
            payload["window_y"] = int(self.root.winfo_y())
        except tk.TclError:
            pass
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

    def on_close(self) -> None:
        self._closing = True
        self._persist_now()
        self._flush_save()
        self.sound.stop()
        if sys.platform == "win32":
            try:
                ctypes.windll.winmm.timeEndPeriod(1)
            except Exception:
                pass
        self.root.destroy()
