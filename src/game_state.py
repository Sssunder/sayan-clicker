"""Pure game state, combo, mood, quote, and mini-event logic for Sayan Clicker."""

from __future__ import annotations

import random
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

SPRITE_MOODS: tuple[str, ...] = (
    "curious",
    "window",
    "stretch",
    "ambush",
    "sleep_sunset",
    "sleep_rug",
    "sleep_chair",
    "sleep_cozy",
    "zoomies",
    "photo_window",
    "photo_cuddle",
    "photo_sink",
    "photo_chair",
    "photo_armchair",
    "photo_nap",
    "photo_sofa",
    "photo_sill_nap",
    "photo_stretch_nap",
    "photo_sprawl",
)
AWAKE_MOODS: tuple[str, ...] = (
    "curious",
    "window",
    "stretch",
    "ambush",
    "photo_window",
    "photo_cuddle",
    "photo_sink",
)
HIGH_COMBO_MOODS: tuple[str, ...] = (
    "stretch",
    "ambush",
    "stretch",
    "ambush",
    "curious",
)
SLEEP_MOODS: tuple[str, ...] = (
    "sleep_sunset",
    "sleep_rug",
    "sleep_chair",
    "sleep_cozy",
    "photo_chair",
    "photo_armchair",
    "photo_nap",
    "photo_sofa",
    "photo_sill_nap",
    "photo_stretch_nap",
    "photo_sprawl",
)
CUSTOM_MOOD: str = "custom"

COMBO_WINDOW_SECONDS: float = 1.4
SLEEP_IDLE_SECONDS: float = 18.0
ZOOMIES_DURATION_SECONDS: float = 10.0
ZOOMIES_COOLDOWN_SECONDS: float = 35.0
TREAT_LIFETIME_SECONDS: float = 9.0
TICK_TREAT_INTERVAL_SECONDS: float = 28.0
CLICK_TREAT_CADENCE: int = 14
CLICK_QUIZ_CADENCE: int = 26
WAKE_UP_BONUS: int = 5
QUIZ_REWARD: int = 30
MAX_PURR_ENERGY: int = 100

LEVELS: tuple[tuple[int, str], ...] = (
    (0, "Котёнок-первоклассник"),
    (25, "Дежурный по тетрадкам"),
    (75, "Знаток таблицы умножения"),
    (160, "Повелитель циркуля и усов"),
    (300, "Хранитель твёрдых пятёрок"),
    (500, "Кандидат мурлычных наук"),
    (800, "Профессор геометрии и тыгыдыка"),
    (1250, "Академик ОГЭ на максимум"),
    (2000, "Легендарный Архитектор Уюта"),
)

MILESTONES: tuple[int, ...] = (
    1,
    5,
    25,
    50,
    100,
    150,
    314,
    500,
    777,
    1000,
    1500,
    2000,
)

MILESTONE_QUOTES: dict[int, str] = {
    1: "Первая лапка! Добро пожаловать в уютную компанию Саяна! 🐾",
    5: "Первая твёрдая пятёрка! Так держать, идём к ОГЭ без стресса! 5️⃣",
    25: "25 лапок — Саян официально назначен дежурным по твоим тетрадкам! 📓",
    50: "50 лапок! Половина сотни пройдена с мурчанием! ✨",
    100: "100 лапок! Стопроцентный уровень кошачьего антистресса! 💯",
    150: "150 лапок! Усы Саяна ловят геометрические теоремы на лету! 📐",
    314: "Число Пи-Мурр! 314 лапок — идеальная окружность уюта и математики! 🥧🐾",
    500: "500 лапок! Саян защитил диссертацию мурлычных наук! 🎓",
    777: "777 лапок! Тройная кошачья удача на контрольных и экзаменах! 🍀",
    1000: "1000 лапок! Тысячекратное мурлыканье поддержки! 🏆",
    1500: "1500 лапок! Ни одна задача №20 не устоит перед таким настроем! ☕",
    2000: "2000 лапок! Звание Легендарного Архитектора Уюта получено! 👑",
}

TREAT_CATALOG: dict[str, tuple[str, str, int]] = {
    "fish": ("Свежая рыбка", "🐟", 15),
    "yarn": ("Мягкий клубочек", "🧶", 20),
    "five": ("Твёрдая пятёрка", "5️⃣", 25),
    "milk": ("Тёплое молочко", "🥛", 18),
}

CAT_QUOTES: dict[str, tuple[str, ...]] = {
    "pet": (
        "Мяу! Проверил твою домашку: всё сошлось, молодец! 🐱",
        "Мур-мур... Почеши ещё за левым ушком — и следующая задача решится сама! 🐾",
        "Усям! Саян потянулся и одобряет твой рабочий ритм! ✨",
        "Тёплые лапки на краю тетради — лучший оберег от глупых ошибок. 📓",
        "Сижу у окна, наблюдаю за облаками и считаю углы треугольников. 🌤️",
        "Мр-р! Перерыв на поглаживание кота официально засчитан как полезная пауза! ☕",
    ),
    "math_easter_egg": (
        "Муррр! Число Пи ≈ 3.14159, а почесать за ушком — бесценно! 🐾",
        "Мяу! ОГЭ по математике сдадим на 5, главное не паниковать! ✨",
        "Мр-р-р! В геометрии главное — видеть чертёж, а не зубрить теоремы! 📐",
        "Мррр! Архитектор мышления учит так, что даже коты понимают функции! 📈",
        "Мяу! Доказательство готово: треугольники равны по двум сторонам и углу! 🏆",
        "Уровень антистресса повышен на 100%! Теперь пора решить задачку №20 ☕",
        "Катет напротив 30° равен половине гипотенузы, а вкусняшка — целому счастью! 🐟",
    ),
    "combo": (
        "Комбо мурчания! Продолжай в том же духе! 🔥",
        "Мурр-турбо! Твои клики точнее циркуля! 📐⚡",
        "Пятёрочный темп! Как на ОГЭ без единой помарки! 5️⃣✨",
        "Усы вибрируют от скорости! Саян в полном восторге! 😻",
    ),
    "sleep": (
        "Zzz... Саян проверяет теоремы во сне... 💤",
        "Кот спит — домашка уже проверена и лежит аккуратно стопочкой. 😴",
        "Мр-р-р... Тёплый лучик солнца, мягкий коврик и формулы в облаках... 🌅",
        "Тихий час: пушистый репетитор восстанавливает мур-энергию... 🛋️",
    ),
    "wake": (
        "Мяу?! Кто-то шуршит тетрадкой или вкусняшкой? +5 лапок за заботу! 🐾",
        "Проснулся! Усы навострены, можно дальше покорять алгебру! +5 ✨",
        "Доброе пробуждение, друг! Выспался и готов к твёрдым пятёркам! +5 5️⃣",
    ),
    "treat": (
        "Хрум! Вкуснейшая рыбка — и мозг сразу решает задачи быстрее! 🐟",
        "Поймал клубочек! Почти как поймать дискриминант > 0! 🧶",
        "Твёрдая пятёрка поймана! Саян ставит личную печать лапкой! 5️⃣",
        "Тёплое молочко — идеальный перерыв после геометрии! 🥛",
    ),
    "zoomies": (
        "ТЫГЫДЫК-ТАЙМ! Удержи кота и собирай минимум x3 лапок! ⚡",
        "Режим ночного тыгыдыка активирован! Все клики усилены! 🚀",
        "Саян носится по комнате со скоростью 3.14 м/с! Лови момент! 🐾💨",
    ),
    "quiz_win": (
        "Блестяще! +30 лапок и твёрдая пятёрка от Саяна! 🏆",
        "Математический мурр-гений! +30 лапок в копилку! ✨",
        "Верно! Даже профессор геометрии и тыгыдыка аплодирует лапками! 🎓",
    ),
    "milestone": (
        "Новая отметка достигнута! Саян гордится твоим упорством! 🎉",
        "Праздничное мурлыканье! Впереди ещё больше открытий и пятёрок! 🏆",
    ),
}


@dataclass(frozen=True)
class LevelInfo:
    """Computed progression rank for a given pets_count."""

    index: int
    title: str
    threshold: int
    next_threshold: int | None
    next_title: str | None
    progress_ratio: float


@dataclass(frozen=True)
class TreatEvent:
    """Floating clickable treat mini-event."""

    kind: str
    label: str
    emoji: str
    bonus: int
    spawned_at: float
    expires_at: float

    def is_expired(self, now: float) -> bool:
        """Return True once the treat window has elapsed."""
        return now >= self.expires_at


@dataclass(frozen=True)
class MathMicroQuiz:
    """Short 3-option math/cat riddle mini-event."""

    question: str
    options: tuple[str, str, str]
    correct_index: int
    reward: int = QUIZ_REWARD
    explanation: str = ""


MATH_QUIZ_BANK: tuple[MathMicroQuiz, ...] = (
    MathMicroQuiz(
        question="2² + 1 = ?",
        options=("4", "5", "6"),
        correct_index=1,
        explanation="2² = 4, плюс 1 — получается твёрдая пятёрка!",
    ),
    MathMicroQuiz(
        question="Сумма углов треугольника?",
        options=("90°", "180°", "360°"),
        correct_index=1,
        explanation="Классика 7 класса: в любом треугольнике 180°!",
    ),
    MathMicroQuiz(
        question="Сколько лап у двух Саянов?",
        options=("4", "6", "8"),
        correct_index=2,
        explanation="2 × 4 = 8 мягких лапок для двойного уюта!",
    ),
    MathMicroQuiz(
        question="√25 = ?",
        options=("4", "5", "6"),
        correct_index=1,
        explanation="5 × 5 = 25, значит корень равен 5!",
    ),
    MathMicroQuiz(
        question="Чему равен π ≈ ?",
        options=("3.14", "2.71", "1.61"),
        correct_index=0,
        explanation="Число Пи-Мурр ≈ 3.14159 — главный кошачий праздник!",
    ),
    MathMicroQuiz(
        question="(3 + 2) × 1 = ?",
        options=("5", "6", "32"),
        correct_index=0,
        explanation="Сначала скобки: 3 + 2 = 5, умножить на 1 = 5!",
    ),
    MathMicroQuiz(
        question="Периметр квадрата со стороной 5?",
        options=("10", "20", "25"),
        correct_index=1,
        explanation="У квадрата 4 равные стороны: 5 × 4 = 20!",
    ),
    MathMicroQuiz(
        question="Гипотенуза при катетах 3 и 4?",
        options=("5", "7", "12"),
        correct_index=0,
        explanation="Знаменитый египетский треугольник 3–4–5 по Пифагору!",
    ),
    MathMicroQuiz(
        question="10% от 50 — сколько это рыбок?",
        options=("5", "10", "15"),
        correct_index=0,
        explanation="Делим 50 на 10 и получаем 5 вкусных рыбок!",
    ),
    MathMicroQuiz(
        question="Если 3x = 15, то x = ?",
        options=("3", "5", "45"),
        correct_index=1,
        explanation="15 / 3 = 5 — уравнение решено быстрее мурлыканья!",
    ),
    MathMicroQuiz(
        question="Сколько спит Саян за 2 дня, если спит 16 ч/день?",
        options=("24 ч", "32 ч", "48 ч"),
        correct_index=1,
        explanation="16 × 2 = 32 часа крепкого кошачьего сна!",
    ),
    MathMicroQuiz(
        question="Площадь прямоугольника 4 × 6 = ?",
        options=("10", "20", "24"),
        correct_index=2,
        explanation="Ширина × длина: 4 × 6 = 24!",
    ),
    MathMicroQuiz(
        question="(-2)² = ?",
        options=("-4", "4", "2"),
        correct_index=1,
        explanation="Минус на минус в квадрате даёт плюс: (-2) × (-2) = 4!",
    ),
    MathMicroQuiz(
        question="Сколько вершин у пятиугольника?",
        options=("4", "5", "6"),
        correct_index=1,
        explanation="Пять углов, пять сторон и пять вершин!",
    ),
    MathMicroQuiz(
        question="Среднее арифметическое чисел 4 и 6?",
        options=("4", "5", "10"),
        correct_index=1,
        explanation="(4 + 6) / 2 = 5 — отличная оценка!",
    ),
    MathMicroQuiz(
        question="7 × 8 = ?",
        options=("54", "64", "56"),
        correct_index=2,
        explanation="7 × 8 = 56 — таблица умножения в деле!",
    ),
    MathMicroQuiz(
        question="Сколько минут в 3 часах?",
        options=("120", "150", "180"),
        correct_index=2,
        explanation="3 × 60 = 180 минут уютного времени!",
    ),
    MathMicroQuiz(
        question="2⁵ = ?",
        options=("10", "25", "32"),
        correct_index=2,
        explanation="2×2×2×2×2 = 32 — степень растёт как аппетит Саяна!",
    ),
    MathMicroQuiz(
        question="Если x + 7 = 12, то x = ?",
        options=("5", "6", "19"),
        correct_index=0,
        explanation="12 − 7 = 5 — уравнение решено!",
    ),
    MathMicroQuiz(
        question="Сумма углов квадрата?",
        options=("180°", "270°", "360°"),
        correct_index=2,
        explanation="Четыре прямых угла по 90°: 4 × 90 = 360°!",
    ),
    MathMicroQuiz(
        question="√81 = ?",
        options=("8", "9", "7"),
        correct_index=1,
        explanation="9 × 9 = 81, значит корень равен 9!",
    ),
    MathMicroQuiz(
        question="25% от 80 — сколько это?",
        options=("20", "25", "40"),
        correct_index=0,
        explanation="Четверть от 80: 80 / 4 = 20!",
    ),
    MathMicroQuiz(
        question="Сколько лап у 5 Саянов?",
        options=("15", "25", "20"),
        correct_index=2,
        explanation="5 × 4 = 20 мягких лапок!",
    ),
    MathMicroQuiz(
        question="12 × 12 = ?",
        options=("124", "144", "148"),
        correct_index=1,
        explanation="12 × 12 = 144 — дюжина дюжин!",
    ),
    MathMicroQuiz(
        question="Периметр треугольника со сторонами 3, 4 и 5?",
        options=("12", "15", "20"),
        correct_index=0,
        explanation="3 + 4 + 5 = 12 — тот самый египетский треугольник!",
    ),
    MathMicroQuiz(
        question="Если 2x = 18, то x = ?",
        options=("8", "9", "16"),
        correct_index=1,
        explanation="18 / 2 = 9 — быстрее мурлыканья!",
    ),
    MathMicroQuiz(
        question="Сколько секунд в 5 минутах?",
        options=("250", "500", "300"),
        correct_index=2,
        explanation="5 × 60 = 300 секунд!",
    ),
    MathMicroQuiz(
        question="(-3) × (-4) = ?",
        options=("-12", "12", "7"),
        correct_index=1,
        explanation="Минус на минус даёт плюс: 3 × 4 = 12!",
    ),
    MathMicroQuiz(
        question="Площадь квадрата со стороной 7?",
        options=("14", "28", "49"),
        correct_index=2,
        explanation="7 × 7 = 49 — сторона в квадрате!",
    ),
    MathMicroQuiz(
        question="Среднее арифметическое чисел 2, 4 и 6?",
        options=("4", "5", "6"),
        correct_index=0,
        explanation="(2 + 4 + 6) / 3 = 12 / 3 = 4!",
    ),
    MathMicroQuiz(
        question="3² + 4² = ?",
        options=("25", "49", "12"),
        correct_index=0,
        explanation="9 + 16 = 25 — Пифагор снова здоровается!",
    ),
    MathMicroQuiz(
        question="Сколько граней у куба?",
        options=("4", "6", "8"),
        correct_index=1,
        explanation="У куба 6 граней — как у игрального кубика!",
    ),
    MathMicroQuiz(
        question="100 − 37 = ?",
        options=("63", "67", "73"),
        correct_index=0,
        explanation="100 − 37 = 63 — простой счёт!",
    ),
    MathMicroQuiz(
        question="Если 5x = 45, то x = ?",
        options=("8", "10", "9"),
        correct_index=2,
        explanation="45 / 5 = 9 — уравнение решено!",
    ),
    MathMicroQuiz(
        question="Сколько часов в 3 сутках?",
        options=("48", "60", "72"),
        correct_index=2,
        explanation="3 × 24 = 72 часа — три дня кошачьего уюта!",
    ),
    MathMicroQuiz(
        question="0.5 × 60 = ?",
        options=("30", "35", "60"),
        correct_index=0,
        explanation="Половина от 60: 60 / 2 = 30!",
    ),
    MathMicroQuiz(
        question="Сколько сторон у шестиугольника?",
        options=("5", "6", "8"),
        correct_index=1,
        explanation="Шести-угольник: шесть сторон и шесть вершин!",
    ),
    MathMicroQuiz(
        question="7² = ?",
        options=("42", "49", "56"),
        correct_index=1,
        explanation="7 × 7 = 49!",
    ),
    MathMicroQuiz(
        question="Делим 36 рыбок на 4 Саянов. Сколько каждому?",
        options=("8", "10", "9"),
        correct_index=2,
        explanation="36 / 4 = 9 рыбок каждому — поровну!",
    ),
    MathMicroQuiz(
        question="2 × 3 × 4 = ?",
        options=("12", "24", "9"),
        correct_index=1,
        explanation="2 × 3 = 6, затем 6 × 4 = 24!",
    ),
)


@dataclass(frozen=True)
class PetResult:
    """Outcome of a single pet click."""

    points_gained: int
    multiplier: int
    multiplier_label: str
    combo_streak: int
    wake_bonus: int
    woke_up: bool
    mood: str
    effective_sprite: str
    quote: str
    quote_category: str
    level_up: LevelInfo | None
    new_milestones: tuple[int, ...]
    zoomies_started: bool
    zoomies_active: bool
    spawned_treat: TreatEvent | None
    spawned_quiz: MathMicroQuiz | None
    purr_energy: int


@dataclass(frozen=True)
class EventClaimResult:
    """Outcome of claiming the active treat event."""

    claimed: bool
    treat: TreatEvent | None
    points_gained: int
    quote: str
    level_up: LevelInfo | None
    new_milestones: tuple[int, ...]


@dataclass(frozen=True)
class QuizAnswerResult:
    """Outcome of answering the active micro-quiz."""

    correct: bool
    points_gained: int
    correct_index: int
    quote: str
    explanation: str
    level_up: LevelInfo | None
    new_milestones: tuple[int, ...]


@dataclass(frozen=True)
class TickResult:
    """Outcome of a periodic timer tick."""

    mood: str
    entered_sleep: bool
    zoomies_ended: bool
    treat_expired: bool
    spawned_treat: TreatEvent | None
    spawned_quiz: MathMicroQuiz | None
    quote: str | None


def get_combo_multiplier(streak: int) -> int:
    """Return the combo multiplier tier for the given streak."""
    if streak >= 25:
        return 5
    if streak >= 12:
        return 3
    if streak >= 5:
        return 2
    return 1


def format_multiplier_label(multiplier: int, zoomies_active: bool = False) -> str:
    """Return human-readable multiplier badge text."""
    if multiplier >= 5:
        return "x5 «Пятёрочный!»"
    if zoomies_active and multiplier >= 3:
        return f"x{multiplier} «Тыгыдык!»"
    return f"x{multiplier}"


def get_level_info(pets_count: int) -> LevelInfo:
    """Compute current rank, next threshold, and progress ratio from pets_count."""
    count = max(0, pets_count)
    current_idx = 0
    for idx, (threshold, _) in enumerate(LEVELS):
        if count >= threshold:
            current_idx = idx
        else:
            break

    threshold, title = LEVELS[current_idx]
    if current_idx + 1 < len(LEVELS):
        next_threshold, next_title = LEVELS[current_idx + 1]
        span = max(1, next_threshold - threshold)
        progress = min(1.0, max(0.0, (count - threshold) / span))
    else:
        next_threshold = None
        next_title = None
        progress = 1.0

    return LevelInfo(
        index=current_idx + 1,
        title=title,
        threshold=threshold,
        next_threshold=next_threshold,
        next_title=next_title,
        progress_ratio=progress,
    )


@dataclass
class SayanGameState:
    """Pure game engine for Sayan Clicker without any GUI dependencies."""

    pets_count: int = 0
    best_combo: int = 0
    total_events_caught: int = 0
    quizzes_solved: int = 0
    unlocked_milestones: list[int] = field(default_factory=list)
    active_photo_mode: str = "auto"
    custom_photo_path: str | None = None

    mood: str = "curious"
    combo_streak: int = 0
    purr_energy: int = 0
    session_clicks: int = 0
    last_pet_at: float | None = None
    zoomies_until: float | None = None
    last_zoomies_at: float | None = None
    active_treat: TreatEvent | None = None
    active_quiz: MathMicroQuiz | None = None
    current_quote: str = "Мяу! Я Саян — погладь меня для заряда уюта и пятёрок! 🐾"

    _idle_anchor_at: float | None = field(default=None, repr=False)
    _last_treat_click: int = field(default=0, repr=False)
    _last_quiz_click: int = field(default=0, repr=False)
    _last_tick_event_at: float | None = field(default=None, repr=False)
    _sleep_cycle_idx: int = field(default=0, repr=False)
    _last_treat_kind: str | None = field(default=None, repr=False)
    _quote_cursors: dict[str, int] = field(default_factory=dict, repr=False)
    _quiz_cursor: int = field(default=0, repr=False)
    _rng: random.Random = field(default_factory=random.Random, repr=False)

    @classmethod
    def from_config(
        cls,
        config: Mapping[str, Any],
        rng: random.Random | None = None,
    ) -> SayanGameState:
        """Create a SayanGameState hydrated from a storage config dictionary."""
        raw_milestones = config.get("unlocked_milestones", [])
        milestones = sorted(
            {
                m
                for m in raw_milestones
                if isinstance(m, int) and not isinstance(m, bool) and m > 0
            }
        )
        photo_mode = config.get("active_photo_mode", "auto")
        if photo_mode not in ("auto", "custom"):
            photo_mode = "auto"

        custom_path = config.get("custom_photo_path")
        if not isinstance(custom_path, str) or not custom_path.strip():
            custom_path = None

        return cls(
            pets_count=max(0, int(config.get("pets_count", 0) or 0)),
            best_combo=max(0, int(config.get("best_combo", 0) or 0)),
            total_events_caught=max(0, int(config.get("total_events_caught", 0) or 0)),
            quizzes_solved=max(0, int(config.get("quizzes_solved", 0) or 0)),
            unlocked_milestones=milestones,
            active_photo_mode=photo_mode,
            custom_photo_path=custom_path,
            _rng=rng if rng is not None else random.Random(),
        )

    def to_config_updates(self) -> dict[str, Any]:
        """Export persistent game fields to merge into save.json."""
        return {
            "pets_count": self.pets_count,
            "best_combo": self.best_combo,
            "total_events_caught": self.total_events_caught,
            "quizzes_solved": self.quizzes_solved,
            "active_photo_mode": self.active_photo_mode,
            "custom_photo_path": self.custom_photo_path,
            "unlocked_milestones": sorted(set(self.unlocked_milestones)),
        }

    def get_level_info(self) -> LevelInfo:
        """Return current level progression details."""
        return get_level_info(self.pets_count)

    def is_sleeping(self) -> bool:
        """Return True if Sayan is currently in a sleeping mood."""
        return self.mood in SLEEP_MOODS

    def is_zoomies_active(self, now: float | None = None) -> bool:
        """Return True while the zoomies boost is active."""
        ts = time.monotonic() if now is None else now
        return self.zoomies_until is not None and ts < self.zoomies_until

    def zoomies_remaining(self, now: float | None = None) -> float:
        """Return seconds remaining in active zoomies (or 0.0)."""
        ts = time.monotonic() if now is None else now
        if self.zoomies_until is None or ts >= self.zoomies_until:
            return 0.0
        return self.zoomies_until - ts

    def get_effective_sprite(self) -> str:
        """Return sprite key, honoring custom photo mode when configured."""
        if self.active_photo_mode == "custom" and self.custom_photo_path:
            return CUSTOM_MOOD
        return self.mood

    def set_photo_mode(
        self,
        mode: str,
        custom_photo_path: str | None = None,
    ) -> None:
        """Switch between automatic mood sprites and user's custom photo."""
        if mode not in ("auto", "custom"):
            raise ValueError(f"Unsupported photo mode: {mode}")
        self.active_photo_mode = mode
        if custom_photo_path is not None:
            stripped = custom_photo_path.strip()
            self.custom_photo_path = stripped or None

    def _next_quote(self, category: str) -> str:
        pool = CAT_QUOTES.get(category) or CAT_QUOTES["pet"]
        cursor = self._quote_cursors.get(category, 0)
        quote = pool[cursor % len(pool)]
        self._quote_cursors[category] = (cursor + 1) % len(pool)
        return quote

    def _award_points(self, delta: int) -> tuple[LevelInfo | None, tuple[int, ...]]:
        prev_level_idx = self.get_level_info().index
        self.pets_count += max(0, delta)
        new_level = self.get_level_info()
        level_up = new_level if new_level.index > prev_level_idx else None

        newly_unlocked: list[int] = []
        known = set(self.unlocked_milestones)
        for milestone in MILESTONES:
            if self.pets_count >= milestone and milestone not in known:
                self.unlocked_milestones.append(milestone)
                known.add(milestone)
                newly_unlocked.append(milestone)

        return level_up, tuple(newly_unlocked)

    def _can_trigger_zoomies(self, now: float) -> bool:
        if self.is_zoomies_active(now):
            return False
        if self.last_zoomies_at is None:
            return True
        return (now - self.last_zoomies_at) >= ZOOMIES_COOLDOWN_SECONDS

    def trigger_zoomies(
        self,
        now: float | None = None,
        duration: float = ZOOMIES_DURATION_SECONDS,
    ) -> float:
        """Start the zoomies frenzy immediately and return its expiration timestamp."""
        ts = time.monotonic() if now is None else now
        self.zoomies_until = ts + duration
        self.last_zoomies_at = ts
        self.mood = "zoomies"
        self.current_quote = self._next_quote("zoomies")
        return self.zoomies_until

    def spawn_treat(
        self,
        kind: str | None = None,
        now: float | None = None,
    ) -> TreatEvent:
        """Create and store a clickable treat event."""
        ts = time.monotonic() if now is None else now
        if kind is None:
            candidates = [k for k in TREAT_CATALOG if k != self._last_treat_kind]
            kind = self._rng.choice(candidates or list(TREAT_CATALOG))
        if kind not in TREAT_CATALOG:
            raise ValueError(f"Unknown treat kind: {kind}")

        label, emoji, bonus = TREAT_CATALOG[kind]
        treat = TreatEvent(
            kind=kind,
            label=label,
            emoji=emoji,
            bonus=bonus,
            spawned_at=ts,
            expires_at=ts + TREAT_LIFETIME_SECONDS,
        )
        self._last_treat_kind = kind
        self.active_treat = treat
        self._last_treat_click = self.session_clicks
        self._last_tick_event_at = ts
        return treat

    def claim_treat(self, now: float | None = None) -> EventClaimResult:
        """Claim the active treat if present and unexpired."""
        ts = time.monotonic() if now is None else now
        treat = self.active_treat
        if treat is None:
            return EventClaimResult(
                claimed=False,
                treat=None,
                points_gained=0,
                quote=self.current_quote,
                level_up=None,
                new_milestones=(),
            )
        if treat.is_expired(ts):
            self.active_treat = None
            return EventClaimResult(
                claimed=False,
                treat=None,
                points_gained=0,
                quote=self.current_quote,
                level_up=None,
                new_milestones=(),
            )

        self.active_treat = None
        self.total_events_caught += 1
        level_up, new_milestones = self._award_points(treat.bonus)

        if 314 in new_milestones:
            quote = MILESTONE_QUOTES[314]
        elif new_milestones:
            quote = MILESTONE_QUOTES.get(
                new_milestones[-1], self._next_quote("milestone")
            )
        else:
            quote = self._next_quote("treat")
        self.current_quote = quote

        return EventClaimResult(
            claimed=True,
            treat=treat,
            points_gained=treat.bonus,
            quote=quote,
            level_up=level_up,
            new_milestones=new_milestones,
        )

    def spawn_quiz(self, index: int | None = None) -> MathMicroQuiz:
        """Spawn a quick school-math or cat riddle micro-quiz."""
        if index is None:
            quiz = MATH_QUIZ_BANK[self._quiz_cursor % len(MATH_QUIZ_BANK)]
            self._quiz_cursor = (self._quiz_cursor + 1) % len(MATH_QUIZ_BANK)
        else:
            quiz = MATH_QUIZ_BANK[index % len(MATH_QUIZ_BANK)]
        self.active_quiz = quiz
        self._last_quiz_click = self.session_clicks
        return quiz

    def dismiss_quiz(self) -> None:
        """Dismiss the active quiz without penalty."""
        self.active_quiz = None

    def answer_quiz(
        self,
        option_index: int,
        now: float | None = None,
    ) -> QuizAnswerResult:
        """Evaluate user's answer to the active micro-quiz."""
        _ = time.monotonic() if now is None else now
        quiz = self.active_quiz
        if quiz is None:
            raise RuntimeError("No active quiz to answer.")
        if not 0 <= option_index < len(quiz.options):
            raise ValueError(f"Option index out of range: {option_index}")

        self.active_quiz = None
        is_correct = option_index == quiz.correct_index

        if not is_correct:
            quote = (
                f"Ничего страшного! {quiz.explanation} Саян всегда подскажет 🐾"
                if quiz.explanation
                else "Ничего страшного, на следующем примере точно получится! 🐾"
            )
            self.current_quote = quote
            return QuizAnswerResult(
                correct=False,
                points_gained=0,
                correct_index=quiz.correct_index,
                quote=quote,
                explanation=quiz.explanation,
                level_up=None,
                new_milestones=(),
            )

        self.quizzes_solved += 1
        self.total_events_caught += 1
        level_up, new_milestones = self._award_points(quiz.reward)

        if 314 in new_milestones:
            quote = MILESTONE_QUOTES[314]
        elif new_milestones:
            quote = MILESTONE_QUOTES.get(
                new_milestones[-1], self._next_quote("milestone")
            )
        else:
            quote = self._next_quote("quiz_win")
        self.current_quote = quote

        return QuizAnswerResult(
            correct=True,
            points_gained=quiz.reward,
            correct_index=quiz.correct_index,
            quote=quote,
            explanation=quiz.explanation,
            level_up=level_up,
            new_milestones=new_milestones,
        )

    def _select_awake_mood(self) -> str:
        if self.combo_streak >= 10:
            return HIGH_COMBO_MOODS[
                (self.session_clicks // 2) % len(HIGH_COMBO_MOODS)
            ]
        return AWAKE_MOODS[(self.session_clicks // 2) % len(AWAKE_MOODS)]

    def _choose_pet_quote(
        self,
        *,
        new_milestones: tuple[int, ...],
        woke_up: bool,
        zoomies_started: bool,
        zoomies_active: bool,
    ) -> tuple[str, str]:
        if woke_up:
            return self._next_quote("wake"), "wake"
        if new_milestones:
            if 314 in new_milestones:
                return MILESTONE_QUOTES[314], "milestone"
            latest = new_milestones[-1]
            return (
                MILESTONE_QUOTES.get(latest, self._next_quote("milestone")),
                "milestone",
            )
        if zoomies_started or zoomies_active:
            return self._next_quote("zoomies"), "zoomies"
        if self.combo_streak in (5, 12, 25) or (
            self.combo_streak >= 10 and self.combo_streak % 10 == 0
        ):
            return self._next_quote("combo"), "combo"
        if self.session_clicks % 3 == 0:
            return self._next_quote("math_easter_egg"), "math_easter_egg"
        return self._next_quote("pet"), "pet"

    def pet(self, now: float | None = None) -> PetResult:
        """Process a single pet click on Sayan and update combo, mood, and events."""
        ts = time.monotonic() if now is None else now

        # Clear expired treat or zoomies before resolving click
        if self.active_treat is not None and self.active_treat.is_expired(ts):
            self.active_treat = None
        if self.zoomies_until is not None and ts >= self.zoomies_until:
            self.zoomies_until = None

        was_sleeping = self.is_sleeping()
        woke_up = False
        wake_bonus = 0

        if was_sleeping:
            woke_up = True
            wake_bonus = WAKE_UP_BONUS
            self.combo_streak = 1
        elif (
            self.last_pet_at is not None
            and (ts - self.last_pet_at) <= COMBO_WINDOW_SECONDS
        ):
            self.combo_streak += 1
        else:
            self.combo_streak = 1

        self.best_combo = max(self.best_combo, self.combo_streak)
        self.session_clicks += 1
        self.last_pet_at = ts
        self._idle_anchor_at = ts

        zoomies_active = self.is_zoomies_active(ts)
        energy_gain = 14 if zoomies_active else 7
        self.purr_energy = min(MAX_PURR_ENERGY, self.purr_energy + energy_gain)

        zoomies_started = False
        if not zoomies_active and self._can_trigger_zoomies(ts):
            if (
                self.combo_streak >= 15 and self.combo_streak % 15 == 0
            ) or self.purr_energy >= MAX_PURR_ENERGY:
                self.trigger_zoomies(now=ts)
                zoomies_active = True
                zoomies_started = True
                self.purr_energy = 0

        if zoomies_active:
            self.mood = "zoomies"
        elif woke_up:
            self.mood = "curious"
        else:
            self.mood = self._select_awake_mood()

        base_mult = get_combo_multiplier(self.combo_streak)
        multiplier = max(base_mult, 3) if zoomies_active else base_mult
        multiplier_label = format_multiplier_label(
            multiplier, zoomies_active=zoomies_active
        )
        points_gained = multiplier + wake_bonus

        level_up, new_milestones = self._award_points(points_gained)

        spawned_treat: TreatEvent | None = None
        spawned_quiz: MathMicroQuiz | None = None
        if self.active_treat is None and self.active_quiz is None:
            if (
                self.session_clicks >= 10
                and (self.session_clicks - self._last_quiz_click) >= CLICK_QUIZ_CADENCE
            ):
                spawned_quiz = self.spawn_quiz()
            elif (self.session_clicks - self._last_treat_click) >= CLICK_TREAT_CADENCE:
                spawned_treat = self.spawn_treat(now=ts)

        quote, quote_category = self._choose_pet_quote(
            new_milestones=new_milestones,
            woke_up=woke_up,
            zoomies_started=zoomies_started,
            zoomies_active=zoomies_active,
        )
        self.current_quote = quote

        return PetResult(
            points_gained=points_gained,
            multiplier=multiplier,
            multiplier_label=multiplier_label,
            combo_streak=self.combo_streak,
            wake_bonus=wake_bonus,
            woke_up=woke_up,
            mood=self.mood,
            effective_sprite=self.get_effective_sprite(),
            quote=quote,
            quote_category=quote_category,
            level_up=level_up,
            new_milestones=new_milestones,
            zoomies_started=zoomies_started,
            zoomies_active=zoomies_active,
            spawned_treat=spawned_treat,
            spawned_quiz=spawned_quiz,
            purr_energy=self.purr_energy,
        )

    def tick(self, now: float | None = None) -> TickResult:
        """Advance timers: expire treats/zoomies, enter sleep if idle, or spawn treats."""
        ts = time.monotonic() if now is None else now

        if self._idle_anchor_at is None:
            self._idle_anchor_at = self.last_pet_at if self.last_pet_at is not None else ts
        if self._last_tick_event_at is None:
            self._last_tick_event_at = ts

        treat_expired = False
        if self.active_treat is not None and self.active_treat.is_expired(ts):
            self.active_treat = None
            treat_expired = True

        zoomies_ended = False
        if self.zoomies_until is not None and ts >= self.zoomies_until:
            self.zoomies_until = None
            zoomies_ended = True
            if self.mood == "zoomies":
                self.mood = "curious"

        if (
            self.last_pet_at is not None
            and (ts - self.last_pet_at) > COMBO_WINDOW_SECONDS
        ):
            self.combo_streak = 0

        idle_since = self.last_pet_at if self.last_pet_at is not None else self._idle_anchor_at
        idle_elapsed = ts - idle_since

        entered_sleep = False
        quote: str | None = None
        if (
            idle_elapsed > SLEEP_IDLE_SECONDS
            and not self.is_zoomies_active(ts)
            and not self.is_sleeping()
        ):
            sleep_mood = SLEEP_MOODS[self._sleep_cycle_idx % len(SLEEP_MOODS)]
            self._sleep_cycle_idx = (self._sleep_cycle_idx + 1) % len(SLEEP_MOODS)
            self.mood = sleep_mood
            self.combo_streak = 0
            entered_sleep = True
            quote = self._next_quote("sleep")
            self.current_quote = quote

        spawned_treat: TreatEvent | None = None
        if (
            not self.is_sleeping()
            and self.active_treat is None
            and self.active_quiz is None
            and (ts - self._last_tick_event_at) >= TICK_TREAT_INTERVAL_SECONDS
        ):
            spawned_treat = self.spawn_treat(now=ts)

        return TickResult(
            mood=self.mood,
            entered_sleep=entered_sleep,
            zoomies_ended=zoomies_ended,
            treat_expired=treat_expired,
            spawned_treat=spawned_treat,
            spawned_quiz=None,
            quote=quote,
        )
