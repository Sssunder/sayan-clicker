#!/usr/bin/env python3
"""Generate docs/quiz-data.js: per-grade (1-11) math question banks with hints.

Topics follow the Russian school curriculum (Моро, Петерсон, Виленкин, Мерзляк,
Макарычев, Атанасян, Алимов, ОГЭ/ЕГЭ сборники). Every numeric answer and
distractor is computed, never hand-typed. Deterministic seed keeps banks
reproducible. Run:  python scripts/generate_quiz.py
"""
import json
import math
import random
from pathlib import Path

R = random.Random(20261115)
BANKS = {g: [] for g in range(1, 12)}
SEEN = set()
CUR = 1

CATS = {
    "count": "Счёт", "frac": "Дроби", "pct": "Проценты", "pow": "Степени и корни",
    "eq": "Уравнения", "geom": "Геометрия", "word": "Задачка про котов",
    "oge": "ОГЭ-формат", "prob": "Вероятность", "cat": "Кошачья логика",
    "trig": "Тригонометрия", "der": "Производная", "int": "Интегралы",
    "log": "Логарифмы", "stat": "Статистика", "alg": "Алгебра",
}

SUP = str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻")


def sup(n):
    return str(n).translate(SUP)


def N(x):
    if isinstance(x, (int, float)) and x == 0:
        return "0"
    if isinstance(x, int):
        return str(x).replace("-", "−")
    s = f"{round(x, 6):.6f}".rstrip("0").rstrip(".")
    return s.replace(".", ",").replace("-", "−")


def fs(a, b):
    g = math.gcd(a, b)
    a, b = a // g, b // g
    return f"{a}/{b}" if b != 1 else str(a)


def pick(seq):
    return R.choice(seq)


def times(n):
    return "раза" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "раз"


def add(cat, q, ans, hint, expl, wrong):
    a = N(ans) if isinstance(ans, (int, float)) else str(ans)
    opts = [a]
    for w in wrong:
        w = N(w) if isinstance(w, (int, float)) else str(w)
        if CUR <= 2 and (w.startswith("−") or w.startswith("-")):
            continue
        if w not in opts:
            opts.append(w)
        if len(opts) == 3:
            break
    if len(opts) < 3 and isinstance(ans, (int, float)):
        for d in (1, 2, 3, 10, 4, 5):
            v = ans + d
            if CUR <= 2 and v < 0:
                continue
            w = N(v)
            if w not in opts:
                opts.append(w)
            if len(opts) == 3:
                break
    if len(opts) < 3:
        raise ValueError(f"not enough distractors: {q}")
    idx = [0, 1, 2]
    R.shuffle(idx)
    BANKS[CUR].append({"q": q, "o": [opts[i] for i in idx], "c": idx.index(0),
                       "h": hint, "e": expl, "cat": cat})


def gen(cat, n, make):
    made = attempts = 0
    while made < n and attempts < n * 80:
        attempts += 1
        item = make()
        if item is None:
            continue
        q, ans, hint, expl, wrong = item
        if q in SEEN:
            continue
        SEEN.add(q)
        add(cat, q, ans, hint, expl, wrong)
        made += 1
    if made < n:
        raise RuntimeError(f"grade {CUR} {cat}: only {made}/{n}")


# ============================================================ 1 класс (Моро)
def gen_g1():
    def addsub10():
        if R.random() < .5:
            a = R.randint(1, 9)
            b = R.randint(1, 10 - a)
            return (f"{a} + {b} = ?", a + b, "Считай по пальчикам или по линейке.",
                    f"{a} + {b} = {a + b}!", [a + b + 1, a + b + 2, a + b + 3])
        a = R.randint(2, 10)
        b = R.randint(1, a)
        return (f"{a} − {b} = ?", a - b, "Отними b от a: шагай назад по линейке.",
                f"{a} − {b} = {a - b}!", [a - b + 1, a - b + 2, a + b])
    gen("count", 15, addsub10)

    def addsub20():
        if R.random() < .5:
            a, b = R.randint(6, 9), R.randint(6, 9)
            return (f"{a} + {b} = ?", a + b, "Дополни первое число до 10, потом прибавь остаток.",
                    f"{a} + {b} = {a + b}: через десяток!", [a + b + 1, a + b - 1, a + b + 2])
        a, b = R.randint(11, 18), R.randint(2, 9)
        return (f"{a} − {b} = ?", a - b, "Разбей вычитание: сначала до 10, потом ещё.",
                f"{a} − {b} = {a - b}!", [a - b + 1, a - b - 1, a - b + 2])
    gen("count", 15, addsub20)

    def compose():
        n = pick([6, 7, 8, 9, 10])
        a = R.randint(1, n - 1)
        return (f"{n} = {a} + …? Какое число спряталось?", n - a,
                "Подумай, сколько не хватает до n.", f"{a} + {n - a} = {n}!",
                [n - a + 1, n - a + 2, a])
    gen("count", 10, compose)

    def compare():
        a, b = R.sample(range(1, 21), 2)
        return (f"Что больше: {a} или {b}?", max(a, b),
                "Большее число стоит правее на числовой прямой.",
                f"{max(a, b)} больше, чем {min(a, b)}!", [min(a, b), "Равны"])
    gen("count", 10, compare)

    def seq():
        a, d = R.randint(1, 10), pick([1, 2])
        s = [a, a + d, a + 2 * d]
        return (f"Продолжи ряд: {', '.join(map(str, s))}, …?", a + 3 * d,
                "Посмотри, на сколько растёт каждый шаг.", f"Шаг +{d}: {s[-1]} + {d} = {a + 3 * d}!",
                [a + 3 * d + 1, a + 3 * d + 2, a + 2 * d])
    gen("count", 10, seq)

    def word():
        if R.random() < .5:
            a, b = R.randint(2, 9), R.randint(1, 9)
            return (f"У Саяна {a} рыбок, Мурка дала ещё {b}. Сколько стало?", a + b,
                    "«Дала ещё» — прибавляй.", f"{a} + {b} = {a + b} рыбок!",
                    [a + b + 1, a + b + 2, a - b if a > b else a + b + 3])
        a = R.randint(5, 15)
        b = R.randint(1, a - 1)
        return (f"У Саяна {a} рыбок, {b} он съел. Сколько осталось?", a - b,
                "«Съел» — вычитай.", f"{a} − {b} = {a - b} рыбок!",
                [a - b + 1, a - b + 2, a + b])
    gen("word", 15, word)

    def shapes():
        items = [
            ("Сколько углов у треугольника?", 3, "Треугольник — три угла.", "У треугольника 3 угла!", [4, 5]),
            ("Сколько сторон у квадрата?", 4, "Квадрат — четыре равные стороны.", "У квадрата 4 стороны!", [3, 5]),
            ("Сколько вершин у круга?", 0, "У круга нет углов и вершин.", "Круг гладкий — вершин 0!", [1, 2]),
            ("Сколько сторон у прямоугольника?", 4, "Как у квадрата, но стороны разной длины.", "4 стороны!", [3, 6]),
            ("У какой фигуры все стороны равны?", "Квадрат", "Вспомни фигуру с 4 равными сторонами.", "У квадрата все 4 стороны равны!", ["Прямоугольник", "Треугольник"]),
            ("Сколько углов у квадрата?", 4, "У квадрата четыре угла.", "У квадрата 4 угла!", [3, 5]),
            ("Сколько сторон у треугольника?", 3, "Треугольник — три стороны.", "У треугольника 3 стороны!", [4, 5]),
            ("У какой фигуры нет углов?", "Круг", "Круг гладкий, без углов.", "У круга нет углов!", ["Квадрат", "Треугольник"]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("geom", 8, shapes)

    def timeq():
        items = [
            ("Сколько дней в неделе?", 7, "Пн, Вт, Ср, Чт, Пт, Сб, Вс.", "7 дней!", [5, 6]),
            ("Сколько месяцев в году?", 12, "От января до декабря.", "12 месяцев!", [10, 11]),
            ("Сколько часов в сутках?", 24, "День и ночь вместе.", "24 часа!", [12, 20]),
            ("Сколько минут в одном часе?", 60, "Час — это 60 минут.", "60 минут!", [30, 100]),
            ("Какой день идёт после среды?", "Четверг", "Вспомни порядок дней недели.", "После среды — четверг!", ["Пятница", "Вторник"]),
            ("Сколько времён года?", 4, "Зима, весна, лето, осень.", "4 времени года!", [3, 5]),
            ("Какой день идёт перед пятницей?", "Четверг", "Вспомни порядок дней недели.", "Перед пятницей — четверг!", ["Среда", "Суббота"]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("cat", 7, timeq)

    def logic():
        items = [
            ("Что лишнее: 2, 4, 5, 6, 8?", 5, "Проверь, какое число нечётное.", "5 — нечётное, остальные чётные!", [4, 6]),
            ("Саян выше Мурки, Мурка выше Барсика. Кто самый низкий?", "Барсик", "Выстрой котов по росту.", "Барсик ниже всех!", ["Саян", "Мурка"]),
            ("Все коты любят спать. Саян — кот. Значит…", "Саян любит спать", "Примени правило к Саяну.", "Саян любит спать!", ["Саян не любит спать", "Все спящие — коты"]),
            ("Что тяжелее: кг пуха или кг корма?", "Одинаково", "Сравнивай килограммы, а не объём.", "Килограмм есть килограмм!", ["Пух", "Корм"]),
            ("Продолжи: 🐾🐟🐾… Что дальше?", "🐾", "Ряд чередует лапку и рыбку.", "Дальше снова 🐾!", ["🐟", "🐟🐟"]),
            ("Что лишнее: 1, 3, 4, 5, 7?", 4, "Проверь, какое число чётное.", "4 — чётное, остальные нечётные!", [3, 5]),
            ("Саян старше Барсика, Барсик старше Мурки. Кто самый старший?", "Саян", "Выстрой котов по возрасту.", "Саян старше всех!", ["Барсик", "Мурка"]),
            ("У кота 2 уха. Сколько ушей у двух котов?", 4, "У каждого кота по 2 уха.", "2 + 2 = 4 уха!", [2, 6]),
            ("Продолжи: 🐟🐟🐾🐟🐟… Что дальше?", "🐾", "После двух рыбок идёт лапка.", "Дальше снова 🐾!", ["🐟", "🐟🐟"]),
            ("Что лишнее: квадрат, круг, треугольник, яблоко?", "Яблоко", "Три фигуры и один фрукт.", "Яблоко — не фигура!", ["Круг", "Квадрат"]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("cat", 10, logic)


# ============================================================ 2 класс
def gen_g2():
    def addsub100():
        if R.random() < .5:
            a, b = R.randint(11, 60), R.randint(11, 39)
            return (f"{a} + {b} = ?", a + b, "Складывай десятки с десятками, единицы с единицами.",
                    f"{a} + {b} = {a + b}!", [a + b + 10, a + b - 1, a + b + 1])
        a, b = R.randint(30, 99), R.randint(11, 29)
        return (f"{a} − {b} = ?", a - b, "Вычитай по разрядам.", f"{a} − {b} = {a - b}!",
                [a - b + 10, a - b - 1, a - b + 1])
    gen("count", 15, addsub100)

    def mult():
        a, b = R.randint(2, 5), R.randint(2, 9)
        return (f"{a} × {b} = ?", a * b, "Вспомни таблицу умножения на a.",
                f"{a} × {b} = {a * b}!", [a * b + a, a * b - b, a * (b + 1)])
    gen("count", 15, mult)

    def div():
        b, q = R.randint(2, 5), R.randint(2, 9)
        return (f"{b * q} ÷ {b} = ?", q, f"Какое число × {b} даёт {b * q}?",
                f"{b * q} ÷ {b} = {q}!", [q + 1, q - 1, q + 2])
    gen("count", 10, div)

    def order():
        t = R.randint(0, 2)
        if t == 0:
            a, b, c = R.randint(1, 9), R.randint(2, 5), R.randint(2, 5)
            return (f"{a} + {b} × {c} = ?", a + b * c, "Сначала умножение, потом сложение.",
                    f"{b} × {c} = {b * c}, затем {a} + {b * c} = {a + b * c}!",
                    [(a + b) * c, a + b * c + 1, a + b + c])
        if t == 1:
            a, b, c = R.randint(1, 9), R.randint(1, 9), R.randint(2, 5)
            return (f"({a} + {b}) × {c} = ?", (a + b) * c, "Скобки сначала.",
                    f"{a} + {b} = {a + b}, затем × {c} = {(a + b) * c}!",
                    [a + b * c, (a + b) * c + c, a + b + c])
        a, b, c = R.randint(1, 3), R.randint(2, 5), R.randint(2, 5)
        return (f"{b} × {c} − {a} = ?", b * c - a, "Умножение раньше вычитания.",
                f"{b} × {c} = {b * c}, минус {a} = {b * c - a}!",
                [b * (c - a) if c > a else b * c - a + 1, b * c - a + 1, b * c + a])
    gen("count", 10, order)

    def eq():
        t = R.randint(0, 2)
        if t == 0:
            a, x = R.randint(5, 40), R.randint(3, 30)
            return (f"x + {a} = {x + a}. Найди x.", x, "Перенеси a вправо с минусом.",
                    f"x = {x + a} − {a} = {x}!", [x + 1, x + a, x + 2])
        if t == 1:
            a, x = R.randint(5, 40), R.randint(3, 30)
            return (f"x − {a} = {x}. Найди x.", x + a, "Перенеси −a вправо как +a.",
                    f"x = {x} + {a} = {x + a}!", [x, x + a + 1, x + a - 1])
        a, x = R.randint(2, 5), R.randint(2, 9)
        return (f"{a} × x = {a * x}. Найди x.", x, f"Раздели {a * x} на {a}.",
                f"x = {a * x} ÷ {a} = {x}!", [x + 1, x - 1, a * x])
    gen("eq", 8, eq)

    def word():
        t = R.randint(0, 2)
        if t == 0:
            p, n = R.randint(2, 5), R.randint(3, 9)
            return (f"Вкусняшка стоит {p} лапок. Сколько за {n} штук?", p * n,
                    "Цена × количество.", f"{p} × {n} = {p * n} лапок!", [p + n, p * n + p, p * n - n])
        if t == 1:
            n, k = R.randint(2, 5), R.randint(3, 9)
            return (f"{n * k} рыбок поровну на {n} котов. Сколько каждому?", k,
                    "Поровну — значит деление.", f"{n * k} ÷ {n} = {k}!", [k + 1, k - 1, n * k - n])
        a, k = R.randint(2, 5), R.randint(2, 4)
        return (f"У Саяна {a} игрушек, у Мурки в {k} раза больше. Сколько у Мурки?", a * k,
                "«В k раза больше» — умножай.", f"{a} × {k} = {a * k}!", [a + k, a * k + a, a * k - 1])
    gen("word", 15, word)

    def perim():
        if R.random() < .5:
            a = R.randint(2, 9)
            return (f"Периметр квадрата со стороной {a}?", 4 * a, "4 равные стороны.",
                    f"{a} × 4 = {4 * a}!", [a * a, 2 * a, 4 * a + 4])
        a, b = R.randint(2, 9), R.randint(2, 9)
        return (f"Периметр прямоугольника {a} × {b}?", 2 * (a + b), "2 × (a + b).",
                f"2 × ({a} + {b}) = {2 * (a + b)}!", [a * b, a + b, 2 * (a + b) + 2])
    gen("geom", 8, perim)

    def units():
        items = [
            ("1 м = … см", 100, "В метре 100 сантиметров.", "1 м = 100 см!", [10, 1000]),
            ("1 ч = … мин", 60, "В часе 60 минут.", "1 ч = 60 мин!", [30, 100]),
            ("1 см = … мм", 10, "В сантиметре 10 миллиметров.", "1 см = 10 мм!", [100, 5]),
            ("1 мин = … с", 60, "В минуте 60 секунд.", "1 мин = 60 с!", [30, 100]),
            ("1 кг = … г", 1000, "В килограмме 1000 граммов.", "1 кг = 1000 г!", [100, 500]),
            ("1 дм = … см", 10, "В дециметре 10 сантиметров.", "1 дм = 10 см!", [100, 1]),
            ("1 м = … дм", 10, "В метре 10 дециметров.", "1 м = 10 дм!", [100, 1000]),
            ("1 сут = … ч", 24, "В сутках 24 часа.", "1 сут = 24 ч!", [12, 60]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("count", 8, units)

    def seq():
        a, d = R.randint(2, 20), pick([2, 3, 5])
        s = [a, a + d, a + 2 * d]
        return (f"Продолжи ряд: {', '.join(map(str, s))}, …?", a + 3 * d,
                "Найди шаг ряда.", f"Шаг +{d}: {s[-1]} + {d} = {a + 3 * d}!",
                [a + 3 * d + 1, a + 3 * d + d, a + 2 * d])
    gen("count", 6, seq)

    def logic():
        items = [
            ("Что лишнее: 3, 6, 9, 12, 14?", 14, "Все кроме одного делятся на 3.", "14 не делится на 3!", [6, 9]),
            ("Продолжи: Пн, Вт, Ср, …?", "Чт", "Дни недели по порядку.", "После среды — четверг!", ["Пт", "Сб"]),
            ("Сколько месяцев имеют 28 дней?", "Все 12", "В каждом месяце есть 28-е число.", "Все 12!", ["Один", "Два"]),
            ("У Саяна 12 усов с каждой стороны. Сколько всего?", 24, "Две стороны.", "12 × 2 = 24!", [12, 36]),
            ("Что лишнее: 2, 4, 6, 8, 9?", 9, "Все кроме одного чётные.", "9 — нечётное!", [4, 8]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("cat", 5, logic)


# ============================================================ 3 класс
def gen_g3():
    def mult9():
        a, b = R.randint(2, 9), R.randint(2, 9)
        return (f"{a} × {b} = ?", a * b, "Таблица умножения до 9.",
                f"{a} × {b} = {a * b}!", [a * b + a, a * b - b, a * (b + 1)])
    gen("count", 15, mult9)

    def div9():
        b, q = R.randint(2, 9), R.randint(2, 9)
        return (f"{b * q} ÷ {b} = ?", q, f"Какое число × {b} = {b * q}?",
                f"{b * q} ÷ {b} = {q}!", [q + 1, q - 1, q + 2])
    gen("count", 12, div9)

    def addsub1000():
        if R.random() < .5:
            a, b = R.randint(100, 600), R.randint(100, 399)
            return (f"{a} + {b} = ?", a + b, "Складывай по разрядам: сотни, десятки, единицы.",
                    f"{a} + {b} = {a + b}!", [a + b + 100, a + b - 10, a + b + 10])
        a, b = R.randint(300, 999), R.randint(100, 299)
        return (f"{a} − {b} = ?", a - b, "Вычитай по разрядам.", f"{a} − {b} = {a - b}!",
                [a - b + 100, a - b - 10, a - b + 10])
    gen("count", 10, addsub1000)

    def eq():
        t = R.randint(0, 2)
        if t == 0:
            a, x = R.randint(2, 9), R.randint(2, 9)
            return (f"x × {a} = {a * x}. Найди x.", x, f"Раздели {a * x} на {a}.",
                    f"x = {a * x} ÷ {a} = {x}!", [x + 1, x - 1, a * x])
        if t == 1:
            a, x = R.randint(2, 9), R.randint(2, 9)
            return (f"x ÷ {a} = {x}. Найди x.", a * x, f"Умножь {x} на {a}.",
                    f"x = {x} × {a} = {a * x}!", [x + a, x, a * x + 1])
        a, x = R.randint(2, 9), R.randint(2, 9)
        return (f"{a} × x = {a * x}. Найди x.", x, f"Раздели обе части на {a}.",
                f"x = {a * x} ÷ {a} = {x}!", [x + 1, x + 2, a * x - a])
    gen("eq", 10, eq)

    def order():
        t = R.randint(0, 2)
        if t == 0:
            a, b, c = R.randint(2, 20), R.randint(2, 9), R.randint(2, 9)
            return (f"{a} + {b} × {c} = ?", a + b * c, "Сначала умножение.",
                    f"{b} × {c} = {b * c}, + {a} = {a + b * c}!", [(a + b) * c, a + b * c + 1, a + b + c])
        if t == 1:
            a, b, c = R.randint(2, 9), R.randint(2, 9), R.randint(2, 9)
            return (f"({a} + {b}) × {c} = ?", (a + b) * c, "Скобки сначала.",
                    f"({a} + {b}) = {a + b}, × {c} = {(a + b) * c}!", [a + b * c, (a + b) * c + c, a + b + c])
        a, b, c = R.randint(2, 9), R.randint(2, 9), R.randint(1, 3)
        return (f"{a} × {b} − {c} = ?", a * b - c, "Умножение раньше вычитания.",
                f"{a} × {b} = {a * b}, − {c} = {a * b - c}!", [a * (b - c), a * b - c + 1, a * b + c])
    gen("count", 10, order)

    def word():
        t = R.randint(0, 2)
        if t == 0:
            v, t_ = R.randint(2, 9), R.randint(3, 9)
            return (f"Саян бежит {v} м/с. Сколько метров за {t_} с?", v * t_,
                    "Путь = скорость × время.", f"{v} × {t_} = {v * t_} м!", [v + t_, v * t_ + v, v * t_ - t_])
        if t == 1:
            p, n = R.randint(3, 9), R.randint(3, 9)
            return (f"Вкусняшка стоит {p} лапок. Сколько за {n} штук?", p * n,
                    "Цена × количество.", f"{p} × {n} = {p * n}!", [p + n, p * n + p, p * n - n])
        n, k = R.randint(2, 9), R.randint(3, 9)
        return (f"{n * k} рыбок поровну на {n} котов. Сколько каждому?", k,
                "Деление поровну.", f"{n * k} ÷ {n} = {k}!", [k + 1, k - 1, n * k - n])
    gen("word", 15, word)

    def area():
        if R.random() < .5:
            a, b = R.randint(3, 12), R.randint(3, 12)
            return (f"Площадь прямоугольника {a} × {b}?", a * b, "Длина × ширина.",
                    f"{a} × {b} = {a * b}!", [2 * (a + b), a + b, a * b + a])
        a = R.randint(3, 12)
        return (f"Площадь квадрата со стороной {a}?", a * a, "Сторона × сторона.",
                f"{a} × {a} = {a * a}!", [4 * a, 2 * a, a * a + a])
    gen("geom", 10, area)

    def frac():
        d = pick([2, 3, 4, 5])
        k = R.randint(2, 9)
        n = d * k
        return (f"Найди 1/{d} от {n}.", k, f"Раздели {n} на {d}.",
                f"{n} ÷ {d} = {k}!", [k + 1, k - 1, n - k])
    gen("frac", 8, frac)

    def units():
        t = R.randint(0, 2)
        if t == 0:
            m, cm = R.randint(1, 5), R.randint(10, 90)
            return (f"{m} м {cm} см = … см", m * 100 + cm, "Метры переведи в см и прибавь.",
                    f"{m} м = {m * 100} см, + {cm} = {m * 100 + cm} см!", [m * 100 + cm + 10, m * 10 + cm, m * 100])
        if t == 1:
            h, m = R.randint(1, 4), R.randint(10, 50)
            return (f"{h} ч {m} мин = … мин", h * 60 + m, "Часы × 60 плюс минуты.",
                    f"{h} × 60 + {m} = {h * 60 + m} мин!", [h * 60 + m + 10, h * 100 + m, h * 60])
        km = R.randint(1, 9)
        return (f"{km} км = … м", km * 1000, "В километре 1000 метров.",
                f"{km} × 1000 = {km * 1000} м!", [km * 100, km * 10000, km * 500])
    gen("count", 5, units)

    def logic():
        items = [
            ("Что лишнее: 4, 8, 12, 15, 16?", 15, "Все кроме одного делятся на 4.", "15 не делится на 4!", [8, 12]),
            ("Саян старше Мурки, Мурка старше Барсика. Кто младше?", "Барсик", "Цепочка возраста.", "Барсик младше!", ["Саян", "Мурка"]),
            ("Продолжи ряд: 2, 4, 8, 16, …?", 32, "Каждое число вдвое больше.", "16 × 2 = 32!", [24, 30]),
            ("Сколько лап у 6 котов?", 24, "У кота 4 лапы.", "6 × 4 = 24!", [12, 20]),
            ("Что лишнее: 5, 10, 15, 20, 23?", 23, "Все кроме одного делятся на 5.", "23 не делится на 5!", [10, 15]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("cat", 5, logic)


# ============================================================ 4 класс
def gen_g4():
    def multidig():
        a, b = R.randint(11, 99), R.randint(2, 9)
        return (f"{a} × {b} = ?", a * b, "Умножай по разрядам: десятки и единицы.",
                f"{a} × {b} = {a * b}!", [a * b + a, a * b - b, a * (b + 1)])
    gen("count", 10, multidig)

    def muldivbig():
        b, q = R.randint(2, 9), R.randint(11, 99)
        return (f"{b * q} ÷ {b} = ?", q, f"Подбери число × {b} = {b * q}.",
                f"{b * q} ÷ {b} = {q}!", [q + 1, q - 1, q + 10])
    gen("count", 12, muldivbig)

    def motion():
        t = R.randint(0, 2)
        if t == 0:
            v, tt = R.randint(3, 12), R.randint(3, 9)
            return (f"Саян бежит {v} м/с за {tt} с. Какой путь?", v * tt, "s = v × t.",
                    f"{v} × {tt} = {v * tt} м!", [v + tt, v * tt + v, v * tt - tt])
        if t == 1:
            v, tt = R.randint(3, 12), R.randint(3, 9)
            return (f"Саян пробежал {v * tt} м за {tt} с. Какая скорость?", v, "v = s ÷ t.",
                    f"{v * tt} ÷ {tt} = {v} м/с!", [v + 1, v * tt, v - 1])
        v, tt = R.randint(3, 12), R.randint(3, 9)
        return (f"Саян пробежал {v * tt} м со скоростью {v} м/с. Сколько секунд?", tt, "t = s ÷ v.",
                f"{v * tt} ÷ {v} = {tt} с!", [tt + 1, v * tt, tt - 1])
    gen("word", 15, motion)

    def frac():
        t = R.randint(0, 2)
        if t == 0:
            den = pick([3, 4, 5, 6, 8])
            num = R.randint(1, den - 1)
            k = R.randint(3, 12)
            total = den * k
            return (f"Найди {num}/{den} от {total}.", num * k, f"{total} ÷ {den} × {num}.",
                    f"{total} ÷ {den} = {k}, × {num} = {num * k}!", [k, num * k + num, total - num * k])
        if t == 1:
            den = pick([5, 7, 8, 9, 10])
            a, b = R.randint(1, den - 2), R.randint(1, den - 2)
            if a + b >= den:
                return None
            return (f"{a}/{den} + {b}/{den} = ?", f"{a + b}/{den}", "Знаменатель общий — складывай числители.",
                    f"{a} + {b} = {a + b}, знаменатель {den}: {a + b}/{den}!",
                    [f"{a + b + 1}/{den}", f"{a * b}/{den}", f"{a + b}/{den * 2}"])
        den = pick([4, 5, 6, 8, 10])
        a, b = R.sample(range(1, den), 2)
        big = max(a, b)
        return (f"Что больше: {a}/{den} или {b}/{den}?", f"{big}/{den}",
                "При одинаковом знаменателе больше та дробь, где числитель больше.",
                f"{big}/{den} больше!", [f"{min(a, b)}/{den}", "Равны"])
    gen("frac", 12, frac)

    def order():
        a, b, c = R.randint(2, 20), R.randint(2, 9), R.randint(2, 9)
        t = R.randint(0, 1)
        if t == 0:
            return (f"{a} + {b} × {c} = ?", a + b * c, "Сначала умножение.",
                    f"{b} × {c} = {b * c}, + {a} = {a + b * c}!", [(a + b) * c, a + b * c + 1, a + b + c])
        return (f"({a} + {b}) × {c} = ?", (a + b) * c, "Скобки сначала.",
                f"({a} + {b}) × {c} = {(a + b) * c}!", [a + b * c, (a + b) * c + c, a + b + c])
    gen("count", 10, order)

    def word():
        t = R.randint(0, 1)
        if t == 0:
            p, k = R.randint(3, 12), R.randint(2, 6)
            n = p * k + R.randint(5, 40)
            return (f"У Саяна {n} лапок. Он купил {k} вкусняшек по {p}. Сколько осталось?", n - p * k,
                    "Сначала стоимость, потом вычти.", f"{k} × {p} = {p * k}, осталось {n} − {p * k} = {n - p * k}!",
                    [n - p, p * k, n - p * k + 1])
        k = R.randint(3, 8)
        n = k * R.randint(2, 9) + R.randint(1, k - 1)
        ans = math.ceil(n / k)
        return (f"{n} рыбок по {k} в коробку. Сколько коробок нужно?", ans,
                "Дели и округляй вверх — остаток тоже требует коробку.",
                f"{n} ÷ {k} = {n // k} полных + остаток → {ans} коробок!", [n // k, ans + 1, n // k - 1])
    gen("word", 12, word)

    def area():
        t = R.randint(0, 1)
        if t == 0:
            a, b = R.randint(4, 20), R.randint(4, 20)
            return (f"Площадь прямоугольника {a} × {b}?", a * b, "Длина × ширина.",
                    f"{a} × {b} = {a * b}!", [2 * (a + b), a + b, a * b + a])
        a = R.randint(4, 20)
        return (f"Площадь квадрата со стороной {a}?", a * a, "Сторона в квадрате.",
                f"{a} × {a} = {a * a}!", [4 * a, 2 * a, a * a + a])
    gen("geom", 10, area)

    def units():
        t = R.randint(0, 2)
        if t == 0:
            t_ = R.randint(1, 9)
            return (f"{t_} т = … кг", t_ * 1000, "В тонне 1000 кг.", f"{t_} × 1000 = {t_ * 1000} кг!",
                    [t_ * 100, t_ * 10000, t_ * 500])
        if t == 1:
            km, m = R.randint(1, 9), R.randint(100, 900)
            return (f"{km} км {m} м = … м", km * 1000 + m, "Км × 1000 плюс метры.",
                    f"{km * 1000} + {m} = {km * 1000 + m} м!", [km * 1000 + m + 100, km * 100 + m, km * 1000])
        h, m = R.randint(1, 5), R.randint(10, 50)
        return (f"{h} ч {m} мин = … мин", h * 60 + m, "Часы × 60 плюс минуты.",
                f"{h * 60} + {m} = {h * 60 + m} мин!", [h * 60 + m + 10, h * 100 + m, h * 60])
    gen("count", 10, units)

    def eq():
        a, x, b = R.randint(2, 9), R.randint(2, 12), R.randint(1, 20)
        return (f"{a}x + {b} = {a * x + b}. Найди x.", x, f"Вычти {b}, потом раздели на {a}.",
                f"{a}x = {a * x}, x = {x}!", [x + 1, (a * x + b) // a, x - 1])
    gen("eq", 5, eq)

    def logic():
        items = [
            ("Продолжи ряд: 1, 4, 9, 16, …?", 25, "Это квадраты: 1², 2², 3², 4²…", "5² = 25!", [20, 24]),
            ("Продолжи ряд: 1, 1, 2, 3, 5, 8, …?", 13, "Каждое число — сумма двух предыдущих.", "5 + 8 = 13!", [11, 12]),
            ("Что тяжелее: кг железа или кг пуха?", "Одинаково", "Килограмм есть килограмм.", "Одинаково!", ["Железо", "Пух"]),
            ("Продолжи ряд: 2, 6, 18, 54, …?", 162, "Каждое число втрое больше.", "54 × 3 = 162!", [108, 160]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("cat", 4, logic)


# ============================================================ 5 класс (Виленкин)
def gen_g5():
    def nat():
        a, b, c = R.randint(20, 200), R.randint(2, 9), R.randint(2, 9)
        t = R.randint(0, 1)
        if t == 0:
            return (f"{a} + {b} × {c} = ?", a + b * c, "Сначала умножение.",
                    f"{b} × {c} = {b * c}, + {a} = {a + b * c}!", [(a + b) * c, a + b * c + 1, a + b + c])
        return (f"({a} + {b}) × {c} = ?", (a + b) * c, "Скобки сначала.",
                f"({a} + {b}) × {c} = {(a + b) * c}!", [a + b * c, (a + b) * c + c, a + b + c])
    gen("count", 12, nat)

    def eq():
        t = R.randint(0, 2)
        if t == 0:
            a, x = R.randint(2, 12), R.randint(2, 12)
            return (f"{a}x = {a * x}. Найди x.", x, f"Раздели на {a}.", f"x = {x}!", [x + 1, a * x, x - 1])
        if t == 1:
            a, x, b = R.randint(2, 9), R.randint(2, 12), R.randint(1, 20)
            return (f"{a}x + {b} = {a * x + b}. Найди x.", x, f"Вычти {b}, раздели на {a}.",
                    f"x = {x}!", [x + 1, (a * x + b) // a, x - 1])
        a, x = R.randint(2, 9), R.randint(2, 9)
        return (f"x ÷ {a} = {x}. Найди x.", a * x, f"Умножь на {a}.", f"x = {a * x}!", [x + a, x, a * x + 1])
    gen("eq", 12, eq)

    def geomvol():
        t = R.randint(0, 2)
        if t == 0:
            a = R.randint(2, 9)
            return (f"Объём куба с ребром {a}?", a ** 3, "V = a³.", f"{a}³ = {a ** 3}!",
                    [a * a, 6 * a * a, a ** 3 + a])
        if t == 1:
            a = R.randint(2, 9)
            return (f"Площадь поверхности куба с ребром {a}?", 6 * a * a, "6 граней по a².",
                    f"6 × {a * a} = {6 * a * a}!", [a ** 3, 4 * a * a, 6 * a])
        a, b, c = R.randint(2, 9), R.randint(2, 9), R.randint(2, 9)
        return (f"Объём прямоугольного параллелепипеда {a}×{b}×{c}?", a * b * c, "V = a×b×c.",
                f"{a} × {b} × {c} = {a * b * c}!", [2 * (a * b + b * c + a * c), a + b + c, a * b + c])
    gen("geom", 12, geomvol)

    def frac():
        t = R.randint(0, 2)
        if t == 0:
            den = pick([5, 7, 8, 9, 10, 12])
            a, b = R.randint(1, den - 2), R.randint(1, den - 2)
            if a + b >= den:
                return None
            return (f"{a}/{den} + {b}/{den} = ?", f"{a + b}/{den}", "Складывай числители.",
                    f"{a + b}/{den}!", [f"{a + b + 1}/{den}", f"{a * b}/{den}", f"{a + b}/{den * 2}"])
        if t == 1:
            den = pick([5, 7, 8, 9, 10, 12])
            a = R.randint(2, den - 1)
            b = R.randint(1, a - 1)
            return (f"{a}/{den} − {b}/{den} = ?", f"{a - b}/{den}", "Вычитай числители.",
                    f"{a - b}/{den}!", [f"{a - b + 1}/{den}", f"{a + b}/{den}", f"{a - b}/{den * 2}"])
        den = pick([4, 5, 6, 8, 10])
        a, b = R.sample(range(1, den), 2)
        return (f"Что больше: {a}/{den} или {b}/{den}?", f"{max(a, b)}/{den}",
                "Общий знаменатель — сравни числители.", f"{max(a, b)}/{den} больше!",
                [f"{min(a, b)}/{den}", "Равны"])
    gen("frac", 15, frac)

    def dec():
        t = R.randint(0, 2)
        if t == 0:
            a, b = R.randint(11, 99) / 10, R.randint(11, 99) / 10
            s = round(a + b, 1)
            return (f"{N(a)} + {N(b)} = ?", s, "Запятую под запятой.", f"{N(s)}!",
                    [round(s + .1, 1), round(s - .1, 1), round(s + 1, 1)])
        if t == 1:
            a, b = R.randint(11, 99) / 10, R.randint(11, 99) / 10
            a, b = max(a, b), min(a, b)
            s = round(a - b, 1)
            return (f"{N(a)} − {N(b)} = ?", s, "Вычитай как обычные числа.", f"{N(s)}!",
                    [round(s + .1, 1), round(s - .1, 1), round(s + 1, 1)])
        x = R.randint(11, 99) / 10
        return (f"{N(x)} × 10 = ?", round(x * 10, 1), "Запятая вправо на один знак.",
                f"{N(round(x * 10, 1))}!", [round(x / 10, 2), round(x * 100, 1), round(x * 10 + 1, 1)])
    gen("frac", 15, dec)

    def word():
        t = R.randint(0, 1)
        if t == 0:
            p, n = R.randint(3, 15), R.randint(3, 9)
            return (f"Вкусняшка стоит {p} лапок. Сколько за {n} штук?", p * n, "Цена × количество.",
                    f"{p * n}!", [p + n, p * n + p, p * n - n])
        v, tt = R.randint(3, 12), R.randint(3, 9)
        return (f"Саян бежит {v} м/с за {tt} с. Какой путь?", v * tt, "s = v × t.",
                f"{v * tt} м!", [v + tt, v * tt + v, v * tt - tt])
    gen("word", 12, word)

    def pct():
        p = pick([10, 25, 50])
        total = R.randint(2, 20) * 20
        ans = total * p // 100
        return (f"{p}% от {total} — сколько лапок?", ans, f"1% = {total // 100}, умножь на {p}.",
                f"{ans} лапок!", [ans * 2, total // 100, ans + total // 10])
    gen("pct", 8, pct)

    def divis():
        n = R.randint(100, 999)
        d = pick([2, 3, 5, 9, 10])
        ans = "Да" if n % d == 0 else "Нет"
        return (f"Делится ли {n} на {d}?", ans, f"Признак делимости на {d}.",
                f"{n} {'делится' if n % d == 0 else 'не делится'} на {d}!",
                ["Нет" if ans == "Да" else "Да", "Не хватает данных"])
    gen("count", 8, divis)

    def logic():
        items = [
            ("Продолжи ряд: 2, 6, 12, 20, …?", 30, "n×(n+1): 1×2, 2×3, 3×4…", "5×6 = 30!", [28, 32]),
            ("Продолжи ряд: 100, 95, 85, 70, …?", 50, "Шаги −5, −10, −15…", "70 − 20 = 50!", [55, 60]),
            ("Сколько жизней у кота по русской легенде?", 9, "Русская легенда.", "9 жизней!", [7, 3]),
            ("Продолжи ряд: 1, 8, 27, 64, …?", 125, "Это кубы: 1³, 2³, 3³, 4³…", "5³ = 125!", [100, 120]),
            ("Что лишнее: 2, 3, 5, 7, 9?", 9, "Все кроме одного — простые числа.", "9 = 3×3, не простое!", [3, 7]),
            ("Саян съел половину рыбок, потом половину остатка. Осталась 1. Сколько было?", 4, "Иди с конца: 1 → 2 → 4.", "Было 4 рыбки!", [2, 8]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("cat", 6, logic)


# ============================================================ 6 класс (Мерзляк)
def gen_g6():
    def fracops():
        t = R.randint(0, 2)
        if t == 0:
            d1, d2 = pick([(2, 3), (3, 4), (4, 6), (5, 10), (6, 8), (2, 5)])
            a, b = R.randint(1, d1 - 1), R.randint(1, d2 - 1)
            l = d1 * d2 // math.gcd(d1, d2)
            na, nb = a * (l // d1), b * (l // d2)
            return (f"{a}/{d1} + {b}/{d2} = ?", fs(na + nb, l), "Приведи к общему знаменателю.",
                    f"{na}/{l} + {nb}/{l} = {fs(na + nb, l)}!",
                    [fs(na + nb + 1, l), fs(a + b, d1 + d2), fs(na + nb, l * 2)])
        if t == 1:
            a, b = R.randint(1, 5), R.randint(2, 6)
            c, d = R.randint(1, 5), R.randint(2, 6)
            return (f"{a}/{b} × {c}/{d} = ?", fs(a * c, b * d), "Числитель × числитель, знаменатель × знаменатель.",
                    f"{fs(a * c, b * d)}!", [fs(a * c + 1, b * d), fs(a + c, b + d), fs(a * c, b * d + 1)])
        a, b = R.randint(1, 5), R.randint(2, 6)
        c, d = R.randint(1, 5), R.randint(2, 6)
        return (f"{a}/{b} ÷ {c}/{d} = ?", fs(a * d, b * c), "Деление = умножение на перевёрнутую дробь.",
                f"{a}/{b} × {d}/{c} = {fs(a * d, b * c)}!", [fs(a * c, b * d), fs(a * d + 1, b * c), fs(a * d, b * c + 1)])
    gen("frac", 18, fracops)

    def decops():
        t = R.randint(0, 1)
        if t == 0:
            a, b = R.randint(11, 49) / 10, R.randint(2, 9)
            p = round(a * b, 1)
            return (f"{N(a)} × {b} = ?", p, "Умножь без запятой, верни один знак.", f"{N(p)}!",
                    [round(p + .1, 1), round(p * 10, 1), round(p - .1, 1)])
        x = R.randint(2, 20)
        return (f"{x} ÷ 0,5 = ?", x * 2, "Деление на 0,5 = умножение на 2.", f"{x * 2}!",
                [x / 2, x, x * 2 + 1])
    gen("frac", 12, decops)

    def pct():
        t = R.randint(0, 2)
        if t == 0:
            p = pick([5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 90])
            total = R.randint(2, 20) * 20
            ans = total * p // 100
            return (f"{p}% от {total}?", ans, f"1% = {total // 100}, × {p}.", f"{ans}!",
                    [ans * 2, total // 100, ans + total // 10])
        if t == 1:
            price = R.randint(2, 20) * 100
            p = pick([10, 20, 25, 50])
            ans = price * (100 - p) // 100
            return (f"Миска стоит {price} лапок, скидка {p}%. Новая цена?", ans, f"Возьми {100 - p}% от цены.",
                    f"{ans}!", [price * p // 100, price - p, ans + 100])
        whole = pick([20, 40, 50, 80, 100, 200])
        p = pick([5, 10, 20, 25, 40, 50, 75])
        part = whole * p // 100
        return (f"{part} из {whole} — сколько процентов?", f"{p}%", f"{part} ÷ {whole} × 100.",
                f"{p}%!", [f"{p * 2}%", f"{100 - p}%", f"{part}%"])
    gen("pct", 15, pct)

    def ratio():
        t = R.randint(0, 1)
        if t == 0:
            g = R.randint(2, 6)
            a, b = R.randint(1, 6) * g, R.randint(1, 6) * g
            return (f"Сократи отношение {a}:{b}.", f"{a // g}:{b // g}", f"Раздели оба на НОД = {g}.",
                    f"{a // g}:{b // g}!", [f"{a}:{b // g}", f"{a // g}:{b}", f"{a // g + 1}:{b // g}"])
        a, b = R.randint(1, 4), R.randint(1, 4)
        k = R.randint(2, 9)
        total = (a + b) * k
        return (f"Раздели {total} в отношении {a}:{b}. Большая часть?", max(a, b) * k,
                f"Всего {a + b} частей, одна = {k}.", f"{max(a, b)} × {k} = {max(a, b) * k}!",
                [min(a, b) * k, total // 2, max(a, b) * k + k])
    gen("alg", 10, ratio)

    def neg():
        a, b = R.randint(2, 12), R.randint(2, 12)
        t = R.randint(0, 2)
        if t == 0:
            return (f"(−{a}) + (−{b}) = ?", -(a + b), "Два минуса складываются.", f"−{a + b}!",
                    [a + b, -(a + b) + 1, -(a - b)])
        if t == 1:
            return (f"(−{a}) × (−{b}) = ?", a * b, "Минус на минус = плюс.", f"{a * b}!",
                    [-a * b, a * b + 1, -(a + b)])
        return (f"{a} − (−{b}) = ?", a + b, "Вычесть минус = прибавить.", f"{a + b}!",
                [a - b, a + b + 1, a - b - 1])
    gen("count", 12, neg)

    def gcdlcm():
        a, b = R.randint(4, 24), R.randint(4, 24)
        if R.random() < .5:
            g = math.gcd(a, b)
            return (f"НОД({a}, {b}) = ?", g, "Наибольший общий делитель.", f"{g}!",
                    [g * 2, a * b, g + 1])
        l = a * b // math.gcd(a, b)
        return (f"НОК({a}, {b}) = ?", l, "Наименьшее общее кратное.", f"{l}!",
                [a * b, math.gcd(a, b), l + a])
    gen("count", 8, gcdlcm)

    def eq():
        a, x, b = R.randint(2, 9), R.randint(2, 12), R.randint(1, 20)
        return (f"{a}x + {b} = {a * x + b}. Найди x.", x, f"Вычти {b}, раздели на {a}.", f"x = {x}!",
                [x + 1, (a * x + b) // a, x - 1])
    gen("eq", 8, eq)

    def geom():
        r = R.randint(1, 10)
        if R.random() < .5:
            ans = round(2 * 3.14 * r, 2)
            return (f"Длина окружности при r = {r} (π ≈ 3,14)?", ans, "C = 2πr.", f"{N(ans)}!",
                    [round(3.14 * r, 2), round(2 * 3.14 * r + 3.14, 2), round(3.14 * r * r, 2)])
        ans = round(3.14 * r * r, 2)
        return (f"Площадь круга при r = {r} (π ≈ 3,14)?", ans, "S = πr².", f"{N(ans)}!",
                [round(2 * 3.14 * r, 2), round(3.14 * r, 2), round(ans / 2, 2)])
    gen("geom", 8, geom)

    def word():
        a, b = pick([(6, 3), (12, 4), (15, 10), (4, 4), (8, 8), (6, 6), (12, 12), (3, 6)])
        ans = a * b // (a + b)
        return (f"Саян съедает мешок за {a} дней, Мурка за {b}. Вместе за сколько?", ans,
                "Сложи скорости 1/a + 1/b, переверни.", f"{ans} дня!", [a + b, (a + b) // 2, ans + 1])
    gen("word", 5, word)

    def stat():
        m = R.randint(5, 20)
        d1, d2 = R.randint(1, 6), R.randint(1, 6)
        nums = [m - d1, m, m + d2, m + d1 - d2]
        R.shuffle(nums)
        return (f"Среднее арифметическое {', '.join(map(str, nums))}?", m, "Сумма ÷ 4.",
                f"{sum(nums)} ÷ 4 = {m}!", [m + 1, sum(nums), sorted(nums)[1]])
    gen("stat", 4, stat)


# ============================================== 7 класс (Макарычев + Атанасян)
def gen_g7():
    def pow():
        b = R.randint(2, 5)
        m, n = R.randint(2, 5), R.randint(2, 5)
        t = R.randint(0, 2)
        if t == 0:
            return (f"{b}{sup(m)} × {b}{sup(n)} = {b} в степени …?", m + n, "Показатели складываются.",
                    f"{m + n}!", [m * n, m + n + 1, abs(m - n)])
        if t == 1:
            m, n = max(m, n) + 1, min(m, n)
            return (f"{b}{sup(m)} ÷ {b}{sup(n)} = {b} в степени …?", m - n, "Показатели вычитаются.",
                    f"{m - n}!", [m + n, m - n + 1, m * n])
        m, n = R.randint(2, 3), R.randint(2, 3)
        return (f"({b}{sup(m)}){sup(n)} = {b} в степени …?", m * n, "Показатели перемножаются.",
                f"{m * n}!", [m + n, m * n + 1, m ** n])
    gen("pow", 12, pow)

    def poly():
        a, b = R.randint(1, 9), R.randint(1, 9)
        if R.random() < .5:
            return (f"Раскрой (x + {a})(x + {b}): коэффициент при x?", a + b, "x·b + a·x = (a+b)x.",
                    f"{a + b}!", [a * b, a + b + 1, a - b])
        return (f"Раскрой (x + {a})(x + {b}): свободный член?", a * b, "a·b.", f"{a * b}!",
                [a + b, a * b + 1, a * b + a])
    gen("alg", 12, poly)

    def fsu():
        a, b = R.randint(2, 9), R.randint(1, 5)
        t = R.randint(0, 2)
        if t == 0:
            return (f"(a + b)² при a={a}, b={b}?", (a + b) ** 2, "(a+b)² = a²+2ab+b².",
                    f"{(a + b) ** 2}!", [a * a + b * b, (a + b) * 2, (a + b) ** 2 + 1])
        if t == 1:
            return (f"(a − b)² при a={a + b}, b={b}?", a * a, "(a−b)² = a²−2ab+b².",
                    f"{a * a}!", [(a + b) * (a + b) + b * b, a * a + 1, (a - b) * 2])
        return (f"a² − b² при a={a + b}, b={b}?", (a + b) * (a + b) - b * b, "a²−b² = (a−b)(a+b).",
                f"{(a + b) ** 2 - b * b}!", [(a + b - b) * (a + b + b) + 1, (a + b) * (a + b), a * a + b * b])
    gen("alg", 10, fsu)

    def lineq():
        a, c = R.randint(2, 9), R.randint(1, 5)
        x = R.randint(2, 12)
        b = R.randint(1, 20)
        d = a * x + b - c * x
        return (f"{a}x + {b} = {c}x + {d}. Найди x.", x, "Перенеси x влево, числа вправо.",
                f"{a - c}x = {d - b}, x = {x}!", [x + 1, x - 1, (d - b)])
    gen("eq", 14, lineq)

    def system():
        x, y = R.randint(2, 12), R.randint(1, 9)
        s, d = x + y, x - y
        return (f"x + y = {s}, x − y = {d}. Найди x.", x, "Сложи уравнения: 2x = s + d.",
                f"2x = {s + d}, x = {x}!", [y, s, x + 1])
    gen("eq", 8, system)

    def func():
        k, b, x = R.randint(2, 6), R.randint(1, 9), R.randint(2, 9)
        return (f"y = {k}x + {b}. Найди y при x = {x}.", k * x + b, "Подставь x.",
                f"{k} × {x} + {b} = {k * x + b}!", [k * x, k * x + b + 1, k + x + b])
    gen("alg", 10, func)

    def pctprop():
        a, b = R.randint(2, 9), R.randint(2, 9)
        k = R.randint(2, 6)
        return (f"Пропорция {a}/{b} = {a * k}/x. Найди x.", b * k, "Перекрёстное умножение.",
                f"x = {b * k}!", [b * k + 1, a * k, b + k])
    gen("pct", 8, pctprop)

    def geom():
        t = R.randint(0, 3)
        if t == 0:
            a, b = R.randint(20, 80), R.randint(20, 80)
            if a + b >= 170:
                return None
            return (f"Два угла треугольника {a}° и {b}°. Третий?", 180 - a - b, "Сумма 180°.",
                    f"{180 - a - b}°!", [190 - a - b, 90, 360 - a - b])
        if t == 1:
            apex = R.randint(10, 40) * 2
            base = (180 - apex) // 2
            return (f"Равнобедренный треугольник, угол при вершине {apex}°. Угол при основании?", base,
                    "(180 − вершина) ÷ 2.", f"{base}°!", [apex, 180 - apex, base + 1])
        if t == 2:
            n = pick([5, 6, 8])
            return (f"Сумма углов {n}-угольника?", (n - 2) * 180, "(n−2)×180°.",
                    f"{(n - 2) * 180}°!", [(n - 1) * 180, n * 180, (n - 2) * 180 + 180])
        a = R.randint(20, 160)
        return (f"Один из смежных углов {a}°. Второй?", 180 - a, "Смежные = 180°.",
                f"{180 - a}°!", [90 - a if a < 90 else a - 90, 180 - a + 10, a])
    gen("geom", 16, geom)

    def word():
        v1, v2, t = R.randint(3, 8), R.randint(3, 8), R.randint(2, 6)
        return (f"Саян и Мурка бегут навстречу: {v1} и {v2} м/с, встретились через {t} с. Расстояние?", (v1 + v2) * t,
                "Сложи скорости, умножь на время.", f"{(v1 + v2) * t} м!", [v1 * v2 * t, (v1 + v2) + t, (v1 + v2) * t + v1])
    gen("word", 6, word)

    def stat():
        m = R.randint(6, 20)
        nums = [m - R.randint(2, 5), m - R.randint(1, 2), m, m + R.randint(1, 3), m + R.randint(3, 6)]
        R.shuffle(nums)
        return (f"Медиана набора {', '.join(map(str, nums))}?", m, "Упорядочь, возьми среднее (3-е из 5).",
                f"{m}!", [sorted(nums)[1], sorted(nums)[3], round(sum(nums) / 5, 1)])
    gen("stat", 4, stat)


# ============================================================ 8 класс
def gen_g8():
    def roots():
        t = R.randint(0, 2)
        if t == 0:
            a = R.randint(3, 15)
            return (f"√{a * a} = ?", a, f"Какое число в квадрате = {a * a}?", f"{a}!",
                    [a * a // 2, a + 1, a * a - a])
        if t == 1:
            a, b = R.randint(2, 9), R.randint(2, 9)
            return (f"√{a * a} × √{b * b} = ?", a * b, "√a² × √b² = a×b.", f"{a * b}!",
                    [a + b, a * b + 1, a * b * 2])
        a, b = R.randint(2, 6), R.randint(2, 9)
        return (f"√{a * a * b} = a√…? (вынеси множитель)", b, "√(a²·b) = a√b.", f"{b}!",
                [b * a, b + 1, b * b])
    gen("pow", 14, roots)

    def quad():
        t = R.randint(0, 2)
        if t == 0:
            r = R.randint(2, 12)
            return (f"x² = {r * r}, x > 0. Найди x.", r, f"Корень из {r * r}.", f"{r}!",
                    [r * r // 2, r + 1, r * r // 4])
        if t == 1:
            r1, r2 = R.randint(1, 9), R.randint(1, 9)
            b, c = -(r1 + r2), r1 * r2
            return (f"x² {'+' if b >= 0 else '−'} {abs(b)}x + {c} = 0. Сумма корней?", r1 + r2,
                    "По Виету сумма = −b.", f"{r1 + r2}!", [r1 * r2, r1 + r2 + 1, -(r1 + r2)])
        r1, r2 = R.randint(1, 9), R.randint(1, 9)
        b, c = -(r1 + r2), r1 * r2
        return (f"x² {'+' if b >= 0 else '−'} {abs(b)}x + {c} = 0. Произведение корней?", r1 * r2,
                "По Виету произведение = c.", f"{r1 * r2}!", [r1 + r2, r1 * r2 + 1, -(r1 * r2)])
    gen("eq", 16, quad)

    def algfrac():
        a, x = R.randint(1, 9), R.randint(2, 12)
        return (f"(x² − {a * a})/(x − {a}) при x = {x}?", x + a, "Сократи: (x−a)(x+a)/(x−a) = x+a.",
                f"{x} + {a} = {x + a}!", [x - a, x * a, x + a + 1])
    gen("alg", 10, algfrac)

    def ineq():
        a, t = R.randint(2, 6), R.randint(2, 12)
        c = a * t + R.randint(1, a - 1)
        return (f"Наименьшее целое x, при котором {a}x > {c}?", t + 1, f"{c} ÷ {a}, следующее целое.",
                f"{t + 1}!", [t, t + 2, c // a])
    gen("eq", 8, ineq)

    def pythag():
        a, b, c = pick([(3, 4, 5), (6, 8, 10), (5, 12, 13), (8, 15, 17),
                        (9, 12, 15), (7, 24, 25), (12, 16, 20), (10, 24, 26),
                        (9, 40, 41), (20, 21, 29), (12, 35, 37)])
        return (f"Катеты {a} и {b}. Гипотенуза?", c, f"{a}²+{b}²={a * a + b * b}, корень.", f"{c}!",
                [a + b, c + 1, c - 2])
    gen("geom", 10, pythag)

    def areas():
        t = R.randint(0, 2)
        if t == 0:
            b, h = R.randint(3, 12), R.randint(2, 8) * 2
            return (f"Площадь треугольника: основание {b}, высота {h}?", b * h // 2, "½·основание·высота.",
                    f"{b * h // 2}!", [b * h, b + h, b * h // 2 + 1])
        if t == 1:
            a, h = R.randint(3, 12), R.randint(2, 9)
            return (f"Площадь параллелограмма: сторона {a}, высота {h}?", a * h, "основание·высота.",
                    f"{a * h}!", [2 * (a + h), a * h // 2, a * h + a])
        a, b, h = R.randint(3, 9), R.randint(3, 9), R.randint(2, 8)
        return (f"Площадь трапеции: основания {a} и {b}, высота {h}?", (a + b) * h // 2, "½·(a+b)·h.",
                f"{(a + b) * h // 2}!", [(a + b) * h, (a + b) + h, (a + b) * h // 2 + 1])
    gen("geom", 12, areas)

    def circle():
        r = R.randint(1, 10)
        if R.random() < .5:
            ans = round(2 * 3.14 * r, 2)
            return (f"Длина окружности r = {r} (π ≈ 3,14)?", ans, "C = 2πr.", f"{N(ans)}!",
                    [round(3.14 * r, 2), round(2 * 3.14 * r + 3.14, 2), round(3.14 * r * r, 2)])
        ans = round(3.14 * r * r, 2)
        return (f"Площадь круга r = {r} (π ≈ 3,14)?", ans, "S = πr².", f"{N(ans)}!",
                [round(2 * 3.14 * r, 2), round(3.14 * r, 2), round(ans / 2, 2)])
    gen("geom", 8, circle)

    def func():
        k, x = R.randint(2, 9), R.randint(2, 9)
        return (f"y = {k}/x. Найди y при x = {x}.", round(k / x, 3), "Подставь x.", f"{N(round(k / x, 3))}!",
                [round(k * x, 3), round(k / x + 1, 3), round(x / k, 3)])
    gen("alg", 8, func)

    def similar():
        k = R.randint(2, 4)
        a = R.randint(2, 9)
        return (f"Треугольники подобны с k = {k}. Сторона меньшего {a}. Соответствующая сторона большего?", a * k,
                "Стороны умножаются на k.", f"{a * k}!", [a + k, a * k * k, a * k + 1])
    gen("geom", 6, similar)

    def word():
        v, t = R.randint(3, 12), R.randint(3, 9)
        return (f"Саян бежит {v} м/с за {t} с. Путь?", v * t, "s = v×t.", f"{v * t} м!",
                [v + t, v * t + v, v * t - t])
    gen("word", 8, word)


# ============================================================ 9 класс (ОГЭ)
def gen_g9():
    def ogecomp():
        t = R.randint(0, 2)
        if t == 0:
            a = R.randint(0, 5)
            d = pick([4, 5, 10])
            k = R.randint(1, d - 1)
            ans = round(a + k / d, 3)
            return (f"Точка на {k} деления правее {a}; отрезок {a}–{a + 1} на {d} частей. Число?", ans,
                    f"Цена деления 1/{d}.", f"{N(ans)}!", [round(a + (k + 1) / d, 3), round(a + k / (d * 2), 3), round(a + k / d + 1, 3)])
        if t == 1:
            n, m = R.randint(2, 15), R.randint(1, 9)
            return (f"{n} ÷ 0,5 − {m} = ?", 2 * n - m, "÷0,5 = ×2.", f"{2 * n - m}!",
                    [n * 2 + m, n - m, 2 * n - m + 1])
        a, b, v = R.randint(2, 9), R.randint(1, 15), R.randint(2, 9)
        return (f"Значение {a}x − {b} при x = {v}?", a * v - b, "Подставь x.", f"{a * v - b}!",
                [a * v + b, a * v - b + 1, a * (v - b)])
    gen("oge", 12, ogecomp)

    def prog():
        t = R.randint(0, 1)
        if t == 0:
            a1, d, n = R.randint(2, 9), R.randint(2, 7), R.randint(4, 8)
            ans = a1 + (n - 1) * d
            return (f"Арифм. прогрессия a₁={a1}, d={d}. a₍{n}₎?", ans, "aₙ = a₁+(n−1)d.", f"{ans}!",
                    [a1 + n * d, a1 * d, ans - d])
        b1, q, n = R.randint(1, 3), R.randint(2, 3), R.randint(3, 5)
        ans = b1 * q ** (n - 1)
        return (f"Геом. прогрессия b₁={b1}, q={q}. b₍{n}₎?", ans, "bₙ = b₁·q^(n−1).", f"{ans}!",
                [b1 * q * n, ans * q, b1 + (n - 1) * q])
    gen("oge", 12, prog)

    def prob():
        t = R.randint(0, 1)
        if t == 0:
            total = pick([4, 5, 8, 10, 20, 25, 50, 100])
            fav = R.randint(1, total - 1)
            ans = fs(fav, total)
            pool = [fs(total - fav, total), fs(fav + 1, total), fs(fav, total + 1),
                    fs(max(1, fav - 1), total), fs(fav, total + fav)]
            wrong, vals = [], {fav / total}
            for w in pool:
                if "/" not in w:
                    continue
                a, b = map(int, w.split("/"))
                v = a / b
                if v not in vals and 0 < v < 1:
                    vals.add(v)
                    wrong.append(w)
                if len(wrong) == 2:
                    break
            if len(wrong) < 2:
                return None
            return (f"В миске {total} вкусняшек, {fav} с рыбой. Вероятность рыбной?", ans,
                    "подходящие ÷ все, сократи.", f"{ans}!", wrong)
        items = [
            ("Вероятность чётного на кубике?", "1/2", "3 чётных из 6.", "3/6 = 1/2!", ["1/3", "1/6"]),
            ("Вероятность числа > 4 на кубике?", "1/3", "5 и 6.", "2/6 = 1/3!", ["1/2", "2/3"]),
            ("Вероятность шестёрки?", "1/6", "одна из 6.", "1/6!", ["1/3", "1/2"]),
            ("Две монеты, два орла?", "1/4", "ОО из 4 исходов.", "1/4!", ["1/2", "1/3"]),
            ("Вероятность НЕ 1 на кубике?", "5/6", "5 из 6.", "5/6!", ["1/6", "1/2"]),
            ("Сумма 7 на двух кубиках?", "1/6", "6 из 36.", "6/36 = 1/6!", ["1/12", "1/36"]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("prob", 14, prob)

    def stat():
        t = R.randint(0, 1)
        if t == 0:
            m = R.randint(5, 20)
            d1, d2 = R.randint(1, 6), R.randint(1, 6)
            nums = [m - d1, m, m + d2, m + d1 - d2]
            R.shuffle(nums)
            return (f"Среднее {', '.join(map(str, nums))}?", m, "сумма ÷ 4.", f"{m}!",
                    [m + 1, sum(nums), sorted(nums)[1]])
        a, b = R.randint(1, 10), R.randint(20, 40)
        mid = R.randint(a + 1, b - 1)
        nums = [a, mid, b]
        R.shuffle(nums)
        return (f"Размах {', '.join(map(str, nums))}?", b - a, "max − min.", f"{b - a}!",
                [b, mid, b - a + 1])
    gen("stat", 8, stat)

    def quadfunc():
        a, b = R.randint(1, 4), R.randint(2, 8) * 2
        xv = -b // (2 * a)
        return (f"y = {a}x² {'+' if b >= 0 else '−'} {abs(b)}x + 1. Абсцисса вершины?", xv, "x = −b/(2a).",
                f"{xv}!", [xv + 1, -xv, b // a])
    gen("alg", 10, quadfunc)

    def ineq():
        a, t = R.randint(2, 6), R.randint(2, 12)
        c = a * t + R.randint(1, a - 1)
        return (f"Наименьшее целое x: {a}x > {c}?", t + 1, f"{c}÷{a}, следующее целое.", f"{t + 1}!",
                [t, t + 2, c // a])
    gen("eq", 8, ineq)

    def geom():
        t = R.randint(0, 3)
        if t == 0:
            a, b, c = pick([(3, 4, 5), (6, 8, 10), (5, 12, 13), (8, 15, 17), (9, 12, 15)])
            return (f"Катеты {a}, {b}. Гипотенуза?", c, "Пифагор.", f"{c}!", [a + b, c + 1, c - 2])
        if t == 1:
            arc = R.randint(20, 160)
            return (f"Вписанный угол опирается на дугу {arc}°. Угол?", arc // 2, "вписанный = ½ дуги.",
                    f"{arc // 2}°!", [arc, arc * 2, arc // 2 + 1])
        if t == 2:
            b, h = R.randint(3, 12), R.randint(2, 8) * 2
            return (f"Площадь треугольника: основание {b}, высота {h}?", b * h // 2, "½·b·h.",
                    f"{b * h // 2}!", [b * h, b + h, b * h // 2 + 1])
        n = pick([5, 6, 8])
        return (f"Сумма углов {n}-угольника?", (n - 2) * 180, "(n−2)·180.", f"{(n - 2) * 180}°!",
                [(n - 1) * 180, n * 180, (n - 2) * 180 + 180])
    gen("geom", 16, geom)

    def word():
        t = R.randint(0, 1)
        if t == 0:
            a, b = pick([(6, 3), (12, 4), (15, 10), (4, 4), (8, 8), (6, 6)])
            ans = a * b // (a + b)
            return (f"Саян съедает мешок за {a} дн, Мурка за {b}. Вместе?", ans, "1/a+1/b, переверни.",
                    f"{ans} дн!", [a + b, (a + b) // 2, ans + 1])
        k = R.randint(3, 8)
        n = k * R.randint(2, 9) + R.randint(1, k - 1)
        ans = math.ceil(n / k)
        return (f"{n} рыбок по {k} в коробку. Коробок?", ans, "округли вверх.", f"{ans}!",
                [n // k, ans + 1, n // k - 1])
    gen("word", 12, word)

    def practical():
        t = R.randint(0, 1)
        if t == 0:
            a, b = R.randint(2, 9), R.randint(2, 9)
            n = R.randint(10, 40)
            fee = R.randint(10, 50)
            cost1, cost2 = a * n, b * n + fee
            ans = "Первый" if cost1 < cost2 else "Второй"
            return (f"Тариф 1: {a}/шт. Тариф 2: {b}/шт + {fee} абонплата. Что выгоднее при {n} шт?", ans,
                    "Посчитай оба: a·n и b·n+абонплата.", f"{ans} выгоднее!",
                    ["Второй" if ans == "Первый" else "Первый", "Одинаково"])
        side = R.randint(2, 6)
        tile = R.randint(1, 3)
        n = (side * side) // (tile * tile)
        return (f"Пол {side}×{side} м, плитка {tile}×{tile} м. Сколько плиток?", n, "площадь пола ÷ площадь плитки.",
                f"{n}!", [n + 1, side * side, n - 1])
    gen("oge", 10, practical)

    def expr():
        b, n = pick([(2, R.randint(2, 8)), (3, R.randint(2, 4)), (10, R.randint(2, 5))])
        ans = b ** n
        return (f"{b}{sup(n)} = ?", ans, f"умножь {b} само на себя {n} {times(n)}.", f"{ans}!",
                [b * n, ans * b, ans // b])
    gen("pow", 8, expr)


# ============================================================ 10 класс (Алимов)
TRIG = {
    0: ("0", "1", "0"), 30: ("1/2", "√3/2", "√3/3"), 45: ("√2/2", "√2/2", "1"),
    60: ("√3/2", "1/2", "√3"), 90: ("1", "0", None), 120: ("√3/2", "−1/2", "−√3"),
    135: ("√2/2", "−√2/2", "−1"), 150: ("1/2", "−√3/2", "−√3/3"), 180: ("0", "−1", "0"),
    210: ("−1/2", "−√3/2", "√3/3"), 225: ("−√2/2", "−√2/2", "1"), 240: ("−√3/2", "−1/2", "√3"),
    270: ("−1", "0", None), 300: ("−√3/2", "1/2", "−√3"), 315: ("−√2/2", "√2/2", "−1"),
    330: ("−1/2", "√3/2", "−√3/3"), 360: ("0", "1", "0"),
}
TRIG_POOL = ["0", "1/2", "√2/2", "√3/2", "1", "−1", "−1/2", "√3", "√3/3"]


def trig_wrong(ans):
    pool = [w for w in TRIG_POOL if w != ans]
    R.shuffle(pool)
    return pool[:2]


def gen_g10():
    def trigval():
        deg = pick(list(TRIG))
        fn = R.randint(0, 2)
        names = ["sin", "cos", "tg"]
        val = TRIG[deg][fn]
        if val is None:
            return None
        return (f"{names[fn]} {deg}° = ?", val, "Табличные значения тригонометрии.",
                f"{names[fn]} {deg}° = {val}!", trig_wrong(val))
    gen("trig", 16, trigval)

    def trigident():
        t = R.randint(0, 6)
        if t == 0:
            return ("sin²α + cos²α = ?", "1", "Основное тригонометрическое тождество.", "1!", ["0", "2"])
        if t == 1:
            deg = pick([30, 45, 60, 90])
            return (f"2·sin {deg}°·cos {deg}° = sin …°?", 2 * deg, "sin 2α = 2 sin α cos α.",
                    f"sin {2 * deg}°!", [deg, 2 * deg + 1, 90 - deg])
        if t == 2:
            deg = pick([30, 45, 60, 90])
            return (f"sin²{deg}° + cos²{deg}° = ?", 1, "Для любого угла сумма квадратов = 1.",
                    "1!", [0, 2])
        if t == 3:
            return ("1 − cos²α = ?", "sin²α", "Из sin²α + cos²α = 1.", "sin²α!", ["cos²α", "1"])
        if t == 4:
            return ("tg α · ctg α = ?", "1", "tg и ctg — взаимно обратные.", "1!", ["0", "tg²α"])
        if t == 5:
            return ("cos²α − sin²α = ?", "cos 2α", "Косинус двойного угла.", "cos 2α!", ["sin 2α", "1"])
        return ("sin(−α) = ?", "−sin α", "Синус — нечётная функция.", "−sin α!", ["sin α", "cos α"])
    gen("trig", 12, trigident)

    def trigform():
        deg = pick([30, 45, 60, 120, 150])
        t = R.randint(0, 2)
        if t == 0:
            val = TRIG[180 - deg][0]
            return (f"sin(180° − {deg}°) = ?", val, "sin(180−α) = sin α.", f"{val}!", trig_wrong(val))
        if t == 1:
            val = TRIG[180 - deg][1]
            return (f"cos(180° − {deg}°) = ?", val, "cos(180−α) = −cos α.", f"{val}!", trig_wrong(val))
        val = TRIG[180 - deg][2]
        if val is None:
            return None
        return (f"tg(180° − {deg}°) = ?", val, "tg(180−α) = −tg α.", f"{val}!", trig_wrong(val))
    gen("trig", 12, trigform)

    def trigeq():
        items = [
            ("sin x = 1/2, наименьший положительный x (град)?", 30, "sin 30° = 1/2.", "30°!", [60, 45]),
            ("cos x = 1/2, наименьший положительный x (град)?", 60, "cos 60° = 1/2.", "60°!", [30, 45]),
            ("tg x = 1, наименьший положительный x (град)?", 45, "tg 45° = 1.", "45°!", [30, 60]),
            ("Сколько решений sin x = 0 на [0°; 360°]?", 3, "0°, 180°, 360°.", "3!", [2, 4]),
            ("sin x = √2/2, наименьший положительный x (град)?", 45, "sin 45° = √2/2.", "45°!", [30, 60]),
            ("cos x = √3/2, наименьший положительный x (град)?", 30, "cos 30° = √3/2.", "30°!", [60, 45]),
            ("sin x = 1, наименьший положительный x (град)?", 90, "sin 90° = 1.", "90°!", [0, 180]),
            ("cos x = 0, наименьший положительный x (град)?", 90, "cos 90° = 0.", "90°!", [0, 180]),
            ("tg x = √3, наименьший положительный x (град)?", 60, "tg 60° = √3.", "60°!", [30, 45]),
            ("sin x = 0, наименьший положительный x (град)?", 180, "sin 180° = 0 (0 не положительный).", "180°!", [90, 360]),
            ("Сколько решений cos x = 1 на [0°; 360°]?", 2, "0° и 360°.", "2!", [1, 3]),
            ("cos x = −1/2, наименьший положительный x (град)?", 120, "cos 120° = −1/2.", "120°!", [60, 150]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("trig", 12, trigeq)

    def der():
        t = R.randint(0, 2)
        if t == 0:
            n, x = R.randint(2, 5), R.randint(1, 5)
            ans = n * x ** (n - 1)
            return (f"f(x) = x{sup(n)}. f'({x}) = ?", ans, "f' = n·x^(n−1).", f"{ans}!",
                    [n * x ** n, (n - 1) * x ** (n - 1), ans + 1])
        if t == 1:
            a, n, x = R.randint(2, 6), R.randint(2, 4), R.randint(1, 4)
            ans = a * n * x ** (n - 1)
            return (f"f(x) = {a}x{sup(n)}. f'({x}) = ?", ans, "f' = a·n·x^(n−1).", f"{ans}!",
                    [a * x ** n, a * n * x ** n, ans + a])
        items = [
            ("f(x) = sin x. f'(0) = ?", 1, "(sin)' = cos, cos 0 = 1.", "1!", [0, -1]),
            ("f(x) = cos x. f'(0) = ?", 0, "(cos)' = −sin, −sin 0 = 0.", "0!", [1, -1]),
            ("f(x) = cos x. f'(π/2) = ?", -1, "(cos)' = −sin, −sin(π/2) = −1.", "−1!", [0, 1]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("der", 18, der)

    def derapp():
        t = R.randint(0, 1)
        if t == 0:
            a, b, x = R.randint(1, 5), R.randint(1, 9), R.randint(1, 5)
            return (f"y = {a}x² + {b}. Угловой коэффициент касательной в x = {x}?", 2 * a * x,
                    "k = y'(x0) = 2a·x0.", f"{2 * a * x}!", [a * x * x + b, 2 * a * x + 1, a * x])
        a, t_ = R.randint(1, 5), R.randint(1, 6)
        return (f"s(t) = {a}t². Скорость в t = {t_}?", 2 * a * t_, "v = s'(t) = 2a·t.", f"{2 * a * t_}!",
                [a * t_ * t_, 2 * a * t_ + 1, a * t_])
    gen("der", 12, derapp)

    def explog():
        items = [
            ("2^x = 8. x = ?", 3, "8 = 2³.", "3!", [2, 4]),
            ("log₂ 8 = ?", 3, "2³ = 8.", "3!", [2, 4]),
            ("log₃ 9 = ?", 2, "3² = 9.", "2!", [3, 1]),
            ("3^x = 27. x = ?", 3, "27 = 3³.", "3!", [2, 9]),
            ("log₅ 25 = ?", 2, "5² = 25.", "2!", [5, 3]),
            ("5^x = 125. x = ?", 3, "125 = 5³.", "3!", [2, 4]),
            ("log₂ 16 = ?", 4, "2⁴ = 16.", "4!", [2, 3]),
            ("log₄ 16 = ?", 2, "4² = 16.", "2!", [4, 3]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("log", 8, explog)

    def prob():
        items = [
            ("Кубик: вероятность чётного числа?", "1/2", "3 из 6.", "1/2!", ["1/3", "1/6"]),
            ("Две монеты: обе решки?", "1/4", "1 из 4.", "1/4!", ["1/2", "1/3"]),
            ("Кубик: вероятность числа, не равного 1?", "5/6", "5 из 6.", "5/6!", ["1/6", "1/2"]),
            ("Вероятность выпадения 6 на кубике?", "1/6", "1 из 6.", "1/6!", ["1/3", "1/2"]),
            ("Вероятность числа больше 4 на кубике?", "1/3", "5 и 6 — это 2 из 6.", "2/6 = 1/3!", ["1/2", "1/6"]),
            ("Две монеты, хотя бы один орёл?", "3/4", "ОО, ОР, РО — 3 из 4.", "3/4!", ["1/2", "1/4"]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("prob", 6, prob)

    def stereom():
        a = R.randint(2, 6)
        t = R.randint(0, 1)
        if t == 0:
            return (f"Объём куба с ребром {a}?", a ** 3, "V = a³.", f"{a ** 3}!", [6 * a * a, a * a, a ** 3 + a])
        return (f"Диагональ куба с ребром {a} = a√…?", 3, "d = a√3.", "3!", [2, 6])
    gen("geom", 4, stereom)


# ============================================================ 11 класс
def gen_g11():
    def integral():
        t = R.randint(0, 1)
        if t == 0:
            n = R.randint(1, 4)
            a = R.randint(1, 4)
            ans = a ** (n + 1) // (n + 1)
            return (f"∫₀{sup(a)} x{sup(n)} dx = ?", ans, "первообразная x^(n+1)/(n+1).", f"{ans}!",
                    [a ** n, ans + 1, a ** (n + 1)])
        a = R.randint(1, 4)
        return (f"∫₀{sup(a)} 2x dx = ?", a * a, "первообразная x².", f"{a * a}!", [2 * a, a * a + 1, a])
    gen("int", 16, integral)

    def log():
        t = R.randint(0, 2)
        if t == 0:
            b, k = pick([2, 3, 5]), R.randint(2, 4)
            return (f"log₍{b}₎ {b ** k} = ?", k, f"{b}^{k} = {b ** k}.", f"{k}!", [k + 1, b, k - 1])
        if t == 1:
            b, x, y = pick([2, 3]), R.randint(1, 3), R.randint(1, 3)
            return (f"log₍{b}₎ {b ** x} + log₍{b}₎ {b ** y} = ?", x + y, "log a + log b = log(ab).",
                    f"{x + y}!", [x * y, x + y + 1, x - y])
        b, x, y = pick([2, 3]), R.randint(2, 4), R.randint(1, 2)
        return (f"log₍{b}₎ {b ** x} − log₍{b}₎ {b ** y} = ?", x - y, "log a − log b = log(a/b).",
                f"{x - y}!", [x + y, x - y + 1, x * y])
    gen("log", 16, log)

    def logeq():
        b, c = pick([2, 3, 5]), R.randint(2, 4)
        a = R.randint(1, 9)
        return (f"log₍{b}₎ (x − {a}) = {c}. x = ?", b ** c + a, f"x − {a} = {b}^{c}.", f"{b ** c + a}!",
                [b ** c, b ** c + a + 1, b * c + a])
    gen("log", 12, logeq)

    def expineq():
        items = [
            ("2^x > 8. Решение?", "x > 3", "8 = 2³, основание > 1.", "x > 3!", ["x < 3", "x > 8"]),
            ("(1/2)^x < (1/2)³. Решение?", "x > 3", "основание < 1 — знак меняется.", "x > 3!", ["x < 3", "x > −3"]),
            ("3^x ≤ 9. Решение?", "x ≤ 2", "9 = 3².", "x ≤ 2!", ["x ≥ 2", "x ≤ 9"]),
            ("2^x < 16. Решение?", "x < 4", "16 = 2⁴, основание > 1.", "x < 4!", ["x > 4", "x < 16"]),
            ("5^x ≥ 25. Решение?", "x ≥ 2", "25 = 5².", "x ≥ 2!", ["x ≤ 2", "x ≥ 25"]),
            ("(1/3)^x > (1/3)². Решение?", "x < 2", "основание < 1 — знак меняется.", "x < 2!", ["x > 2", "x < −2"]),
            ("3^x > 27. Решение?", "x > 3", "27 = 3³.", "x > 3!", ["x < 3", "x > 27"]),
            ("2^x ≤ 1. Решение?", "x ≤ 0", "1 = 2⁰.", "x ≤ 0!", ["x ≥ 0", "x ≤ 1"]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("alg", 8, expineq)

    def stereom():
        t = R.randint(0, 2)
        if t == 0:
            sb = pick([3, 6, 9, 12])
            h = R.randint(2, 9)
            return (f"Пирамида: S основания {sb}, высота {h}. Объём?", sb * h // 3, "V = ⅓·S·h.",
                    f"{sb * h // 3}!", [sb * h, sb * h // 3 + 1, sb + h])
        if t == 1:
            r = pick([3, 6, 9])
            return (f"Шар r = {r}. Объём = …π (V = 4/3·π·r³)?", 4 * r ** 3 // 3, "4/3·r³.",
                    f"{4 * r ** 3 // 3}π!", [4 * r ** 3, r ** 3, 4 * r ** 3 // 3 + 1])
        r, h = R.randint(2, 6), R.randint(2, 9)
        return (f"Цилиндр r = {r}, h = {h}. Объём = …π?", r * r * h, "V = πr²h.", f"{r * r * h}π!",
                [2 * r * h, r * h, r * r * h + 1])
    gen("geom", 18, stereom)

    def comb():
        t = R.randint(0, 2)
        if t == 0:
            n = R.randint(3, 7)
            return (f"{n}! = ?", math.factorial(n), "произведение 1·2·…·n.", f"{math.factorial(n)}!",
                    [math.factorial(n) // n, math.factorial(n) + n, n * n])
        if t == 1:
            n, k = R.randint(4, 8), 2
            ans = math.comb(n, k)
            return (f"C({n}, {k}) = ?", ans, "n!/(k!(n−k)!).", f"{ans}!", [ans + 1, n * k, ans * 2])
        n, k = R.randint(4, 6), 3
        ans = math.comb(n, k)
        return (f"C({n}, {k}) = ?", ans, "n!/(k!(n−k)!).", f"{ans}!", [ans + 1, n * k, ans * 2])
    gen("prob", 10, comb)

    def derapp2():
        a, b = R.randint(1, 4), R.randint(2, 8) * 2
        xv = b // (2 * a)
        return (f"y = {a}x² − {b}x + 1. Точка минимума x = ?", xv, "y' = 2ax − b = 0.", f"{xv}!",
                [xv + 1, -xv, b // a])
    gen("der", 8, derapp2)

    def probstat():
        m = R.randint(5, 20)
        d1, d2 = R.randint(1, 6), R.randint(1, 6)
        nums = [m - d1, m, m + d2, m + d1 - d2]
        R.shuffle(nums)
        return (f"Среднее {', '.join(map(str, nums))}?", m, "сумма ÷ 4.", f"{m}!",
                [m + 1, sum(nums), sorted(nums)[1]])
    gen("stat", 6, probstat)

    def func():
        items = [
            ("Область определения y = √(x − 3)?", "x ≥ 3", "под корнем ≥ 0.", "x ≥ 3!", ["x > 3", "x ≤ 3"]),
            ("Область определения y = log₂(x − 1)?", "x > 1", "аргумент логарифма > 0.", "x > 1!", ["x ≥ 1", "x > 0"]),
            ("Область определения y = 1/(x − 2)?", "x ≠ 2", "знаменатель ≠ 0.", "x ≠ 2!", ["x > 2", "x ≠ 0"]),
            ("Область определения y = √(x + 2)?", "x ≥ −2", "под корнем ≥ 0.", "x ≥ −2!", ["x > −2", "x ≤ −2"]),
            ("Область определения y = 1/(x + 4)?", "x ≠ −4", "знаменатель ≠ 0.", "x ≠ −4!", ["x > −4", "x ≠ 0"]),
            ("Область определения y = log₃(x + 5)?", "x > −5", "аргумент логарифма > 0.", "x > −5!", ["x ≥ −5", "x > 0"]),
        ]
        q, a, h, e, w = pick(items)
        return (q, a, h, e, w)
    gen("alg", 6, func)


LEVELS = [
    [0, "Котёнок-первоклассник"], [25, "Дежурный по тетрадкам"],
    [75, "Знаток таблицы умножения"], [160, "Повелитель циркуля и усов"],
    [300, "Хранитель твёрдых пятёрок"], [500, "Кандидат мурлычных наук"],
    [800, "Профессор геометрии и тыгыдыка"], [1250, "Академик математики на максимум"],
    [2000, "Легендарный Архитектор Уюта"], [3200, "Магистр девяти жизней"],
    [5000, "Гранд-мастер уюта"], [8000, "Хранитель всех фотокарточек"],
    [13000, "Легенда кошачьей математики"], [21000, "Бессмертный Саян 👑"],
]
MILESTONES = {
    "1": "Первая лапка! Добро пожаловать в уютную компанию Саяна! 🐾",
    "5": "Первая твёрдая пятёрка! Так держать! 5️⃣",
    "25": "25 лапок — Саян официально назначен дежурным по твоим тетрадкам! 📓",
    "50": "50 лапок! Половина сотни пройдена с мурчанием! ✨",
    "100": "100 лапок! Стопроцентный уровень кошачьего антистресса! 💯",
    "150": "150 лапок! Усы Саяна ловят геометрические теоремы на лету! 📐",
    "314": "Число Пи-Мурр! 314 лапок — идеальная окружность уюта и математики! 🥧🐾",
    "500": "500 лапок! Саян защитил диссертацию мурлычных наук! 🎓",
    "777": "777 лапок! Тройная кошачья удача на контрольных и экзаменах! 🍀",
    "1000": "1000 лапок! Тысячекратное мурлыканье поддержки! 🏆",
    "1500": "1500 лапок! Ни одна контрольная не устоит перед таким настроем! ☕",
    "2000": "2000 лапок! Звание Легендарного Архитектора Уюта получено! 👑",
    "3200": "3200 лапок! Магистр девяти жизней — престиж уже не за горами! 🌟",
    "5000": "5000 лапок! Гранд-мастер уюта: Саян гордится тобой! 🏅",
    "10000": "10000 лапок! Десять тысяч — это серьёзная заявка на бессмертие! 🌌",
    "21000": "21000 лапок! Все фотокарточки открыты — Саян полностью твой! 📸👑",
}

GRADE_FUNCS = [gen_g1, gen_g2, gen_g3, gen_g4, gen_g5, gen_g6,
               gen_g7, gen_g8, gen_g9, gen_g10, gen_g11]


def main():
    global CUR
    for g, fn in enumerate(GRADE_FUNCS, start=1):
        CUR = g
        fn()
    total = sum(len(b) for b in BANKS.values())
    assert total == 1110, total
    assert len(SEEN) == total, (len(SEEN), total)
    for g, b in BANKS.items():
        assert len(b) >= 90, (g, len(b))
        for q in b:
            assert len(q["o"]) == 3 and len(set(q["o"])) == 3, q
            assert 0 <= q["c"] <= 2 and q["h"] and q["e"], q
        R.shuffle(b)
    data = {"grades": {str(g): BANKS[g] for g in range(1, 12)}, "cats": CATS,
            "levels": LEVELS, "milestones": MILESTONES, "quizReward": 30}
    out = Path(__file__).resolve().parent.parent / "docs" / "quiz-data.js"
    out.write_text("window.SAYAN_DATA = " + json.dumps(data, ensure_ascii=False, separators=(", ", ": ")) + ";\n",
                   encoding="utf-8")
    print(f"OK: {total} questions across 11 grades -> {out}")
    print({g: len(b) for g, b in BANKS.items()})


if __name__ == "__main__":
    main()