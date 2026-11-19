"""Редактор босса, встроенный в правую панель."""

import copy

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .animation import AnimationEditor
from .boss_preview import BossPreview
from .canvas import opaque_bounds
from .scripting import ScriptEditor
from .theme import THEME, make_scroll_form_tab, section_label


# Способы поведения, которые генератор умеет собирать в C#-код.
BOSS_AI_OPTIONS = (
    ("Парение над игроком", "hover"),
    ("Прыжки по земле", "jump"),
    ("Рывки и паузы", "charge"),
    ("Кружит вокруг игрока", "orbit"),
    ("Телепортация к игроку", "teleport"),
)

BOSS_AI_LABELS = {
    code: label for label, code in BOSS_AI_OPTIONS
}
BOSS_AI_CODES = frozenset(BOSS_AI_LABELS)

# Что делает каждое поведение — эти тексты видит пользователь.
BOSS_AI_DESCRIPTIONS = {
    "hover": (
        "Босс держится на заданной высоте над игроком и плавно догоняет "
        "его. Не проваливается сквозь блоки."
    ),
    "jump": (
        "Босс бежит по земле в сторону игрока и прыгает, когда оказывается "
        "рядом. Учитывает блоки и гравитацию."
    ),
    "charge": (
        "Босс замирает, прицеливается и резко бросается на игрока, затем "
        "снова замирает. Летает сквозь блоки, как Око Ктулху."
    ),
    "orbit": (
        "Босс кружит вокруг игрока по кругу заданного радиуса. Хорошо "
        "сочетается со спиральными выстрелами."
    ),
    "teleport": (
        "Босс периодически исчезает и появляется рядом с игроком, а между "
        "телепортами медленно подплывает к нему."
    ),
}

# Состояния, для которых можно нарисовать отдельную ленту кадров.
BOSS_ANIMATION_STATES = (
    ("idle", "Покой"),
    ("move", "Движение"),
    ("attack", "Атака"),
    ("jump", "Прыжок"),
)

BOSS_ANIMATION_STATE_IDS = {
    state: index
    for index, (state, _label) in enumerate(BOSS_ANIMATION_STATES)
}

# Ванильная музыка, которую можно назначить боссу.
BOSS_MUSIC_OPTIONS = (
    ("Как у обычного босса", ""),
    ("Boss 1", "Boss1"),
    ("Boss 2", "Boss2"),
    ("Boss 3", "Boss3"),
    ("Boss 4", "Boss4"),
    ("Boss 5", "Boss5"),
    ("Eerie", "Eerie"),
)

# Дебаффы для иммунитетов и накладывания при касании.
BOSS_BUFF_OPTIONS = (
    ("Огонь", "OnFire"),
    ("Яд", "Poisoned"),
    ("Кровотечение", "Bleeding"),
    ("Замедление", "Slow"),
    ("Слабость", "Weak"),
    ("Замешательство", "Confused"),
    ("Проклятое пламя", "CursedInferno"),
    ("Ихор", "Ichor"),
    ("Обморожение", "Frostburn"),
    ("Ядовитый укус", "Venom"),
    ("Темнота", "Darkness"),
    ("Немота", "Silenced"),
    ("Проклятие", "Cursed"),
    ("Разрушенная броня", "BrokenArmor"),
    ("Электризация", "Electrified"),
    ("Озноб", "Chilled"),
    ("Паутина", "Webbed"),
    ("Окаменение", "Stoned"),
    ("Горение", "Burning"),
    ("Теневое пламя", "ShadowFlame"),
    ("Ошеломление", "Dazed"),
)

BOSS_BUFF_CODES = frozenset(code for _label, code in BOSS_BUFF_OPTIONS)

# Готовые ванильные снаряды для дальней атаки.
BOSS_PROJECTILE_OPTIONS = (
    ("Демоническая коса", "DemonScythe"),
    ("Проклятое пламя", "CursedFlameHostile"),
    ("Лазер смерти", "DeathLaser"),
    ("Глазной лазер", "EyeLaser"),
    ("Тёмный луч", "ShadowBeamHostile"),
    ("Ледяной залп", "FrostBlastHostile"),
    ("Огненный глаз", "EyeFire"),
    ("Рунный взрыв", "RuneBlast"),
    ("Розовый лазер", "PinkLaser"),
    ("Нечестивый трезубец", "UnholyTridentHostile"),
    ("Демонический серп", "DemonSickle"),
    ("Бомба Скелетрона", "BombSkeletronPrime"),
    ("Блуждающая душа", "LostSoulHostile"),
)

BOSS_PROJECTILE_CODES = frozenset(
    code for _label, code in BOSS_PROJECTILE_OPTIONS
)

# Узоры стрельбы. Разброс в узорах используется по-разному.
BOSS_SHOOT_PATTERNS = (
    ("Веер в игрока", "fan"),
    ("Круг во все стороны", "radial"),
    ("Спираль", "spiral"),
)

BOSS_SHOOT_PATTERN_CODES = frozenset(
    code for _label, code in BOSS_SHOOT_PATTERNS
)

BOSS_SHOOT_PATTERN_LABELS = {
    code: label for label, code in BOSS_SHOOT_PATTERNS
}

# Откуда берётся снаряд: ванильный ID или собственный класс от TMC.
BOSS_SHOOT_SOURCES = (
    ("Ванильный снаряд", "vanilla"),
    ("Свой снаряд (TMC создаст класс)", "custom"),
)

BOSS_SHOOT_SOURCE_CODES = frozenset(
    code for _label, code in BOSS_SHOOT_SOURCES
)

# Ингредиенты для рецепта предмета-призыва.
BOSS_RECIPE_INGREDIENTS = (
    ("Гель", "Gel"),
    ("Линза", "Lens"),
    ("Кость", "Bone"),
    ("Перо", "Feather"),
    ("Гнилой кусок", "RottenChunk"),
    ("Позвонок", "Vertebra"),
    ("Дерево", "Wood"),
    ("Факел", "Torch"),
    ("Серебряный слиток", "SilverBar"),
    ("Золотой слиток", "GoldBar"),
    ("Демонитовый слиток", "DemoniteBar"),
    ("Кримтановый слиток", "CrimtaneBar"),
    ("Святой слиток", "HallowedBar"),
    ("Адамантитовый слиток", "AdamantiteBar"),
    ("Титановый слиток", "TitaniumBar"),
    ("Душа света", "SoulofLight"),
    ("Душа ночи", "SoulofNight"),
)

BOSS_RECIPE_INGREDIENT_CODES = frozenset(
    code for _label, code in BOSS_RECIPE_INGREDIENTS
)

# Станции для рецепта призыва.
BOSS_RECIPE_STATIONS = (
    ("Без станции", ""),
    ("Верстак", "WorkBenches"),
    ("Наковальня", "Anvils"),
    ("Печь", "Furnaces"),
    ("Демонический алтарь", "DemonAltar"),
    ("Книжная полка", "Bookcases"),
)

BOSS_RECIPE_STATION_CODES = frozenset(
    code for _label, code in BOSS_RECIPE_STATIONS
)

# Кого босс может призывать в бою: готовые ванильные NPC.
BOSS_SUMMON_NPC_OPTIONS = (
    ("Зомби", "Zombie"),
    ("Демонический глаз", "DemonEye"),
    ("Слизень", "BlueSlime"),
    ("Скелет", "Skeleton"),
    ("Шершень", "Hornet"),
    ("Пещерная мышь", "CaveBat"),
    ("Гарпия", "Harpy"),
    ("Кримера", "Crimera"),
    ("Пожиратель душ", "EaterofSouls"),
    ("Розовый слизень", "Pinky"),
    ("Лицо-монстр", "FaceMonster"),
)

BOSS_SUMMON_NPC_CODES = frozenset(
    code for _label, code in BOSS_SUMMON_NPC_OPTIONS
)

# Старые данные TMC: «Slime» в Terraria называется BlueSlime.
BOSS_SUMMON_NPC_ALIASES = {
    "Slime": "BlueSlime",
}


def normalize_adds_npc(value):
    """Приводит ID моба призыва к известному или возвращает пустую строку."""

    code = str(value or "")
    code = BOSS_SUMMON_NPC_ALIASES.get(code, code)

    return code if code in BOSS_SUMMON_NPC_CODES else ""

MAX_BOSS_PHASES = 8

DEFAULT_DASH = {
    "enabled": False,
    "interval_ticks": 300,
    "speed": 18.0,
    "duration_ticks": 30,
    "expert_only": False,
}

DEFAULT_SHOOT = {
    "enabled": False,
    "interval_ticks": 180,
    "pattern": "fan",
    "source": "vanilla",
    "projectile": "DemonScythe",
    "damage": 20,
    "count": 3,
    "spread_degrees": 12.0,
    "speed": 8.0,
    "spiral_step": 20.0,
    "color": "#ff9b3d",
    "radius": 12,
    "homing": 0.0,
    "pierce": 1,
    "lifetime_ticks": 300,
    "expert_only": False,
}

DEFAULT_CONTACT_BUFF = {
    "enabled": False,
    "buff": "OnFire",
    "duration_ticks": 300,
}

DEFAULT_SUMMON_RECIPE = {
    "enabled": False,
    "item": "Gel",
    "count": 5,
    "station": "WorkBenches",
}

# Призыв мобов во время боя.
DEFAULT_ADD_ATTACK = {
    "enabled": False,
    "interval_ticks": 600,
    "npc": "Zombie",
    "count": 1,
    "expert_only": False,
}

DEFAULT_PHASE = {
    "name": "Фаза 1",
    "threshold": 1.0,
    "speed_multiplier": 1.0,
    "attack_multiplier": 1.0,
}

# Начальные боевые параметры нового босса.
DEFAULT_BOSS_STATS = {
    "life_max": 4000,
    "damage": 30,
    "defense": 10,
    "knockback_resist": 0.0,
    "width": 100,
    "height": 100,
    "scale": 1.0,
    "value_copper": 100000,
    "ai": "hover",
    "movement_speed": 6.0,
    "hover_height": 180,
    "jump_force": 10.0,
    "orbit_radius": 260,
    "orbit_speed": 1.5,
    "teleport_interval": 240,
    "teleport_range": 320,
    "charge_speed": 16.0,
    "charge_pause": 90,
    "expert_life_percent": 100,
    "master_life_percent": 100,
}

# Готовые образы боссов: заполняют характеристики и атаки одним нажатием.
BOSS_TEMPLATES = (
    {
        "title": "Король слизней — прыжки",
        "hint": (
            "Классический прыгающий босс: много здоровья, мягкие прыжки, "
            "без дальних атак. Хорошая основа для первого босса."
        ),
        "music": "Boss1",
        "stats": {
            "life_max": 2000,
            "damage": 24,
            "defense": 6,
            "knockback_resist": 0.0,
            "width": 120,
            "height": 90,
            "scale": 1.6,
            "value_copper": 50000,
            "ai": "jump",
            "movement_speed": 4.5,
            "jump_force": 9.5,
        },
        "actions": {
            "dash": {"enabled": False},
            "shoot": {"enabled": False},
        },
    },
    {
        "title": "Око Ктулху — парение и рывки",
        "hint": (
            "Летающий босс держится над игроком и периодически бросается "
            "в него. Анимация «Атака» включается на время рывка."
        ),
        "music": "Boss1",
        "stats": {
            "life_max": 2800,
            "damage": 24,
            "defense": 4,
            "knockback_resist": 0.1,
            "width": 80,
            "height": 80,
            "scale": 1.0,
            "value_copper": 80000,
            "ai": "hover",
            "movement_speed": 8.0,
            "hover_height": 150,
        },
        "actions": {
            "dash": {
                "enabled": True,
                "interval_ticks": 210,
                "speed": 15.0,
                "duration_ticks": 24,
            },
            "shoot": {"enabled": False},
        },
    },
    {
        "title": "Пожиратель — таранные броски",
        "hint": (
            "Босс замирает, целится и летит напролом. Между рывками "
            "медленно подкрадывается к игроку."
        ),
        "music": "Boss2",
        "stats": {
            "life_max": 4200,
            "damage": 30,
            "defense": 8,
            "knockback_resist": 0.0,
            "width": 100,
            "height": 60,
            "scale": 1.0,
            "value_copper": 90000,
            "ai": "charge",
            "movement_speed": 6.0,
            "charge_speed": 13.0,
            "charge_pause": 100,
        },
        "actions": {
            "dash": {"enabled": False},
            "shoot": {"enabled": False},
        },
    },
    {
        "title": "Колдун — телепорт и кольцо снарядов",
        "hint": (
            "Босс исчезает и появляется рядом, выпуская снаряды во все "
            "стороны. Хорошо смотрится с рунным взрывом или тёмным лучом."
        ),
        "music": "Boss3",
        "stats": {
            "life_max": 3200,
            "damage": 28,
            "defense": 10,
            "knockback_resist": 0.2,
            "width": 60,
            "height": 90,
            "scale": 1.0,
            "value_copper": 120000,
            "ai": "teleport",
            "movement_speed": 5.0,
            "hover_height": 120,
            "teleport_interval": 240,
            "teleport_range": 300,
        },
        "actions": {
            "dash": {"enabled": False},
            "shoot": {
                "enabled": True,
                "interval_ticks": 210,
                "pattern": "radial",
                "source": "vanilla",
                "projectile": "RuneBlast",
                "damage": 22,
                "count": 8,
                "speed": 7.0,
                "spread_degrees": 45.0,
            },
            "summon": {
                "enabled": True,
                "interval_ticks": 600,
                "npc": "CaveBat",
                "count": 2,
            },
        },
    },
    {
        "title": "Небесный страж — орбита и спираль",
        "hint": (
            "Босс кружит вокруг игрока и раскручивает спираль снарядов. "
            "Две фазы: на половине здоровья становится быстрее и злее."
        ),
        "music": "Boss4",
        "stats": {
            "life_max": 6000,
            "damage": 36,
            "defense": 14,
            "knockback_resist": 0.0,
            "width": 90,
            "height": 90,
            "scale": 1.3,
            "value_copper": 200000,
            "ai": "orbit",
            "movement_speed": 5.0,
            "orbit_radius": 280,
            "orbit_speed": 1.4,
        },
        "actions": {
            "dash": {"enabled": False},
            "shoot": {
                "enabled": True,
                "interval_ticks": 150,
                "pattern": "spiral",
                "source": "vanilla",
                "projectile": "ShadowBeamHostile",
                "damage": 26,
                "count": 4,
                "spread_degrees": 18.0,
                "spiral_step": 23.0,
                "speed": 8.0,
            },
        },
        "phases": [
            {"name": "Фаза 1", "threshold": 1.0,
             "speed_multiplier": 1.0, "attack_multiplier": 1.0},
            {"name": "Фаза 2", "threshold": 0.5,
             "speed_multiplier": 1.25, "attack_multiplier": 1.4},
        ],
    },
    {
        "title": "Древний страж — свой снаряд",
        "hint": (
            "Показывает собственный снаряд TMC: светящийся шар с лёгким "
            "самонаведением, три фазы и мощный рывок. Нужен спрайт босса."
        ),
        "music": "Boss5",
        "stats": {
            "life_max": 9000,
            "damage": 48,
            "defense": 24,
            "knockback_resist": 0.0,
            "width": 110,
            "height": 110,
            "scale": 1.5,
            "value_copper": 400000,
            "ai": "hover",
            "movement_speed": 7.0,
            "hover_height": 200,
        },
        "actions": {
            "dash": {
                "enabled": True,
                "interval_ticks": 300,
                "speed": 18.0,
                "duration_ticks": 30,
            },
            "shoot": {
                "enabled": True,
                "interval_ticks": 150,
                "pattern": "fan",
                "source": "custom",
                "projectile": "DemonScythe",
                "damage": 40,
                "count": 5,
                "spread_degrees": 14.0,
                "speed": 9.0,
                "color": "#8a6bff",
                "radius": 14,
                "homing": 0.04,
                "pierce": 2,
                "lifetime_ticks": 360,
            },
            "summon": {
                "enabled": True,
                "interval_ticks": 480,
                "npc": "Harpy",
                "count": 2,
                "expert_only": True,
            },
        },
        "phases": [
            {"name": "Фаза 1", "threshold": 1.0,
             "speed_multiplier": 1.0, "attack_multiplier": 1.0},
            {"name": "Фаза 2", "threshold": 0.6,
             "speed_multiplier": 1.15, "attack_multiplier": 1.25},
            {"name": "Фаза 3", "threshold": 0.3,
             "speed_multiplier": 1.35, "attack_multiplier": 1.6},
        ],
    },
)


# ============================================================
# НОРМАЛИЗАЦИЯ ДАННЫХ
# ============================================================


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _clamped_int(value, default, minimum, maximum):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = int(default)

    return max(minimum, min(maximum, number))


def _clamped_float(value, default, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float(default)

    if number != number:  # NaN
        number = float(default)

    return max(minimum, min(maximum, number))


def normalize_boss_phases(value):
    """Фазы босса в безопасном виде: первая всегда 100%, пороги убывают."""

    phases = []

    for entry in _as_list(value):
        if not isinstance(entry, dict):
            continue

        name = str(entry.get("name") or "").strip()

        phases.append({
            "name": name or f"Фаза {len(phases) + 1}",
            "threshold": _clamped_float(
                entry.get("threshold"), 1.0, 0.0, 1.0
            ),
            "speed_multiplier": _clamped_float(
                entry.get("speed_multiplier"), 1.0, 0.1, 5.0
            ),
            "attack_multiplier": _clamped_float(
                entry.get("attack_multiplier"), 1.0, 0.1, 5.0
            ),
        })

    if not phases:
        phases = [dict(DEFAULT_PHASE)]

    phases = phases[:MAX_BOSS_PHASES]
    phases[0]["threshold"] = 1.0

    previous = 1.0

    for phase in phases[1:]:
        phase["threshold"] = max(
            0.0, min(phase["threshold"], round(previous - 0.01, 4))
        )
        previous = phase["threshold"]

    return phases


def boss_frame_count(animations):
    """Сколько всего кадров во всех состояниях босса."""

    total = 0

    for state, _label in BOSS_ANIMATION_STATES:
        animation = _as_dict(_as_dict(animations).get(state))
        total += sum(
            1 for frame in _as_list(animation.get("frames"))
            if isinstance(frame, dict)
        )

    return total


def boss_is_animated(animations):
    """Совпадает с правилом генератора: лист кадров нужен от двух кадров."""

    return boss_frame_count(animations) >= 2


def boss_generated_members(data):
    """Члены класса, которые TMC пишет сам для этого босса."""

    members = []
    defense = _as_dict(_as_dict(data).get("defense"))
    contact = _as_dict(defense.get("contact_buff"))

    if contact.get("enabled", False):
        members.append("OnHitPlayer")

    if _as_list(_as_dict(data).get("loot")):
        members.append("OnKill")

    return tuple(members)


def boss_custom_projectile_id(boss_id):
    """Имя класса собственного снаряда босса."""

    return f"{boss_id}_orb"


def boss_custom_projectile_enabled(data):
    shoot = _as_dict(_as_dict(_as_dict(data).get("actions")).get("shoot"))

    return bool(shoot.get("enabled")) and str(
        shoot.get("source", "vanilla")
    ) == "custom"


def empty_boss_animations():
    """Пустые ленты кадров для всех состояний босса."""

    return {
        state: {
            "frames": [],
            "loop": state != "attack",
        }
        for state, _label in BOSS_ANIMATION_STATES
    }


def normalize_boss_animations(data):
    """Достаёт анимации из нового и старого формата данных босса."""

    data = _as_dict(data)
    source = data.get("animations")

    if not isinstance(source, dict):
        source = {}

    result = {}

    for state, _label in BOSS_ANIMATION_STATES:
        animation = source.get(state)

        if not isinstance(animation, dict):
            animation = {}

        frames = animation.get("frames")

        if not isinstance(frames, list):
            frames = []

        result[state] = {
            "frames": list(frames),
            "loop": bool(animation.get("loop", state != "attack")),
        }

    # В проектах до появления состояний была одна анимация.
    # Считаем её анимацией движения, чтобы ничего не потерять.
    if not result["move"]["frames"]:
        legacy = data.get("animation")

        if isinstance(legacy, dict):
            frames = legacy.get("frames")

            if isinstance(frames, list) and frames:
                result["move"] = {
                    "frames": list(frames),
                    "loop": bool(legacy.get("loop", True)),
                }

    return result


# ============================================================
# ПРОВЕРКА ПАРАМЕТРОВ
# ============================================================


def check_boss(boss_id, data, sprite, animations):
    """Проверяет параметры босса и возвращает замечания."""

    issues = []
    prefix = str(boss_id or "босс")

    def add(text):
        issues.append(f"{prefix}: {text}")

    data = _as_dict(data)
    stats = _as_dict(data.get("stats"))
    actions = _as_dict(data.get("actions"))
    defense = _as_dict(data.get("defense"))

    dash = _as_dict(actions.get("dash"))
    shoot = _as_dict(actions.get("shoot"))
    contact = _as_dict(defense.get("contact_buff"))

    if not str(data.get("name", "")).strip():
        add("нет названия — в игре будет показан внутренний ID.")

    life = _clamped_int(stats.get("life_max"), 4000, 1, 10_000_000)
    damage = _clamped_int(stats.get("damage"), 0, 0, 100_000)
    defense_value = _clamped_int(stats.get("defense"), 0, 0, 10_000)
    width = _clamped_int(stats.get("width"), 100, 8, 1024)
    height = _clamped_int(stats.get("height"), 100, 8, 1024)
    scale = _clamped_float(stats.get("scale"), 1.0, 0.1, 10.0)
    speed = _clamped_float(stats.get("movement_speed"), 6.0, 0.1, 30.0)
    ai = str(stats.get("ai", "hover"))

    if life < 100:
        add("меньше 100 здоровья: для босса это почти мгновенная смерть.")

    if damage <= 0:
        add("урон 0: босс не сможет нанести урон игроку.")

    if defense_value > 1000:
        add(f"защита {defense_value}: игрок почти не сможет пробить босса.")

    if width < 16 or height < 16:
        add("хитбокс меньше 16 px: босс будет почти неосязаемым.")

    if max(width, height) > 1024:
        add("хитбокс больше 1024 px: столкновения могут работать странно.")

    if scale < 0.2 or scale > 5.0:
        add(f"масштаб {scale:g}: разумный диапазон — от 0.2 до 5.")

    if ai not in BOSS_AI_CODES:
        add(f"неизвестное поведение «{ai}», будет использовано парение.")
    elif ai == "hover" and speed > 20:
        add(f"скорость {speed:g} для парения очень высокая.")
    elif ai == "jump" and speed > 15:
        add(f"скорость {speed:g} для прыжков очень высокая.")

    if ai == "orbit":
        radius = _clamped_int(stats.get("orbit_radius"), 260, 40, 1500)
        angular = _clamped_float(stats.get("orbit_speed"), 1.5, 0.1, 12.0)

        if radius < 80:
            add(f"радиус орбиты {radius} px: босс будет висеть на игроке.")
        if angular > 6:
            add(f"скорость орбиты {angular:g}°/тик: игрока будет укачивать.")
    elif ai == "teleport":
        interval = _clamped_int(
            stats.get("teleport_interval"), 240, 30, 36_000
        )
        teleport_range = _clamped_int(
            stats.get("teleport_range"), 320, 60, 1200
        )

        if interval < 60:
            add("телепорт чаще раза в секунду: бой станет хаотичным.")
        if teleport_range > 900:
            add(
                f"разброс телепорта {teleport_range} px: босс может "
                "оказаться далеко за экраном."
            )
    elif ai == "charge":
        charge_speed = _clamped_float(
            stats.get("charge_speed"), 16.0, 2.0, 40.0
        )
        pause = _clamped_int(stats.get("charge_pause"), 90, 10, 1200)

        if charge_speed > 30:
            add(f"скорость броска {charge_speed:g} очень высокая.")
        if pause < 30:
            add("пауза между бросками меньше 0.5 секунды: босс не даст передышки.")

    expert = _clamped_int(stats.get("expert_life_percent"), 100, 50, 1000)
    master = _clamped_int(stats.get("master_life_percent"), 100, 50, 1000)

    if master < expert:
        add("в мастере здоровья меньше, чем в эксперте — обычно наоборот.")

    if master > 500:
        add(f"в мастере {master}% здоровья: бой может затянуться на минуты.")

    # --- анимации ---
    state_has_frames = {}
    images = []
    sizes = set()

    for state, label in BOSS_ANIMATION_STATES:
        animation = animations.get(state) if isinstance(animations, dict) else None
        animation = _as_dict(animation)
        state_has_frames[state] = False

        frames = [
            frame
            for frame in _as_list(animation.get("frames"))
            if isinstance(frame, dict)
        ]

        if not frames:
            continue

        state_has_frames[state] = True

        for index, frame in enumerate(frames, 1):
            image = frame.get("image")
            frame_label = f"{label.lower()}, кадр {index}"

            if image is None or image.isNull():
                add(f"{frame_label}: пустой или повреждённый кадр.")
                continue

            bounds = opaque_bounds(image)

            if bounds is None:
                add(
                    f"{frame_label}: полностью прозрачный — в игре "
                    "этого кадра не будет видно."
                )
                continue

            images.append(image)
            sizes.add((image.width(), image.height()))

            if max(image.width(), image.height()) > 512:
                add(
                    f"{frame_label}: больше 512 px, текстура тяжёлая, "
                    "а хитбокс задаётся отдельными полями."
                )

    if not images:
        bounds = opaque_bounds(sprite) if sprite is not None else None

        if bounds is None:
            add("спрайт полностью прозрачный — в игре босса не будет видно.")
        else:
            images = [sprite]
            sizes.add((sprite.width(), sprite.height()))

    if len(sizes) > 1:
        add("кадры разного размера: в лист они будут выровнены по центру.")

    if len(images) > 1:
        frame_height = max(image.height() for image in images)
        total_height = frame_height * len(images)

        if total_height > 4096:
            add(
                f"лист анимации выше 4096 px ({total_height}): "
                "текстура может не загрузиться на слабых видеокартах."
            )

    # --- рывок ---
    if dash.get("enabled"):
        interval = _clamped_int(dash.get("interval_ticks"), 300, 30, 36_000)
        duration = _clamped_int(dash.get("duration_ticks"), 30, 5, 600)
        dash_speed = _clamped_float(dash.get("speed"), 18.0, 1.0, 60.0)

        if interval < 30:
            add("интервал рывка меньше 0.5 секунды — босс будет дёргаться.")
        if duration < 5:
            add("рывок короче 5 тиков — его почти не будет видно.")
        if duration >= interval:
            add("рывок длится не меньше интервала — паузы между рывками нет.")
        if dash_speed > 40:
            add(f"скорость рывка {dash_speed:g} очень высокая.")
        if not state_has_frames.get("attack"):
            add(
                "рывок включён, но у состояния «Атака» нет кадров: "
                "действие будет без отдельной анимации."
            )

    # --- стрельба ---
    if shoot.get("enabled"):
        interval = _clamped_int(shoot.get("interval_ticks"), 180, 30, 36_000)
        shot_damage = _clamped_int(shoot.get("damage"), 20, 0, 100_000)
        count = _clamped_int(shoot.get("count"), 3, 1, 20)
        spread = _clamped_float(shoot.get("spread_degrees"), 12.0, 0.0, 180.0)
        shot_speed = _clamped_float(shoot.get("speed"), 8.0, 1.0, 60.0)
        pattern = str(shoot.get("pattern", "fan"))
        source = str(shoot.get("source", "vanilla"))

        if interval < 30:
            add("интервал стрельбы меньше 0.5 секунды — слишком часто.")
        if shot_damage <= 0:
            add("урон снаряда 0: выстрелы не будут наносить урон.")
        if count > 10:
            add(f"снарядов за выстрел: {count}, это очень много.")
        if shot_speed > 40:
            add(f"скорость снаряда {shot_speed:g} очень высокая.")

        if pattern not in BOSS_SHOOT_PATTERN_CODES:
            add(f"неизвестный узор стрельбы «{pattern}», будет веер.")
            pattern = "fan"

        if source not in BOSS_SHOOT_SOURCE_CODES:
            add(f"неизвестный источник снаряда «{source}», будет ванильный.")
            source = "vanilla"

        if pattern in ("fan", "spiral") and spread <= 0:
            add("разброс 0°: снаряды полетят в одну точку — для веера это мало.")

        if pattern == "fan" and spread > 120:
            add(f"разброс {spread:g}°: снаряды почти не летят в игрока.")

        if pattern == "spiral":
            step = _clamped_float(shoot.get("spiral_step"), 20.0, 1.0, 90.0)

            if step < 5:
                add("шаг спирали меньше 5°: снаряды слипнутся в одну линию.")

        if source == "vanilla":
            projectile = str(shoot.get("projectile", ""))

            if projectile not in BOSS_PROJECTILE_CODES:
                add(
                    f"неизвестный снаряд «{projectile}» — будет "
                    "использован DemonScythe."
                )
        else:
            radius = _clamped_int(shoot.get("radius"), 12, 4, 64)
            homing = _clamped_float(shoot.get("homing"), 0.0, 0.0, 1.0)
            pierce = _clamped_int(shoot.get("pierce"), 1, 1, 10)
            lifetime = _clamped_int(
                shoot.get("lifetime_ticks"), 300, 60, 1800
            )
            color = QColor(str(shoot.get("color") or ""))

            if not color.isValid():
                add("цвет своего снаряда не распознан — будет оранжевый.")

            if radius > 48:
                add(f"радиус снаряда {radius} px: хитбокс будет огромным.")
            if homing > 0.2:
                add(
                    f"самонаведение {homing:g}: снаряды почти не промахиваются, "
                    "это может быть нечестно."
                )
            if pierce > 4:
                add(f"пробивание {pierce}: снаряд проходит сквозь игрока много раз.")
            if lifetime > 900:
                add("снаряд живёт дольше 15 секунд — экран забьётся снарядами.")

        if not state_has_frames.get("attack"):
            add(
                "стрельба включена, но у состояния «Атака» нет кадров: "
                "выстрел будет без отдельной анимации."
            )

    # --- призыв мобов ---
    adds = _as_dict(actions.get("summon"))

    if adds.get("enabled"):
        interval = _clamped_int(
            adds.get("interval_ticks"), 600, 60, 36_000
        )
        count = _clamped_int(adds.get("count"), 1, 1, 10)
        npc = normalize_adds_npc(adds.get("npc"))

        if not npc:
            add(
                "неизвестный моб призыва "
                f"«{adds.get('npc')}» — призыв будет пропущен."
            )

        if interval < 120:
            add("призыв чаще двух секунд: экран забьётся мобами.")

        if count > 5:
            add(f"за один призыв {count} мобов — это очень много.")

    # --- фазы ---
    raw_phases = _as_list(data.get("phases"))
    phases = normalize_boss_phases(raw_phases)

    if len(phases) > 1:
        thresholds = []

        for entry in raw_phases:
            entry = _as_dict(entry)
            thresholds.append(
                _clamped_float(entry.get("threshold"), 1.0, 0.0, 1.0)
            )

        if not all(a > b for a, b in zip(thresholds, thresholds[1:])):
            add("пороги фаз должны убывать: 100% → 60% → 30%.")

        for index, phase in enumerate(phases, 1):
            if index == 1:
                continue

            if phase["speed_multiplier"] > 3:
                add(f"фаза {index}: скорость ×{phase['speed_multiplier']:g} — это очень много.")
            if phase["attack_multiplier"] > 3:
                add(f"фаза {index}: атаки ×{phase['attack_multiplier']:g} — это очень много.")

        if len(phases) > 5:
            add(f"фаз {len(phases)}: игрок вряд ли заметит столько переходов.")

    # --- защита ---
    immunities = _as_list(defense.get("immunities"))
    known_immunities = [
        code for code in immunities if code in BOSS_BUFF_CODES
    ]

    for code in immunities:
        if code not in BOSS_BUFF_CODES:
            add(f"неизвестный иммунитет «{code}» — будет пропущен.")

    if contact.get("enabled"):
        buff = str(contact.get("buff", ""))

        if buff not in BOSS_BUFF_CODES:
            add(f"неизвестный дебафф касания «{buff}» — будет OnFire.")
        if not known_immunities:
            add(
                "босс накладывает дебафф, но не имеет иммунитетов: "
                "себя он тоже сможет поджечь (обычно это не мешает)."
            )

    # --- призыв и рецепт ---
    summon = _as_dict(data.get("summon"))
    recipe = _as_dict(summon.get("recipe"))

    if recipe.get("enabled"):
        if not summon.get("enabled", True):
            add("рецепт призыва включён, но сам предмет-призыв отключён.")

        ingredient = str(recipe.get("item", ""))

        if ingredient not in BOSS_RECIPE_INGREDIENT_CODES:
            add(
                f"неизвестный ингредиент рецепта «{ingredient}» — "
                "рецепт будет пропущен."
            )

        station = str(recipe.get("station", ""))

        if station and station not in BOSS_RECIPE_STATION_CODES:
            add(
                f"неизвестная станция рецепта «{station}» — "
                "рецепт будет без станции."
            )

        if _clamped_int(recipe.get("count"), 5, 1, 999) > 99:
            add("ингредиентов больше 99 — рецепт будет выглядеть странно.")

    # --- мешок с лутом ---
    bag = _as_dict(data.get("bag"))

    if bag.get("enabled"):
        if not _as_list(data.get("loot")):
            add(
                "мешок с лутом включён, но таблица дропа пуста — "
                "мешок не создастся."
            )

    music = str(data.get("music", ""))
    known_music = {code for _label, code in BOSS_MUSIC_OPTIONS}

    if music and music not in known_music:
        add(f"неизвестная музыка «{music}» — будет обычная боевая тема.")

    return issues


def prepare_boss_phases(data):
    """Фазы, готовые для генератора: те же правила, что и в редакторе."""

    return normalize_boss_phases(_as_dict(data).get("phases"))


class BossEditor(QWidget):
    """Форма босса: свойства, бой, фазы, защита, дроп, скрипт и анимации."""

    # Живая сводка для левой панели: данные и текущий ключ.
    changed = Signal(dict, str)

    def __init__(self):
        super().__init__()

        self.loading = False
        self._data = {}
        self.sprite = QImage()
        self.item_choices = []
        self.animation_editors = {}
        self.immunity_boxes = {}
        self.shoot_color = QColor(DEFAULT_SHOOT["color"])

        self.issue_timer = QTimer(self)
        self.issue_timer.setSingleShot(True)
        self.issue_timer.setInterval(250)
        self.issue_timer.timeout.connect(self.refresh_issues)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 6, 0, 0)
        root.setSpacing(6)

        self.title_label = section_label("Босс не выбран")
        root.addWidget(self.title_label)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.build_general_tab()
        self.build_attacks_tab()
        self.build_defense_tab()
        self.build_phases_tab()
        self.build_loot_tab()
        self.build_script_tab()
        self.build_sprite_tab()
        self.build_animation_tab()
        self.build_preview_tab()

        self.issues_label = QLabel()
        self.issues_label.setObjectName("hint")
        self.issues_label.setWordWrap(True)
        root.addWidget(self.issues_label)

        hint = QLabel(
            "Изменения сохраняются автоматически: при переключении объекта, "
            "категории или сохранении проекта. Генератор мода создаст класс "
            "босса, его иконку для карты, собственный снаряд (если выбран) "
            "и, если включено, мешок с лутом и предмет-призыв."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.name.textChanged.connect(self.update_title)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.connect_change_signals()
        self.clear()

    # --------------------------------------------------------
    # TABS
    # --------------------------------------------------------

    def build_general_tab(self):
        tab, form = make_scroll_form_tab(780)
        self.general_form = form

        form.addRow(section_label("ШАБЛОН"))

        template_row = QWidget()
        template_layout = QHBoxLayout(template_row)
        template_layout.setContentsMargins(0, 0, 0, 0)
        template_layout.setSpacing(8)

        self.template_box = QComboBox()

        for template in BOSS_TEMPLATES:
            self.template_box.addItem(template["title"])

        self.template_button = QPushButton("Применить шаблон")
        self.template_button.clicked.connect(self.apply_template)

        template_layout.addWidget(self.template_box, 1)
        template_layout.addWidget(self.template_button)

        form.addRow(template_row)

        self.template_hint = QLabel()
        self.template_hint.setObjectName("hint")
        self.template_hint.setWordWrap(True)
        form.addRow(self.template_hint)

        self.template_box.currentIndexChanged.connect(
            self.update_template_hint
        )
        self.update_template_hint()

        form.addRow(section_label("СВОЙСТВА"))

        self.name = QLineEdit()
        self.internal_id = QLineEdit()

        self.description = QPlainTextEdit()
        self.description.setMaximumHeight(90)

        self.summon_enabled = QCheckBox("Создавать предмет-призыв")
        self.summon_enabled.setChecked(True)
        self.summon_enabled.setToolTip(
            "Предмет с ID «<ID босса>_summon» позволит призвать босса в игре "
            "и не даст призвать второго, пока первый жив."
        )

        self.summon_recipe_enabled = QCheckBox("Добавить рецепт призыва")
        self.summon_recipe_enabled.setToolTip(
            "TMC допишет рецепт в класс предмета-призыва: ингредиент, "
            "количество и станция."
        )

        self.summon_recipe_item = QComboBox()

        for label, code in BOSS_RECIPE_INGREDIENTS:
            self.summon_recipe_item.addItem(label, code)

        self.summon_recipe_count = QSpinBox()
        self.summon_recipe_count.setRange(1, 999)
        self.summon_recipe_count.setValue(
            DEFAULT_SUMMON_RECIPE["count"]
        )

        self.summon_recipe_station = QComboBox()

        for label, code in BOSS_RECIPE_STATIONS:
            self.summon_recipe_station.addItem(label, code)

        self.music = QComboBox()

        for label, code in BOSS_MUSIC_OPTIONS:
            self.music.addItem(label, code)

        form.addRow("Название", self.name)
        form.addRow("Внутренний ID", self.internal_id)
        form.addRow("Описание", self.description)
        form.addRow("При экспорте", self.summon_enabled)
        form.addRow("Рецепт", self.summon_recipe_enabled)
        form.addRow("Ингредиент", self.summon_recipe_item)
        form.addRow("Количество", self.summon_recipe_count)
        form.addRow("Станция", self.summon_recipe_station)
        form.addRow("Музыка", self.music)

        recipe_note = QLabel(
            "Рецепт необязателен: без него предмет-призыв существует, но "
            "получить его в игре можно только дропом или своим рецептом."
        )
        recipe_note.setObjectName("hint")
        recipe_note.setWordWrap(True)
        form.addRow(recipe_note)

        self.summon_enabled.toggled.connect(self.update_summon_fields)
        self.summon_recipe_enabled.toggled.connect(
            self.update_summon_fields
        )
        self.update_summon_fields()

        note = QLabel(
            "Если не выбирать музыку, tModLoader использует обычную "
            "боевую тему. Ванильные темы подставляются без музыканта "
            "в моде."
        )
        note.setObjectName("hint")
        note.setWordWrap(True)
        form.addRow(note)

        form.addRow(section_label("ХАРАКТЕРИСТИКИ"))

        self.life_max = QSpinBox()
        self.life_max.setRange(1, 10_000_000)
        self.life_max.setSingleStep(100)
        self.life_max.setValue(DEFAULT_BOSS_STATS["life_max"])

        self.damage = QSpinBox()
        self.damage.setRange(0, 100_000)
        self.damage.setValue(DEFAULT_BOSS_STATS["damage"])

        self.defense = QSpinBox()
        self.defense.setRange(0, 10_000)
        self.defense.setValue(DEFAULT_BOSS_STATS["defense"])

        self.knockback_resist = QDoubleSpinBox()
        self.knockback_resist.setRange(0.0, 1.0)
        self.knockback_resist.setDecimals(2)
        self.knockback_resist.setSingleStep(0.05)
        self.knockback_resist.setValue(
            DEFAULT_BOSS_STATS["knockback_resist"]
        )

        self.width = QSpinBox()
        self.width.setRange(8, 1024)
        self.width.setValue(DEFAULT_BOSS_STATS["width"])

        self.height = QSpinBox()
        self.height.setRange(8, 1024)
        self.height.setValue(DEFAULT_BOSS_STATS["height"])

        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.1, 10.0)
        self.scale.setDecimals(2)
        self.scale.setSingleStep(0.05)
        self.scale.setValue(DEFAULT_BOSS_STATS["scale"])

        self.value = QSpinBox()
        self.value.setRange(0, 2_000_000_000)
        self.value.setSingleStep(1000)
        self.value.setValue(DEFAULT_BOSS_STATS["value_copper"])

        form.addRow("Максимум здоровья", self.life_max)
        form.addRow("Урон", self.damage)
        form.addRow("Защита", self.defense)
        form.addRow(
            "Сопротивление отбрасыванию (0–1)", self.knockback_resist
        )
        form.addRow("Ширина хитбокса", self.width)
        form.addRow("Высота хитбокса", self.height)
        form.addRow("Визуальный масштаб", self.scale)
        form.addRow("Награда (медные монеты)", self.value)

        note = QLabel(
            "Хитбокс и масштаб независимы: масштаб меняет только картинку. "
            "Сопротивление 0 — босса нельзя оттолкнуть, 1 — как NPC."
        )
        note.setObjectName("hint")
        note.setWordWrap(True)
        form.addRow(note)

        form.addRow(section_label("СЛОЖНОСТЬ"))

        self.expert_life_percent = QSpinBox()
        self.expert_life_percent.setRange(50, 1000)
        self.expert_life_percent.setSingleStep(5)
        self.expert_life_percent.setSuffix(" %")
        self.expert_life_percent.setValue(
            DEFAULT_BOSS_STATS["expert_life_percent"]
        )

        self.master_life_percent = QSpinBox()
        self.master_life_percent.setRange(50, 1000)
        self.master_life_percent.setSingleStep(5)
        self.master_life_percent.setSuffix(" %")
        self.master_life_percent.setValue(
            DEFAULT_BOSS_STATS["master_life_percent"]
        )

        form.addRow("Здоровье в эксперте", self.expert_life_percent)
        form.addRow("Здоровье в мастере", self.master_life_percent)

        note = QLabel(
            "100% — столько же здоровья, сколько в обычном мире. "
            "Terraria обычно даёт боссам больше здоровья на высоких "
            "сложностях: 100–200% — привычный диапазон."
        )
        note.setObjectName("hint")
        note.setWordWrap(True)
        form.addRow(note)

        form.addRow(section_label("ПОВЕДЕНИЕ"))

        self.ai = QComboBox()

        for label, code in BOSS_AI_OPTIONS:
            self.ai.addItem(label, code)

        self.movement_speed = QDoubleSpinBox()
        self.movement_speed.setRange(0.1, 30.0)
        self.movement_speed.setDecimals(2)
        self.movement_speed.setSingleStep(0.5)
        self.movement_speed.setValue(
            DEFAULT_BOSS_STATS["movement_speed"]
        )

        self.hover_height = QSpinBox()
        self.hover_height.setRange(0, 3000)
        self.hover_height.setSingleStep(10)
        self.hover_height.setSuffix(" px")
        self.hover_height.setValue(DEFAULT_BOSS_STATS["hover_height"])

        self.jump_force = QDoubleSpinBox()
        self.jump_force.setRange(1.0, 30.0)
        self.jump_force.setDecimals(2)
        self.jump_force.setSingleStep(0.5)
        self.jump_force.setValue(DEFAULT_BOSS_STATS["jump_force"])

        self.orbit_radius = QSpinBox()
        self.orbit_radius.setRange(40, 1500)
        self.orbit_radius.setSingleStep(10)
        self.orbit_radius.setSuffix(" px")
        self.orbit_radius.setValue(DEFAULT_BOSS_STATS["orbit_radius"])

        self.orbit_speed = QDoubleSpinBox()
        self.orbit_speed.setRange(0.1, 12.0)
        self.orbit_speed.setDecimals(2)
        self.orbit_speed.setSingleStep(0.1)
        self.orbit_speed.setSuffix(" °/тик")
        self.orbit_speed.setValue(DEFAULT_BOSS_STATS["orbit_speed"])

        self.teleport_interval = QSpinBox()
        self.teleport_interval.setRange(30, 36_000)
        self.teleport_interval.setSingleStep(30)
        self.teleport_interval.setSuffix(" тик.")
        self.teleport_interval.setValue(
            DEFAULT_BOSS_STATS["teleport_interval"]
        )

        self.teleport_range = QSpinBox()
        self.teleport_range.setRange(60, 1200)
        self.teleport_range.setSingleStep(20)
        self.teleport_range.setSuffix(" px")
        self.teleport_range.setValue(DEFAULT_BOSS_STATS["teleport_range"])

        self.charge_speed = QDoubleSpinBox()
        self.charge_speed.setRange(2.0, 40.0)
        self.charge_speed.setDecimals(2)
        self.charge_speed.setSingleStep(1.0)
        self.charge_speed.setValue(DEFAULT_BOSS_STATS["charge_speed"])

        self.charge_pause = QSpinBox()
        self.charge_pause.setRange(10, 1200)
        self.charge_pause.setSingleStep(10)
        self.charge_pause.setSuffix(" тик.")
        self.charge_pause.setValue(DEFAULT_BOSS_STATS["charge_pause"])

        self.ai_label = QLabel()
        self.ai_label.setObjectName("hint")
        self.ai_label.setWordWrap(True)

        form.addRow("Поведение", self.ai)
        form.addRow("Скорость движения", self.movement_speed)
        form.addRow("Высота парения", self.hover_height)
        form.addRow("Сила прыжка", self.jump_force)
        form.addRow("Радиус орбиты", self.orbit_radius)
        form.addRow("Скорость орбиты", self.orbit_speed)
        form.addRow("Интервал телепорта", self.teleport_interval)
        form.addRow("Разброс телепорта", self.teleport_range)
        form.addRow("Скорость броска", self.charge_speed)
        form.addRow("Пауза между бросками", self.charge_pause)
        form.addRow(self.ai_label)

        note = QLabel(
            "Скорость задаётся в пикселях за игровой тик: 6 — умеренно "
            "быстрый босс, 10 и выше — очень резкий. Для прыжков скорость "
            "задаёт разбег по земле, а сила прыжка — высоту отскока."
        )
        note.setObjectName("hint")
        note.setWordWrap(True)
        form.addRow(note)

        self.ai.currentIndexChanged.connect(self.update_ai_fields)
        self.update_ai_fields()

        self.tabs.addTab(tab, "Основное")

    def build_attacks_tab(self):
        tab, form = make_scroll_form_tab(760)
        self.attacks_form = form

        self.dash_enabled = QCheckBox(
            "Периодически делает рывок к игроку"
        )
        self.dash_enabled.setToolTip(
            "Рывок включает анимацию состояния «Атака» и временно "
            "подменяет обычное движение."
        )

        self.dash_interval = QSpinBox()
        self.dash_interval.setRange(30, 36_000)
        self.dash_interval.setSingleStep(30)
        self.dash_interval.setSuffix(" тик.")
        self.dash_interval.setValue(DEFAULT_DASH["interval_ticks"])

        self.dash_speed = QDoubleSpinBox()
        self.dash_speed.setRange(1.0, 60.0)
        self.dash_speed.setDecimals(2)
        self.dash_speed.setSingleStep(1.0)
        self.dash_speed.setValue(DEFAULT_DASH["speed"])

        self.dash_duration = QSpinBox()
        self.dash_duration.setRange(5, 600)
        self.dash_duration.setSingleStep(5)
        self.dash_duration.setSuffix(" тик.")
        self.dash_duration.setValue(DEFAULT_DASH["duration_ticks"])

        self.dash_expert_only = QCheckBox("Только в эксперте и мастере")

        form.addRow(section_label("РЫВОК"))
        form.addRow(self.dash_enabled)
        form.addRow("Интервал", self.dash_interval)
        form.addRow("Скорость", self.dash_speed)
        form.addRow("Длительность", self.dash_duration)
        form.addRow(self.dash_expert_only)

        self.shoot_enabled = QCheckBox(
            "Периодически стреляет снарядами"
        )
        self.shoot_enabled.setToolTip(
            "Снаряды летят по выбранному узору. Выстрел включает "
            "анимацию состояния «Атака»."
        )

        self.shoot_interval = QSpinBox()
        self.shoot_interval.setRange(30, 36_000)
        self.shoot_interval.setSingleStep(30)
        self.shoot_interval.setSuffix(" тик.")
        self.shoot_interval.setValue(DEFAULT_SHOOT["interval_ticks"])

        self.shoot_pattern = QComboBox()

        for label, code in BOSS_SHOOT_PATTERNS:
            self.shoot_pattern.addItem(label, code)

        self.shoot_source = QComboBox()

        for label, code in BOSS_SHOOT_SOURCES:
            self.shoot_source.addItem(label, code)

        self.shoot_projectile = QComboBox()

        for label, code in BOSS_PROJECTILE_OPTIONS:
            self.shoot_projectile.addItem(label, code)

        self.shoot_color_button = QPushButton()
        self.shoot_color_button.clicked.connect(self.choose_shoot_color)

        self.shoot_radius = QSpinBox()
        self.shoot_radius.setRange(4, 64)
        self.shoot_radius.setSuffix(" px")
        self.shoot_radius.setValue(DEFAULT_SHOOT["radius"])

        self.shoot_homing = QDoubleSpinBox()
        self.shoot_homing.setRange(0.0, 1.0)
        self.shoot_homing.setDecimals(2)
        self.shoot_homing.setSingleStep(0.02)
        self.shoot_homing.setValue(DEFAULT_SHOOT["homing"])

        self.shoot_pierce = QSpinBox()
        self.shoot_pierce.setRange(1, 10)
        self.shoot_pierce.setValue(DEFAULT_SHOOT["pierce"])

        self.shoot_lifetime = QSpinBox()
        self.shoot_lifetime.setRange(60, 1800)
        self.shoot_lifetime.setSingleStep(30)
        self.shoot_lifetime.setSuffix(" тик.")
        self.shoot_lifetime.setValue(DEFAULT_SHOOT["lifetime_ticks"])

        self.shoot_spiral_step = QDoubleSpinBox()
        self.shoot_spiral_step.setRange(1.0, 90.0)
        self.shoot_spiral_step.setDecimals(0)
        self.shoot_spiral_step.setSingleStep(1.0)
        self.shoot_spiral_step.setSuffix("°")
        self.shoot_spiral_step.setValue(DEFAULT_SHOOT["spiral_step"])

        self.shoot_damage = QSpinBox()
        self.shoot_damage.setRange(0, 100_000)
        self.shoot_damage.setValue(DEFAULT_SHOOT["damage"])

        self.shoot_count = QSpinBox()
        self.shoot_count.setRange(1, 20)
        self.shoot_count.setValue(DEFAULT_SHOOT["count"])

        self.shoot_spread = QDoubleSpinBox()
        self.shoot_spread.setRange(0.0, 180.0)
        self.shoot_spread.setDecimals(1)
        self.shoot_spread.setSingleStep(2.0)
        self.shoot_spread.setSuffix("°")
        self.shoot_spread.setValue(DEFAULT_SHOOT["spread_degrees"])

        self.shoot_speed = QDoubleSpinBox()
        self.shoot_speed.setRange(1.0, 60.0)
        self.shoot_speed.setDecimals(2)
        self.shoot_speed.setSingleStep(1.0)
        self.shoot_speed.setValue(DEFAULT_SHOOT["speed"])

        self.shoot_expert_only = QCheckBox("Только в эксперте и мастере")

        self.adds_enabled = QCheckBox(
            "Периодически призывает мобов"
        )
        self.adds_enabled.setToolTip(
            "Босс зовёт на помощь ванильных мобов. Призыв тоже включает "
            "анимацию состояния «Атака»."
        )

        self.adds_interval = QSpinBox()
        self.adds_interval.setRange(60, 36_000)
        self.adds_interval.setSingleStep(30)
        self.adds_interval.setSuffix(" тик.")
        self.adds_interval.setValue(DEFAULT_ADD_ATTACK["interval_ticks"])

        self.adds_npc = QComboBox()

        for label, code in BOSS_SUMMON_NPC_OPTIONS:
            self.adds_npc.addItem(label, code)

        self.adds_count = QSpinBox()
        self.adds_count.setRange(1, 10)
        self.adds_count.setValue(DEFAULT_ADD_ATTACK["count"])

        self.adds_expert_only = QCheckBox("Только в эксперте и мастере")

        form.addRow(section_label("СНАРЯДЫ"))
        form.addRow(self.shoot_enabled)
        form.addRow("Интервал", self.shoot_interval)
        form.addRow("Узор", self.shoot_pattern)
        form.addRow("Источник", self.shoot_source)
        form.addRow("Ванильный снаряд", self.shoot_projectile)
        form.addRow("Цвет своего снаряда", self.shoot_color_button)
        form.addRow("Радиус своего снаряда", self.shoot_radius)
        form.addRow("Самонаведение (0–1)", self.shoot_homing)
        form.addRow("Пробивание", self.shoot_pierce)
        form.addRow("Время жизни", self.shoot_lifetime)
        form.addRow("Шаг спирали", self.shoot_spiral_step)
        form.addRow("Урон", self.shoot_damage)
        form.addRow("Количество", self.shoot_count)
        form.addRow("Разброс", self.shoot_spread)
        form.addRow("Скорость", self.shoot_speed)
        form.addRow(self.shoot_expert_only)

        form.addRow(section_label("ПРИЗЫВ МОБОВ"))
        form.addRow(self.adds_enabled)
        form.addRow("Интервал", self.adds_interval)
        form.addRow("Моб", self.adds_npc)
        form.addRow("Количество за призыв", self.adds_count)
        form.addRow(self.adds_expert_only)

        self.adds_note = QLabel()
        self.adds_note.setObjectName("hint")
        self.adds_note.setWordWrap(True)
        form.addRow(self.adds_note)

        self.attack_note = QLabel()
        self.attack_note.setObjectName("hint")
        self.attack_note.setWordWrap(True)
        form.addRow(self.attack_note)

        note = QLabel(
            "Интервал и длительность указаны в игровых тиках (60 в секунду). "
            "Веер стреляет в игрока с разбросом, круг — во все стороны, "
            "спираль поворачивает каждый залп на шаг спирали."
        )
        note.setObjectName("hint")
        note.setWordWrap(True)
        form.addRow(note)

        self.dash_enabled.toggled.connect(self.update_action_fields)
        self.shoot_enabled.toggled.connect(self.update_action_fields)
        self.adds_enabled.toggled.connect(self.update_action_fields)
        self.adds_npc.currentIndexChanged.connect(
            self.update_action_fields
        )
        self.adds_interval.valueChanged.connect(
            self.update_action_fields
        )
        self.adds_count.valueChanged.connect(self.update_action_fields)
        self.shoot_source.currentIndexChanged.connect(
            self.update_action_fields
        )
        self.shoot_pattern.currentIndexChanged.connect(
            self.update_action_fields
        )
        self.update_shoot_color_button()
        self.update_action_fields()

        self.tabs.addTab(tab, "Атаки")

    def build_defense_tab(self):
        tab, form = make_scroll_form_tab(760)

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(8)

        for index, (label, code) in enumerate(BOSS_BUFF_OPTIONS):
            box = QCheckBox(label)
            self.immunity_boxes[code] = box
            grid.addWidget(box, index // 3, index % 3)

        form.addRow("Иммунитеты", grid_host)

        self.contact_enabled = QCheckBox(
            "Накладывать дебафф при касании"
        )

        self.contact_buff = QComboBox()

        for label, code in BOSS_BUFF_OPTIONS:
            self.contact_buff.addItem(label, code)

        self.contact_duration = QSpinBox()
        self.contact_duration.setRange(1, 36_000)
        self.contact_duration.setSingleStep(30)
        self.contact_duration.setSuffix(" тик.")
        self.contact_duration.setValue(
            DEFAULT_CONTACT_BUFF["duration_ticks"]
        )

        form.addRow(self.contact_enabled)
        form.addRow("Дебафф", self.contact_buff)
        form.addRow("Длительность", self.contact_duration)

        note = QLabel(
            "Иммунитеты попадают в SetDefaults, а дебафф при касании — "
            "в OnHitPlayer. Иммунитет не мешает боссу получать урон."
        )
        note.setObjectName("hint")
        note.setWordWrap(True)
        form.addRow(note)

        self.contact_enabled.toggled.connect(
            self.update_contact_fields
        )
        self.update_contact_fields()

        self.tabs.addTab(tab, "Защита")

    def build_phases_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        hint = QLabel(
            "Фаза включается, когда у босса остаётся указанный процент "
            "здоровья. Первая фаза всегда 100%. Скорость и атаки — "
            "множители к базовым значениям: ×1.5 значит в полтора раза "
            "быстрее и чаще."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.phase_table = QTableWidget(0, 4)
        self.phase_table.setHorizontalHeaderLabels([
            "Фаза",
            "Порог HP",
            "Скорость",
            "Атаки",
        ])
        self.phase_table.verticalHeader().setVisible(False)
        self.phase_table.verticalHeader().setDefaultSectionSize(40)
        self.phase_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.phase_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.phase_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.phase_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )

        for column in (1, 2, 3):
            self.phase_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

        layout.addWidget(self.phase_table, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        self.add_phase_btn = QPushButton("+ Добавить фазу")
        self.add_phase_btn.clicked.connect(self.add_phase_row)

        self.remove_phase_btn = QPushButton("Удалить фазу")
        self.remove_phase_btn.clicked.connect(self.remove_phase_row)

        self.reset_phases_btn = QPushButton("Сбросить к одной фазе")
        self.reset_phases_btn.clicked.connect(self.reset_phases)

        buttons.addWidget(self.add_phase_btn)
        buttons.addWidget(self.remove_phase_btn)
        buttons.addWidget(self.reset_phases_btn)
        buttons.addStretch(1)

        layout.addLayout(buttons)

        self.phase_hint = QLabel()
        self.phase_hint.setObjectName("hint")
        self.phase_hint.setWordWrap(True)

        self.phase_effect = QCheckBox(
            "Вспышка и короткая неуязвимость при смене фазы"
        )
        self.phase_effect.setChecked(True)
        self.phase_effect.setToolTip(
            "При переходе на новую фазу босс взрывается пылью и на "
            "полсекунды перестаёт получать урон."
        )

        layout.addWidget(self.phase_effect)
        layout.addWidget(self.phase_hint)

        self.tabs.addTab(tab, "Фазы")

    def build_loot_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        hint = QLabel(
            "Дроп собирается из предметов проекта. Шанс указан в процентах "
            "на один труп, количество — в штуках. 100% — гарантированный дроп. "
            "Галочка «Эксперт» оставляет предмет только для эксперта и мастера."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.loot_table = QTableWidget(0, 5)
        self.loot_table.setHorizontalHeaderLabels([
            "Предмет",
            "Шанс",
            "Мин.",
            "Макс.",
            "Эксперт",
        ])
        self.loot_table.verticalHeader().setVisible(False)
        self.loot_table.verticalHeader().setDefaultSectionSize(40)
        self.loot_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.loot_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.loot_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.loot_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )

        for column in (1, 2, 3, 4):
            self.loot_table.horizontalHeader().setSectionResizeMode(
                column, QHeaderView.ResizeMode.ResizeToContents
            )

        layout.addWidget(self.loot_table, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)

        self.add_loot_btn = QPushButton("+ Добавить предмет")
        self.add_loot_btn.clicked.connect(self.add_loot_row)

        self.remove_loot_btn = QPushButton("Удалить строку")
        self.remove_loot_btn.clicked.connect(self.remove_loot_row)

        buttons.addWidget(self.add_loot_btn)
        buttons.addWidget(self.remove_loot_btn)
        buttons.addStretch(1)

        layout.addLayout(buttons)

        self.loot_hint = QLabel()
        self.loot_hint.setObjectName("hint")
        self.loot_hint.setWordWrap(True)
        layout.addWidget(self.loot_hint)

        self.bag_enabled = QCheckBox(
            "В эксперте и мастере босс выпадает мешком с лутом"
        )
        self.bag_enabled.setToolTip(
            "TMC создаст отдельный предмет-мешок: его класс, иконку и "
            "локализацию."
        )
        layout.addWidget(self.bag_enabled)

        self.bag_hint = QLabel(
            "Мешок повторяет поведение ванильных сумок боссов: в обычном "
            "мире добыча выпадает напрямую, а в эксперте и мастере — "
            "одним мешком. Внутри лежат все предметы таблицы, включая "
            "те, что отмечены галочкой «Эксперт»."
        )
        self.bag_hint.setObjectName("hint")
        self.bag_hint.setWordWrap(True)
        layout.addWidget(self.bag_hint)

        self.tabs.addTab(tab, "Дроп")

    def build_script_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.script_editor = ScriptEditor(variant="boss")
        layout.addWidget(self.script_editor)

        self.tabs.addTab(tab, "Скрипт")

    def build_sprite_tab(self):
        tab = QWidget()
        self.sprite_tab = tab
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self.sprite_preview = QLabel()
        self.sprite_preview.setObjectName("cardSprite")
        self.sprite_preview.setFixedSize(260, 260)
        self.sprite_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)

        choose_button = QPushButton("Выбрать изображение…")
        choose_button.clicked.connect(self.choose_sprite)

        fit_button = QPushButton("Подогнать хитбокс под спрайт")
        fit_button.clicked.connect(self.fit_hitbox_to_sprite)

        fit_art_button = QPushButton("Подогнать по рисунку")
        fit_art_button.setToolTip(
            "Берёт только непрозрачные пиксели: прозрачные поля холста "
            "не попадут в хитбокс."
        )
        fit_art_button.clicked.connect(self.fit_hitbox_to_art)

        self.sprite_info = QLabel()
        self.sprite_info.setObjectName("hint")
        self.sprite_info.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(
            self.sprite_preview, 0, Qt.AlignmentFlag.AlignHCenter
        )
        layout.addWidget(choose_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(fit_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(fit_art_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.sprite_info)
        layout.addStretch(1)

        self.tabs.addTab(tab, "Спрайт")

    def build_animation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        hint = QLabel(
            "У каждого состояния своя лента кадров. В игре босс "
            "переключает их по действию: покой, движение, атака и прыжок. "
            "Состояние без кадров берёт ленту движения."
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.animation_tabs = QTabWidget()
        layout.addWidget(self.animation_tabs, 1)

        for state, label in BOSS_ANIMATION_STATES:
            editor = AnimationEditor()
            editor.add_frame_requested.connect(
                lambda checked=False, target=editor: target.add_frame(
                    self.sprite
                )
            )
            self.animation_editors[state] = editor
            self.animation_tabs.addTab(editor, label)

        controls = QHBoxLayout()
        controls.setSpacing(10)

        copy_button = QPushButton(
            "Скопировать ленту во все состояния"
        )
        copy_button.setToolTip(
            "Удобно, когда у босса одна анимация: нарисуй её один раз "
            "и разложи по остальным состояниям."
        )
        copy_button.clicked.connect(self.copy_animation_to_all)

        self.animation_note = QLabel()
        self.animation_note.setObjectName("hint")
        self.animation_note.setWordWrap(True)

        controls.addWidget(copy_button)
        controls.addWidget(self.animation_note, 1)
        layout.addLayout(controls)

        self.tabs.addTab(tab, "Анимация")

    def copy_animation_to_all(self):
        """Дублирует ленту открытого состояния в остальные состояния."""

        index = self.animation_tabs.currentIndex()

        if not (0 <= index < len(BOSS_ANIMATION_STATES)):
            return

        state, label = BOSS_ANIMATION_STATES[index]
        source = self.animation_editors[state].frames

        if not source:
            self.animation_note.setText(
                f"В состоянии «{label}» нет кадров — копировать нечего."
            )
            return

        for other_state, editor in self.animation_editors.items():
            if other_state == state:
                continue

            editor.set_animation({
                "frames": [
                    {
                        "image": frame["image"].copy(),
                        "duration_ms": int(frame["duration_ms"]),
                    }
                    for frame in source
                ],
                "loop": bool(editor.loop),
            })

        self.animation_note.setText(
            f"Лента «{label}» ({len(source)} кадр.) скопирована "
            "в остальные состояния."
        )
        self.schedule_issue_check()

    def build_preview_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        controls = QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(QLabel("Состояние:"))

        self.preview_state = QComboBox()

        for state, label in BOSS_ANIMATION_STATES:
            self.preview_state.addItem(label, state)

        self.preview_state.currentIndexChanged.connect(
            self.update_preview_state
        )
        controls.addWidget(self.preview_state)
        controls.addStretch(1)

        self.preview = BossPreview(
            BOSS_AI_LABELS,
            BOSS_SHOOT_PATTERN_LABELS,
            BOSS_ANIMATION_STATES,
        )

        layout.addLayout(controls)
        layout.addWidget(self.preview, 1)

        note = QLabel(
            "Предпросмотр показывает, как босс будет выглядеть в бою: "
            "полоса здоровья с метками фаз, кадры анимации и сводка атак. "
            "Это только просмотр — на генерацию он не влияет."
        )
        note.setObjectName("hint")
        note.setWordWrap(True)
        layout.addWidget(note)

        self.tabs.addTab(tab, "Предпросмотр")

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    def connect_change_signals(self):
        """Любое изменение в форме откладывает пересчёт замечаний."""

        for widget in self.findChildren(QLineEdit):
            widget.textChanged.connect(self.schedule_issue_check)

        for widget in self.findChildren(QPlainTextEdit):
            widget.textChanged.connect(self.schedule_issue_check)

        for widget in self.findChildren(QSpinBox):
            widget.valueChanged.connect(self.schedule_issue_check)

        for widget in self.findChildren(QDoubleSpinBox):
            widget.valueChanged.connect(self.schedule_issue_check)

        for widget in self.findChildren(QComboBox):
            widget.currentIndexChanged.connect(self.schedule_issue_check)

        for widget in self.findChildren(QCheckBox):
            widget.toggled.connect(self.schedule_issue_check)

    def set_item_choices(self, items):
        """Запоминает предметы проекта для таблицы дропа."""

        self.item_choices = [
            (key, obj.get("data", {}).get("name", key))
            for key, obj in items.items()
        ]

        self.add_loot_btn.setEnabled(bool(self.item_choices))

        if self.item_choices:
            self.loot_hint.setText(
                "Доступно предметов: "
                f"{len(self.item_choices)}. Список берётся из категории "
                "«Предметы»."
            )
        else:
            self.loot_hint.setText(
                "В проекте пока нет предметов: создай их в категории "
                "«Предметы», чтобы добавить дроп."
            )

    def set_boss(self, data, sprite, animations=None):
        """Показывает данные босса в форме."""

        raw = data if isinstance(data, dict) else {}

        # Анимации приходят отдельным аргументом и живут в редакторах
        # кадров. В копию данных их кладём только при сохранении: QImage
        # нельзя deepcopy, а форма должна переживать переключение боссов.
        if animations is None:
            animations = normalize_boss_animations(raw)

        self.loading = True
        self._data = copy.deepcopy({
            key: value
            for key, value in raw.items()
            if key not in ("animations", "animation")
        })

        self.name.setText(self._data.get("name", "Новый босс"))
        self.internal_id.setText(self._data.get("internal_id", ""))
        self.description.setPlainText(
            self._data.get("description", "")
        )

        summon = _as_dict(self._data.get("summon"))
        self.summon_enabled.setChecked(
            bool(summon.get("enabled", True))
        )

        recipe = _as_dict(summon.get("recipe"))
        self.summon_recipe_enabled.setChecked(
            bool(recipe.get("enabled", DEFAULT_SUMMON_RECIPE["enabled"]))
        )

        recipe_index = self.summon_recipe_item.findData(
            recipe.get("item", DEFAULT_SUMMON_RECIPE["item"])
        )
        self.summon_recipe_item.setCurrentIndex(max(0, recipe_index))
        self.summon_recipe_count.setValue(
            _clamped_int(
                recipe.get("count"),
                DEFAULT_SUMMON_RECIPE["count"],
                1,
                999,
            )
        )
        station_index = self.summon_recipe_station.findData(
            recipe.get("station", DEFAULT_SUMMON_RECIPE["station"])
        )
        self.summon_recipe_station.setCurrentIndex(max(0, station_index))
        self.update_summon_fields()

        music_index = self.music.findData(
            self._data.get("music", "")
        )
        self.music.setCurrentIndex(max(0, music_index))

        stats = _as_dict(self._data.get("stats"))

        self.life_max.setValue(
            _clamped_int(
                stats.get("life_max"),
                DEFAULT_BOSS_STATS["life_max"],
                1,
                10_000_000,
            )
        )
        self.damage.setValue(
            _clamped_int(
                stats.get("damage"), DEFAULT_BOSS_STATS["damage"], 0, 100_000
            )
        )
        self.defense.setValue(
            _clamped_int(
                stats.get("defense"),
                DEFAULT_BOSS_STATS["defense"],
                0,
                10_000,
            )
        )
        self.knockback_resist.setValue(
            _clamped_float(
                stats.get("knockback_resist"),
                DEFAULT_BOSS_STATS["knockback_resist"],
                0.0,
                1.0,
            )
        )
        self.width.setValue(
            _clamped_int(stats.get("width"), DEFAULT_BOSS_STATS["width"], 8, 1024)
        )
        self.height.setValue(
            _clamped_int(
                stats.get("height"), DEFAULT_BOSS_STATS["height"], 8, 1024
            )
        )
        self.scale.setValue(
            _clamped_float(
                stats.get("scale"), DEFAULT_BOSS_STATS["scale"], 0.1, 10.0
            )
        )
        self.value.setValue(
            _clamped_int(
                stats.get("value_copper"),
                DEFAULT_BOSS_STATS["value_copper"],
                0,
                2_000_000_000,
            )
        )

        ai_code = stats.get("ai", DEFAULT_BOSS_STATS["ai"])
        ai_index = self.ai.findData(ai_code)
        self.ai.setCurrentIndex(max(0, ai_index))

        self.movement_speed.setValue(
            _clamped_float(
                stats.get("movement_speed"),
                DEFAULT_BOSS_STATS["movement_speed"],
                0.1,
                30.0,
            )
        )
        self.hover_height.setValue(
            _clamped_int(
                stats.get("hover_height"),
                DEFAULT_BOSS_STATS["hover_height"],
                0,
                3000,
            )
        )
        self.jump_force.setValue(
            _clamped_float(
                stats.get("jump_force"),
                DEFAULT_BOSS_STATS["jump_force"],
                1.0,
                30.0,
            )
        )
        self.orbit_radius.setValue(
            _clamped_int(
                stats.get("orbit_radius"),
                DEFAULT_BOSS_STATS["orbit_radius"],
                40,
                1500,
            )
        )
        self.orbit_speed.setValue(
            _clamped_float(
                stats.get("orbit_speed"),
                DEFAULT_BOSS_STATS["orbit_speed"],
                0.1,
                12.0,
            )
        )
        self.teleport_interval.setValue(
            _clamped_int(
                stats.get("teleport_interval"),
                DEFAULT_BOSS_STATS["teleport_interval"],
                30,
                36_000,
            )
        )
        self.teleport_range.setValue(
            _clamped_int(
                stats.get("teleport_range"),
                DEFAULT_BOSS_STATS["teleport_range"],
                60,
                1200,
            )
        )
        self.charge_speed.setValue(
            _clamped_float(
                stats.get("charge_speed"),
                DEFAULT_BOSS_STATS["charge_speed"],
                2.0,
                40.0,
            )
        )
        self.charge_pause.setValue(
            _clamped_int(
                stats.get("charge_pause"),
                DEFAULT_BOSS_STATS["charge_pause"],
                10,
                1200,
            )
        )
        self.expert_life_percent.setValue(
            _clamped_int(
                stats.get("expert_life_percent"),
                DEFAULT_BOSS_STATS["expert_life_percent"],
                50,
                1000,
            )
        )
        self.master_life_percent.setValue(
            _clamped_int(
                stats.get("master_life_percent"),
                DEFAULT_BOSS_STATS["master_life_percent"],
                50,
                1000,
            )
        )

        actions = _as_dict(self._data.get("actions"))
        dash = _as_dict(actions.get("dash"))

        self.dash_enabled.setChecked(
            bool(dash.get("enabled", DEFAULT_DASH["enabled"]))
        )
        self.dash_interval.setValue(
            _clamped_int(
                dash.get("interval_ticks"),
                DEFAULT_DASH["interval_ticks"],
                30,
                36_000,
            )
        )
        self.dash_speed.setValue(
            _clamped_float(
                dash.get("speed"), DEFAULT_DASH["speed"], 1.0, 60.0
            )
        )
        self.dash_duration.setValue(
            _clamped_int(
                dash.get("duration_ticks"),
                DEFAULT_DASH["duration_ticks"],
                5,
                600,
            )
        )
        self.dash_expert_only.setChecked(
            bool(dash.get("expert_only", False))
        )

        shoot = _as_dict(actions.get("shoot"))

        self.shoot_enabled.setChecked(
            bool(shoot.get("enabled", DEFAULT_SHOOT["enabled"]))
        )
        self.shoot_interval.setValue(
            _clamped_int(
                shoot.get("interval_ticks"),
                DEFAULT_SHOOT["interval_ticks"],
                30,
                36_000,
            )
        )

        pattern_index = self.shoot_pattern.findData(
            shoot.get("pattern", DEFAULT_SHOOT["pattern"])
        )
        self.shoot_pattern.setCurrentIndex(max(0, pattern_index))

        source_index = self.shoot_source.findData(
            shoot.get("source", DEFAULT_SHOOT["source"])
        )
        self.shoot_source.setCurrentIndex(max(0, source_index))

        projectile_index = self.shoot_projectile.findData(
            shoot.get("projectile", DEFAULT_SHOOT["projectile"])
        )
        self.shoot_projectile.setCurrentIndex(max(0, projectile_index))

        color = QColor(
            str(shoot.get("color") or DEFAULT_SHOOT["color"])
        )

        if not color.isValid():
            color = QColor(DEFAULT_SHOOT["color"])

        self.shoot_color = color
        self.update_shoot_color_button()

        self.shoot_radius.setValue(
            _clamped_int(
                shoot.get("radius"), DEFAULT_SHOOT["radius"], 4, 64
            )
        )
        self.shoot_homing.setValue(
            _clamped_float(
                shoot.get("homing"), DEFAULT_SHOOT["homing"], 0.0, 1.0
            )
        )
        self.shoot_pierce.setValue(
            _clamped_int(
                shoot.get("pierce"), DEFAULT_SHOOT["pierce"], 1, 10
            )
        )
        self.shoot_lifetime.setValue(
            _clamped_int(
                shoot.get("lifetime_ticks"),
                DEFAULT_SHOOT["lifetime_ticks"],
                60,
                1800,
            )
        )
        self.shoot_spiral_step.setValue(
            _clamped_float(
                shoot.get("spiral_step"),
                DEFAULT_SHOOT["spiral_step"],
                1.0,
                90.0,
            )
        )
        self.shoot_damage.setValue(
            _clamped_int(
                shoot.get("damage"), DEFAULT_SHOOT["damage"], 0, 100_000
            )
        )
        self.shoot_count.setValue(
            _clamped_int(shoot.get("count"), DEFAULT_SHOOT["count"], 1, 20)
        )
        self.shoot_spread.setValue(
            _clamped_float(
                shoot.get("spread_degrees"),
                DEFAULT_SHOOT["spread_degrees"],
                0.0,
                180.0,
            )
        )
        self.shoot_speed.setValue(
            _clamped_float(
                shoot.get("speed"), DEFAULT_SHOOT["speed"], 1.0, 60.0
            )
        )
        self.shoot_expert_only.setChecked(
            bool(shoot.get("expert_only", False))
        )

        adds = _as_dict(actions.get("summon"))

        self.adds_enabled.setChecked(
            bool(adds.get("enabled", DEFAULT_ADD_ATTACK["enabled"]))
        )
        self.adds_interval.setValue(
            _clamped_int(
                adds.get("interval_ticks"),
                DEFAULT_ADD_ATTACK["interval_ticks"],
                60,
                36_000,
            )
        )

        npc_index = self.adds_npc.findData(
            normalize_adds_npc(
                adds.get("npc", DEFAULT_ADD_ATTACK["npc"])
            )
        )
        self.adds_npc.setCurrentIndex(max(0, npc_index))
        self.adds_count.setValue(
            _clamped_int(
                adds.get("count"), DEFAULT_ADD_ATTACK["count"], 1, 10
            )
        )
        self.adds_expert_only.setChecked(
            bool(adds.get("expert_only", False))
        )

        defense = _as_dict(self._data.get("defense"))
        immunities = _as_list(defense.get("immunities"))

        for code, box in self.immunity_boxes.items():
            box.setChecked(code in immunities)

        contact = _as_dict(defense.get("contact_buff"))

        self.contact_enabled.setChecked(
            bool(contact.get("enabled", DEFAULT_CONTACT_BUFF["enabled"]))
        )
        buff_index = self.contact_buff.findData(
            contact.get("buff", DEFAULT_CONTACT_BUFF["buff"])
        )
        self.contact_buff.setCurrentIndex(max(0, buff_index))
        self.contact_duration.setValue(
            _clamped_int(
                contact.get("duration_ticks"),
                DEFAULT_CONTACT_BUFF["duration_ticks"],
                1,
                36_000,
            )
        )

        self.set_phases(self._data.get("phases"))
        self.phase_effect.setChecked(
            bool(self._data.get("phase_effect", True))
        )
        self.set_loot(_as_list(self._data.get("loot")))
        self.bag_enabled.setChecked(
            bool(_as_dict(self._data.get("bag")).get("enabled", False))
        )
        self.script_editor.set_script(_as_dict(self._data.get("script")))

        normalized = {}

        for state, _label in BOSS_ANIMATION_STATES:
            animation = _as_dict(
                animations.get(state)
                if isinstance(animations, dict)
                else None
            )
            frames = _as_list(animation.get("frames"))
            normalized[state] = {
                "frames": list(frames),
                "loop": bool(
                    animation.get("loop", state != "attack")
                ),
            }

        animations = normalized

        for state, editor in self.animation_editors.items():
            editor.set_animation(
                animations.get(
                    state,
                    {"frames": [], "loop": state != "attack"},
                )
            )

        self.sprite = (
            sprite.copy() if isinstance(sprite, QImage) else QImage()
        )
        self.refresh_sprite()

        self.tabs.setEnabled(True)
        self.loading = False
        self.update_title()
        self.update_ai_fields()
        self.update_action_fields()
        self.update_contact_fields()
        self.refresh_issues()

    def collect_data(self):
        """Поля формы в формате данных босса, без анимаций и спрайта."""

        return {
            "schema_version": 3,
            "kind": "boss",
            "name": self.name.text().strip(),
            "internal_id": self.internal_id.text().strip(),
            "description": self.description.toPlainText().strip(),
            "music": self.music.currentData() or "",
            "stats": {
                "life_max": self.life_max.value(),
                "damage": self.damage.value(),
                "defense": self.defense.value(),
                "knockback_resist": self.knockback_resist.value(),
                "width": self.width.value(),
                "height": self.height.value(),
                "scale": self.scale.value(),
                "value_copper": self.value.value(),
                "ai": self.ai.currentData(),
                "movement_speed": self.movement_speed.value(),
                "hover_height": self.hover_height.value(),
                "jump_force": self.jump_force.value(),
                "orbit_radius": self.orbit_radius.value(),
                "orbit_speed": self.orbit_speed.value(),
                "teleport_interval": self.teleport_interval.value(),
                "teleport_range": self.teleport_range.value(),
                "charge_speed": self.charge_speed.value(),
                "charge_pause": self.charge_pause.value(),
                "expert_life_percent": self.expert_life_percent.value(),
                "master_life_percent": self.master_life_percent.value(),
            },
            "phases": self.get_phases(),
            "phase_effect": self.phase_effect.isChecked(),
            "actions": {
                "dash": {
                    "enabled": self.dash_enabled.isChecked(),
                    "interval_ticks": self.dash_interval.value(),
                    "speed": self.dash_speed.value(),
                    "duration_ticks": self.dash_duration.value(),
                    "expert_only": self.dash_expert_only.isChecked(),
                },
                "shoot": {
                    "enabled": self.shoot_enabled.isChecked(),
                    "interval_ticks": self.shoot_interval.value(),
                    "pattern": self.shoot_pattern.currentData(),
                    "source": self.shoot_source.currentData(),
                    "projectile": self.shoot_projectile.currentData(),
                    "damage": self.shoot_damage.value(),
                    "count": self.shoot_count.value(),
                    "spread_degrees": self.shoot_spread.value(),
                    "speed": self.shoot_speed.value(),
                    "spiral_step": self.shoot_spiral_step.value(),
                    "color": self.shoot_color.name(),
                    "radius": self.shoot_radius.value(),
                    "homing": self.shoot_homing.value(),
                    "pierce": self.shoot_pierce.value(),
                    "lifetime_ticks": self.shoot_lifetime.value(),
                    "expert_only": self.shoot_expert_only.isChecked(),
                },
                "summon": {
                    "enabled": self.adds_enabled.isChecked(),
                    "interval_ticks": self.adds_interval.value(),
                    "npc": self.adds_npc.currentData(),
                    "count": self.adds_count.value(),
                    "expert_only": self.adds_expert_only.isChecked(),
                },
            },
            "defense": {
                "immunities": [
                    code
                    for code, box in self.immunity_boxes.items()
                    if box.isChecked()
                ],
                "contact_buff": {
                    "enabled": self.contact_enabled.isChecked(),
                    "buff": self.contact_buff.currentData(),
                    "duration_ticks": self.contact_duration.value(),
                },
            },
            "loot": self.get_loot(),
            "bag": {
                "enabled": self.bag_enabled.isChecked(),
            },
            "summon": {
                "enabled": self.summon_enabled.isChecked(),
                "recipe": {
                    "enabled": self.summon_recipe_enabled.isChecked(),
                    "item": self.summon_recipe_item.currentData(),
                    "count": self.summon_recipe_count.value(),
                    "station": self.summon_recipe_station.currentData(),
                },
            },
            "script": self.script_editor.get_script(),
        }

    def animation_snapshot(self):
        """Анимации без копирования картинок — для проверок и предпросмотра."""

        return {
            state: {
                "frames": [
                    {
                        "image": frame["image"],
                        "duration_ms": int(frame["duration_ms"]),
                    }
                    for frame in editor.frames
                    if isinstance(frame.get("image"), QImage)
                ],
                "loop": bool(editor.loop),
            }
            for state, editor in self.animation_editors.items()
        }

    def get_boss(self):
        """Собирает данные из формы: (data, sprite, animations)."""

        data = copy.deepcopy(self._data)
        data.update(self.collect_data())

        animations = {
            state: editor.get_animation()
            for state, editor in self.animation_editors.items()
        }

        data["animations"] = animations
        data["animation"] = animations.get(
            "move", {"frames": [], "loop": True}
        )

        return data, self.sprite.copy(), animations

    def clear(self):
        """Сбрасывает форму, когда босс не выбран."""

        self.loading = True
        self._data = {}
        self.sprite = QImage()
        self.shoot_color = QColor(DEFAULT_SHOOT["color"])

        self.name.clear()
        self.internal_id.clear()
        self.description.clear()
        self.summon_enabled.setChecked(True)
        self.summon_recipe_enabled.setChecked(False)
        self.summon_recipe_item.setCurrentIndex(0)
        self.summon_recipe_count.setValue(
            DEFAULT_SUMMON_RECIPE["count"]
        )
        self.summon_recipe_station.setCurrentIndex(0)
        self.update_summon_fields()
        self.music.setCurrentIndex(0)

        self.life_max.setValue(DEFAULT_BOSS_STATS["life_max"])
        self.damage.setValue(DEFAULT_BOSS_STATS["damage"])
        self.defense.setValue(DEFAULT_BOSS_STATS["defense"])
        self.knockback_resist.setValue(
            DEFAULT_BOSS_STATS["knockback_resist"]
        )
        self.width.setValue(DEFAULT_BOSS_STATS["width"])
        self.height.setValue(DEFAULT_BOSS_STATS["height"])
        self.scale.setValue(DEFAULT_BOSS_STATS["scale"])
        self.value.setValue(DEFAULT_BOSS_STATS["value_copper"])
        self.ai.setCurrentIndex(0)
        self.movement_speed.setValue(
            DEFAULT_BOSS_STATS["movement_speed"]
        )
        self.hover_height.setValue(
            DEFAULT_BOSS_STATS["hover_height"]
        )
        self.jump_force.setValue(DEFAULT_BOSS_STATS["jump_force"])
        self.orbit_radius.setValue(DEFAULT_BOSS_STATS["orbit_radius"])
        self.orbit_speed.setValue(DEFAULT_BOSS_STATS["orbit_speed"])
        self.teleport_interval.setValue(
            DEFAULT_BOSS_STATS["teleport_interval"]
        )
        self.teleport_range.setValue(
            DEFAULT_BOSS_STATS["teleport_range"]
        )
        self.charge_speed.setValue(DEFAULT_BOSS_STATS["charge_speed"])
        self.charge_pause.setValue(DEFAULT_BOSS_STATS["charge_pause"])
        self.expert_life_percent.setValue(
            DEFAULT_BOSS_STATS["expert_life_percent"]
        )
        self.master_life_percent.setValue(
            DEFAULT_BOSS_STATS["master_life_percent"]
        )

        self.dash_enabled.setChecked(False)
        self.dash_interval.setValue(DEFAULT_DASH["interval_ticks"])
        self.dash_speed.setValue(DEFAULT_DASH["speed"])
        self.dash_duration.setValue(DEFAULT_DASH["duration_ticks"])
        self.dash_expert_only.setChecked(False)

        self.shoot_enabled.setChecked(False)
        self.shoot_interval.setValue(DEFAULT_SHOOT["interval_ticks"])
        self.shoot_pattern.setCurrentIndex(0)
        self.shoot_source.setCurrentIndex(0)
        self.shoot_projectile.setCurrentIndex(0)
        self.shoot_radius.setValue(DEFAULT_SHOOT["radius"])
        self.shoot_homing.setValue(DEFAULT_SHOOT["homing"])
        self.shoot_pierce.setValue(DEFAULT_SHOOT["pierce"])
        self.shoot_lifetime.setValue(DEFAULT_SHOOT["lifetime_ticks"])
        self.shoot_spiral_step.setValue(DEFAULT_SHOOT["spiral_step"])
        self.shoot_damage.setValue(DEFAULT_SHOOT["damage"])
        self.shoot_count.setValue(DEFAULT_SHOOT["count"])
        self.shoot_spread.setValue(DEFAULT_SHOOT["spread_degrees"])
        self.shoot_speed.setValue(DEFAULT_SHOOT["speed"])
        self.shoot_expert_only.setChecked(False)
        self.update_shoot_color_button()

        self.adds_enabled.setChecked(False)
        self.adds_interval.setValue(
            DEFAULT_ADD_ATTACK["interval_ticks"]
        )
        self.adds_npc.setCurrentIndex(0)
        self.adds_count.setValue(DEFAULT_ADD_ATTACK["count"])
        self.adds_expert_only.setChecked(False)

        for box in self.immunity_boxes.values():
            box.setChecked(False)

        self.contact_enabled.setChecked(False)
        self.contact_buff.setCurrentIndex(0)
        self.contact_duration.setValue(
            DEFAULT_CONTACT_BUFF["duration_ticks"]
        )

        self.set_phases(None)
        self.phase_effect.setChecked(True)
        self.set_loot([])
        self.bag_enabled.setChecked(False)
        self.script_editor.set_script(None)

        for state, editor in self.animation_editors.items():
            editor.set_animation({
                "frames": [],
                "loop": state != "attack",
            })

        self.animation_note.setText("")

        self.refresh_sprite()

        self.title_label.setText("Босс не выбран")
        self.tabs.setEnabled(False)
        self.loading = False
        self.update_ai_fields()
        self.update_action_fields()
        self.update_contact_fields()
        self.preview.set_data({}, QImage(), {})
        self.issues_label.setText("")

    def update_title(self):
        if self.loading:
            return

        name = self.name.text().strip() or "без названия"
        self.title_label.setText(f"Босс: {name}")

    def update_ai_fields(self, *_):
        """Показывает только те поля, которые нужны выбранному поведению."""

        ai = self.ai.currentData() or "hover"

        visible = {
            "hover": {"hover_height"},
            "jump": {"jump_force"},
            "orbit": {"orbit_radius", "orbit_speed"},
            "teleport": {"teleport_interval", "teleport_range",
                         "hover_height"},
            "charge": {"charge_speed", "charge_pause"},
        }.get(ai, set())

        rows = (
            ("hover_height", self.hover_height),
            ("jump_force", self.jump_force),
            ("orbit_radius", self.orbit_radius),
            ("orbit_speed", self.orbit_speed),
            ("teleport_interval", self.teleport_interval),
            ("teleport_range", self.teleport_range),
            ("charge_speed", self.charge_speed),
            ("charge_pause", self.charge_pause),
        )

        for key, widget in rows:
            _set_row_visible(self.general_form, widget, key in visible)

        self.ai_label.setText(
            BOSS_AI_DESCRIPTIONS.get(ai, BOSS_AI_DESCRIPTIONS["hover"])
        )

    def update_action_fields(self, *_):
        """Включает и скрывает поля у отмеченных атак."""

        dash = self.dash_enabled.isChecked()

        for widget in (
            self.dash_interval,
            self.dash_speed,
            self.dash_duration,
        ):
            widget.setEnabled(dash)

        self.dash_expert_only.setEnabled(dash)

        shoot = self.shoot_enabled.isChecked()

        for widget in (
            self.shoot_interval,
            self.shoot_pattern,
            self.shoot_source,
            self.shoot_damage,
            self.shoot_count,
            self.shoot_speed,
        ):
            widget.setEnabled(shoot)

        self.shoot_expert_only.setEnabled(shoot)

        custom = (self.shoot_source.currentData() or "vanilla") == "custom"

        _set_row_visible(
            self.attacks_form,
            self.shoot_projectile,
            shoot and not custom,
        )

        for widget in (
            self.shoot_color_button,
            self.shoot_radius,
            self.shoot_homing,
            self.shoot_pierce,
            self.shoot_lifetime,
        ):
            _set_row_visible(
                self.attacks_form, widget, shoot and custom
            )
            widget.setEnabled(shoot)

        pattern = self.shoot_pattern.currentData() or "fan"

        _set_row_visible(
            self.attacks_form,
            self.shoot_spiral_step,
            shoot and pattern == "spiral",
        )
        _set_row_visible(
            self.attacks_form,
            self.shoot_spread,
            shoot and pattern in ("fan", "spiral"),
        )

        self.shoot_spiral_step.setEnabled(shoot)
        self.shoot_spread.setEnabled(shoot)

        self.update_attack_note(pattern, custom)

        adds = self.adds_enabled.isChecked()

        for widget in (
            self.adds_interval,
            self.adds_npc,
            self.adds_count,
        ):
            widget.setEnabled(adds)

        self.adds_expert_only.setEnabled(adds)

        if adds:
            npc_label = self.adds_npc.currentText()
            interval = self.adds_interval.value() / 60.0
            count = self.adds_count.value()
            self.adds_note.setText(
                f"Каждые {interval:.1f} с босс призывает «{npc_label}» "
                f"×{count}. Мобы появляются вокруг босса и дальше живут "
                "сами. Не ставь слишком частый призыв: экран забьётся."
            )
        else:
            self.adds_note.setText(
                "Босс может звать на помощь ванильных мобов: выбери моба, "
                "интервал и количество. Это украшает бой и не даёт игроку "
                "спокойно сосредоточиться на боссе."
            )

    def update_attack_note(self, pattern, custom):
        if not self.shoot_enabled.isChecked():
            text = (
                "Рывок и выстрел используют готовые ванильные снаряды, "
                "поэтому отдельные текстуры для них не нужны."
            )
        elif custom:
            text = (
                "TMC создаст собственный класс снаряда и текстуру-орб: "
                "цвет, радиус, наведение и время жизни задаются здесь. "
                "Все выстрелы босса используют этот снаряд."
            )
        else:
            text = (
                "Снаряд берётся из ванильной игры: отдельные текстуры "
                "для него не нужны, он уже есть в Terraria."
            )

        if self.shoot_enabled.isChecked():
            if pattern == "fan":
                text += (
                    " Веер: количество снарядов летит в игрока с шагом "
                    "разброса."
                )
            elif pattern == "radial":
                text += (
                    " Круг: снаряды делят 360° поровну, поле разброса "
                    "не используется."
                )
            else:
                text += (
                    " Спираль: каждый залп поворачивается на шаг спирали, "
                    "разброс задаёт угол между снарядами в залпе."
                )

        self.attack_note.setText(text)

    def update_contact_fields(self, *_):
        enabled = self.contact_enabled.isChecked()
        self.contact_buff.setEnabled(enabled)
        self.contact_duration.setEnabled(enabled)

    def update_summon_fields(self, *_):
        """Показывает поля рецепта только у включённого призыва."""

        summon = self.summon_enabled.isChecked()
        recipe = summon and self.summon_recipe_enabled.isChecked()

        _set_row_visible(
            self.general_form, self.summon_recipe_enabled, summon
        )

        for widget in (
            self.summon_recipe_item,
            self.summon_recipe_count,
            self.summon_recipe_station,
        ):
            _set_row_visible(self.general_form, widget, recipe)
            widget.setEnabled(recipe)

    def update_template_hint(self, *_):
        index = self.template_box.currentIndex()

        if 0 <= index < len(BOSS_TEMPLATES):
            self.template_hint.setText(BOSS_TEMPLATES[index]["hint"])

    def update_shoot_color_button(self):
        color = self.shoot_color

        self.shoot_color_button.setText(color.name().upper())
        self.shoot_color_button.setStyleSheet(
            "QPushButton {"
            f"background-color: {color.name()};"
            "color: #12151a;"
            "font-weight: 700;"
            "border: 1px solid #12151a;"
            "}"
        )

    def choose_shoot_color(self):
        color = QColorDialog.getColor(
            self.shoot_color, self, "Цвет своего снаряда"
        )

        if not color.isValid():
            return

        self.shoot_color = color
        self.update_shoot_color_button()
        self.schedule_issue_check()

    def apply_template(self):
        """Заполняет характеристики и атаки выбранным шаблоном."""

        index = self.template_box.currentIndex()

        if not (0 <= index < len(BOSS_TEMPLATES)):
            return

        template = BOSS_TEMPLATES[index]

        self.apply_stats(template.get("stats", {}))
        self.apply_actions(template.get("actions", {}))

        if template.get("music"):
            music_index = self.music.findData(template["music"])
            self.music.setCurrentIndex(max(0, music_index))

        if "phases" in template:
            self.set_phases(template["phases"])

        self.update_ai_fields()
        self.update_action_fields()
        self.refresh_issues()

    def apply_stats(self, stats):
        widgets = {
            "life_max": self.life_max,
            "damage": self.damage,
            "defense": self.defense,
            "knockback_resist": self.knockback_resist,
            "width": self.width,
            "height": self.height,
            "scale": self.scale,
            "value_copper": self.value,
            "movement_speed": self.movement_speed,
            "hover_height": self.hover_height,
            "jump_force": self.jump_force,
            "orbit_radius": self.orbit_radius,
            "orbit_speed": self.orbit_speed,
            "teleport_interval": self.teleport_interval,
            "teleport_range": self.teleport_range,
            "charge_speed": self.charge_speed,
            "charge_pause": self.charge_pause,
            "expert_life_percent": self.expert_life_percent,
            "master_life_percent": self.master_life_percent,
        }

        for key, widget in widgets.items():
            if key not in stats:
                continue

            value = stats[key]

            if isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            else:
                widget.setValue(int(value))

        if "ai" in stats:
            ai_index = self.ai.findData(stats["ai"])
            self.ai.setCurrentIndex(max(0, ai_index))

    def apply_actions(self, actions):
        dash = _as_dict(actions.get("dash"))
        shoot = _as_dict(actions.get("shoot"))
        adds = _as_dict(actions.get("summon"))

        if dash:
            if "enabled" in dash:
                self.dash_enabled.setChecked(bool(dash["enabled"]))
            if "interval_ticks" in dash:
                self.dash_interval.setValue(int(dash["interval_ticks"]))
            if "speed" in dash:
                self.dash_speed.setValue(float(dash["speed"]))
            if "duration_ticks" in dash:
                self.dash_duration.setValue(int(dash["duration_ticks"]))
            if "expert_only" in dash:
                self.dash_expert_only.setChecked(bool(dash["expert_only"]))

        if shoot:
            if "enabled" in shoot:
                self.shoot_enabled.setChecked(bool(shoot["enabled"]))
            if "interval_ticks" in shoot:
                self.shoot_interval.setValue(int(shoot["interval_ticks"]))
            if "pattern" in shoot:
                pattern_index = self.shoot_pattern.findData(
                    shoot["pattern"]
                )
                self.shoot_pattern.setCurrentIndex(max(0, pattern_index))
            if "source" in shoot:
                source_index = self.shoot_source.findData(shoot["source"])
                self.shoot_source.setCurrentIndex(max(0, source_index))
            if "projectile" in shoot:
                projectile_index = self.shoot_projectile.findData(
                    shoot["projectile"]
                )
                self.shoot_projectile.setCurrentIndex(
                    max(0, projectile_index)
                )
            if "damage" in shoot:
                self.shoot_damage.setValue(int(shoot["damage"]))
            if "count" in shoot:
                self.shoot_count.setValue(int(shoot["count"]))
            if "spread_degrees" in shoot:
                self.shoot_spread.setValue(float(shoot["spread_degrees"]))
            if "speed" in shoot:
                self.shoot_speed.setValue(float(shoot["speed"]))
            if "spiral_step" in shoot:
                self.shoot_spiral_step.setValue(
                    float(shoot["spiral_step"])
                )
            if "radius" in shoot:
                self.shoot_radius.setValue(int(shoot["radius"]))
            if "homing" in shoot:
                self.shoot_homing.setValue(float(shoot["homing"]))
            if "pierce" in shoot:
                self.shoot_pierce.setValue(int(shoot["pierce"]))
            if "lifetime_ticks" in shoot:
                self.shoot_lifetime.setValue(int(shoot["lifetime_ticks"]))
            if "color" in shoot:
                color = QColor(str(shoot["color"]))

                if color.isValid():
                    self.shoot_color = color
                    self.update_shoot_color_button()
            if "expert_only" in shoot:
                self.shoot_expert_only.setChecked(
                    bool(shoot["expert_only"])
                )

        if adds:
            if "enabled" in adds:
                self.adds_enabled.setChecked(bool(adds["enabled"]))
            if "interval_ticks" in adds:
                self.adds_interval.setValue(int(adds["interval_ticks"]))
            if "npc" in adds:
                npc_index = self.adds_npc.findData(adds["npc"])
                self.adds_npc.setCurrentIndex(max(0, npc_index))
            if "count" in adds:
                self.adds_count.setValue(int(adds["count"]))
            if "expert_only" in adds:
                self.adds_expert_only.setChecked(
                    bool(adds["expert_only"])
                )

        self.update_action_fields()

    def focus_first_field(self):
        """Ставит курсор в название — удобно сразу после создания."""

        self.tabs.setCurrentIndex(0)
        self.name.setFocus()
        self.name.selectAll()

    def show_sprite_tab(self):
        """Открывает вкладку спрайта — так делает менеджер ресурсов."""

        self.tabs.setCurrentIndex(self.tabs.indexOf(self.sprite_tab))

    def on_tab_changed(self, _index):
        self.refresh_issues()

    def update_preview_state(self, _index):
        state = self.preview_state.currentData()

        if state:
            self.preview.set_state(state)

    # --------------------------------------------------------
    # CHECKS
    # --------------------------------------------------------

    def schedule_issue_check(self, *_):
        if self.loading:
            return

        self.issue_timer.start()

    def refresh_issues(self):
        """Считает замечания по текущей форме и обновляет предпросмотр."""

        if self.loading or not self.tabs.isEnabled():
            return

        data = self.collect_data()
        animations = self.animation_snapshot()

        self.script_editor.set_context(
            animated=boss_is_animated(animations),
            extra_members=boss_generated_members(data),
        )

        issues = check_boss(
            data.get("name") or data.get("internal_id") or "босс",
            data,
            self.sprite,
            animations,
        )

        if issues:
            first = issues[0]
            more = f" и ещё {len(issues) - 1}" if len(issues) > 1 else ""
            self.issues_label.setText(
                f"Замечаний: {len(issues)} — {first}{more}"
            )
            self.issues_label.setStyleSheet(
                f"color: {THEME['accent']}; padding: 4px 2px;"
            )
            self.issues_label.setToolTip("\n".join(issues))
        else:
            self.issues_label.setText("Проверка пройдена: замечаний нет.")
            self.issues_label.setStyleSheet(
                f"color: {THEME['muted']}; padding: 4px 2px;"
            )
            self.issues_label.setToolTip("")

        self.preview.set_data(data, self.sprite, animations)
        self.update_preview_state(self.preview_state.currentIndex())
        self.changed.emit(data, str(data.get("internal_id") or ""))

    # --------------------------------------------------------
    # LOOT
    # --------------------------------------------------------

    def add_loot_row(
        self,
        item_id=None,
        chance=0.25,
        min_amount=1,
        max_amount=1,
        expert=False,
    ):
        if not self.item_choices and not item_id:
            return

        row = self.loot_table.rowCount()
        self.loot_table.insertRow(row)

        combo = QComboBox()

        for key, name in self.item_choices:
            combo.addItem(name, key)

        if item_id:
            index = combo.findData(item_id)

            if index < 0:
                combo.addItem(f"{item_id} (нет в проекте)", item_id)
                index = combo.count() - 1

            combo.setCurrentIndex(index)

        chance_box = QDoubleSpinBox()
        chance_box.setRange(0.0, 100.0)
        chance_box.setDecimals(1)
        chance_box.setSingleStep(5.0)
        chance_box.setSuffix(" %")
        chance_box.setValue(max(0.0, min(100.0, chance * 100.0)))

        min_box = QSpinBox()
        min_box.setRange(1, 9999)
        min_box.setValue(max(1, int(min_amount)))

        max_box = QSpinBox()
        max_box.setRange(1, 9999)
        max_box.setValue(max(int(min_amount), int(max_amount)))

        self.loot_table.setCellWidget(row, 0, combo)
        self.loot_table.setCellWidget(row, 1, chance_box)
        self.loot_table.setCellWidget(row, 2, min_box)
        self.loot_table.setCellWidget(row, 3, max_box)

        expert_host = QWidget()
        expert_layout = QHBoxLayout(expert_host)
        expert_layout.setContentsMargins(0, 0, 0, 0)
        expert_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        expert_box = QCheckBox()
        expert_box.setChecked(bool(expert))
        expert_box.setToolTip(
            "Дроп только в эксперте и мастере."
        )
        expert_layout.addWidget(expert_box)
        self.loot_table.setCellWidget(row, 4, expert_host)

        combo.currentIndexChanged.connect(self.schedule_issue_check)
        chance_box.valueChanged.connect(self.schedule_issue_check)
        min_box.valueChanged.connect(self.schedule_issue_check)
        max_box.valueChanged.connect(self.schedule_issue_check)
        expert_box.toggled.connect(self.schedule_issue_check)

    def remove_loot_row(self):
        row = self.loot_table.currentRow()

        if row >= 0:
            self.loot_table.removeRow(row)
            self.schedule_issue_check()

    def set_loot(self, loot):
        self.loot_table.setRowCount(0)

        for entry in loot:
            if not isinstance(entry, dict):
                continue

            item_id = entry.get("item")

            if not isinstance(item_id, str) or not item_id:
                continue

            try:
                chance = float(entry.get("chance", 0.25))
            except (TypeError, ValueError):
                chance = 0.25

            try:
                min_amount = int(entry.get("min", 1))
            except (TypeError, ValueError):
                min_amount = 1

            try:
                max_amount = int(entry.get("max", min_amount))
            except (TypeError, ValueError):
                max_amount = min_amount

            self.add_loot_row(
                item_id,
                chance,
                max(1, min_amount),
                max(1, max_amount),
                bool(entry.get("expert", False)),
            )

    def get_loot(self):
        loot = []

        for row in range(self.loot_table.rowCount()):
            combo = self.loot_table.cellWidget(row, 0)
            chance_box = self.loot_table.cellWidget(row, 1)
            min_box = self.loot_table.cellWidget(row, 2)
            max_box = self.loot_table.cellWidget(row, 3)
            expert_host = self.loot_table.cellWidget(row, 4)

            if not isinstance(combo, QComboBox) or not isinstance(
                chance_box, QDoubleSpinBox
            ):
                continue

            item_id = combo.currentData()

            if not item_id:
                continue

            min_amount = max(1, min_box.value())
            max_amount = max(min_amount, max_box.value())

            expert_box = (
                expert_host.findChild(QCheckBox)
                if expert_host is not None
                else None
            )

            loot.append({
                "item": item_id,
                "chance": chance_box.value() / 100.0,
                "min": min_amount,
                "max": max_amount,
                "expert": bool(
                    expert_box is not None and expert_box.isChecked()
                ),
            })

        return loot

    # --------------------------------------------------------
    # PHASES
    # --------------------------------------------------------

    def add_phase_row(
        self,
        name="Фаза",
        threshold=1.0,
        speed_multiplier=1.0,
        attack_multiplier=1.0,
    ):
        row = self.phase_table.rowCount()

        if row >= MAX_BOSS_PHASES:
            return

        self.phase_table.insertRow(row)

        name_edit = QLineEdit(str(name))
        name_edit.setPlaceholderText(f"Фаза {row + 1}")

        threshold_box = QDoubleSpinBox()
        threshold_box.setRange(1.0, 100.0)
        threshold_box.setDecimals(0)
        threshold_box.setSingleStep(5.0)
        threshold_box.setSuffix(" %")
        threshold_box.setValue(
            max(1.0, min(100.0, float(threshold) * 100.0))
        )

        speed_box = QDoubleSpinBox()
        speed_box.setRange(0.1, 5.0)
        speed_box.setDecimals(2)
        speed_box.setSingleStep(0.05)
        speed_box.setPrefix("× ")
        speed_box.setValue(max(0.1, min(5.0, float(speed_multiplier))))

        attack_box = QDoubleSpinBox()
        attack_box.setRange(0.1, 5.0)
        attack_box.setDecimals(2)
        attack_box.setSingleStep(0.05)
        attack_box.setPrefix("× ")
        attack_box.setValue(
            max(0.1, min(5.0, float(attack_multiplier)))
        )

        self.phase_table.setCellWidget(row, 0, name_edit)
        self.phase_table.setCellWidget(row, 1, threshold_box)
        self.phase_table.setCellWidget(row, 2, speed_box)
        self.phase_table.setCellWidget(row, 3, attack_box)

        name_edit.textChanged.connect(self.schedule_issue_check)
        threshold_box.valueChanged.connect(self.schedule_issue_check)
        speed_box.valueChanged.connect(self.schedule_issue_check)
        attack_box.valueChanged.connect(self.schedule_issue_check)

        self.refresh_phase_rows()

    def refresh_phase_rows(self):
        """Первая фаза всегда 100% и не редактируется."""

        for row in range(self.phase_table.rowCount()):
            threshold_box = self.phase_table.cellWidget(row, 1)

            if not isinstance(threshold_box, QDoubleSpinBox):
                continue

            if row == 0:
                threshold_box.blockSignals(True)
                threshold_box.setValue(100.0)
                threshold_box.blockSignals(False)
                threshold_box.setEnabled(False)
                threshold_box.setToolTip("Первая фаза всегда активна.")
            else:
                threshold_box.setEnabled(True)
                threshold_box.setToolTip("")

        self.remove_phase_btn.setEnabled(
            self.phase_table.rowCount() > 1
        )
        self.add_phase_btn.setEnabled(
            self.phase_table.rowCount() < MAX_BOSS_PHASES
        )
        self.update_phase_hint()

    def remove_phase_row(self):
        row = self.phase_table.currentRow()

        if row <= 0 or self.phase_table.rowCount() <= 1:
            return

        self.phase_table.removeRow(row)
        self.refresh_phase_rows()
        self.schedule_issue_check()

    def reset_phases(self):
        self.set_phases(None)
        self.schedule_issue_check()

    def update_phase_hint(self):
        count = self.phase_table.rowCount()

        if count <= 1:
            self.phase_hint.setText(
                "Одна фаза: босс ведёт себя одинаково до самой смерти. "
                "Добавь вторую фазу, чтобы он ускорялся на низком здоровье."
            )
        else:
            self.phase_hint.setText(
                f"Фаз: {count}. Первая действует от 100% здоровья, "
                "каждая следующая включается на своём пороге. Генератор "
                "подставит множители в скорость и интервалы атак."
            )

    def set_phases(self, phases):
        self.phase_table.setRowCount(0)

        # Показываем то, что реально лежит в проекте (в безопасных
        # границах): порог первой фазы всё равно принудительно 100%.
        source = _as_list(phases)
        entries = []

        for entry in source:
            if not isinstance(entry, dict):
                continue

            entries.append({
                "name": str(entry.get("name") or ""),
                "threshold": _clamped_float(
                    entry.get("threshold"), 1.0, 0.0, 1.0
                ),
                "speed_multiplier": _clamped_float(
                    entry.get("speed_multiplier"), 1.0, 0.1, 5.0
                ),
                "attack_multiplier": _clamped_float(
                    entry.get("attack_multiplier"), 1.0, 0.1, 5.0
                ),
            })

        if not entries:
            entries = [dict(DEFAULT_PHASE)]

        for index, entry in enumerate(entries[:MAX_BOSS_PHASES], 1):
            self.add_phase_row(
                entry["name"] or f"Фаза {index}",
                entry["threshold"],
                entry["speed_multiplier"],
                entry["attack_multiplier"],
            )

        self.refresh_phase_rows()

    def get_phases(self):
        phases = []

        for row in range(self.phase_table.rowCount()):
            name_edit = self.phase_table.cellWidget(row, 0)
            threshold_box = self.phase_table.cellWidget(row, 1)
            speed_box = self.phase_table.cellWidget(row, 2)
            attack_box = self.phase_table.cellWidget(row, 3)

            if not isinstance(threshold_box, QDoubleSpinBox):
                continue

            name = (
                name_edit.text().strip()
                if isinstance(name_edit, QLineEdit)
                else ""
            )

            phases.append({
                "name": name or f"Фаза {row + 1}",
                "threshold": (
                    1.0 if row == 0 else threshold_box.value() / 100.0
                ),
                "speed_multiplier": (
                    speed_box.value()
                    if isinstance(speed_box, QDoubleSpinBox)
                    else 1.0
                ),
                "attack_multiplier": (
                    attack_box.value()
                    if isinstance(attack_box, QDoubleSpinBox)
                    else 1.0
                ),
            })

        if not phases:
            phases = [dict(DEFAULT_PHASE)]

        return phases

    # --------------------------------------------------------
    # SPRITE
    # --------------------------------------------------------

    def choose_sprite(self):
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Выбрать спрайт босса",
            "",
            "Изображения (*.png *.webp *.bmp *.jpg *.jpeg)",
        )

        if not filename:
            return

        candidate = QImage(filename)

        if candidate.isNull():
            QMessageBox.warning(
                self, "Ошибка", "Не удалось открыть изображение."
            )
            return

        self.sprite = candidate
        self.refresh_sprite()
        self.schedule_issue_check()

    def set_sprite(self, image):
        """Спрайт из менеджера ресурсов."""

        self.sprite = image.copy()
        self.refresh_sprite()
        self.schedule_issue_check()

    def fit_hitbox_to_sprite(self):
        """Ставит хитбокс по размеру текущего спрайта."""

        if self.sprite.isNull():
            QMessageBox.information(
                self,
                "Нет спрайта",
                "Сначала выбери изображение босса.",
            )
            return

        self.width.setValue(max(8, min(1024, self.sprite.width())))
        self.height.setValue(max(8, min(1024, self.sprite.height())))

    def fit_hitbox_to_art(self):
        """Хитбокс по непрозрачным пикселям, без прозрачных полей."""

        if self.sprite.isNull():
            QMessageBox.information(
                self,
                "Нет спрайта",
                "Сначала выбери изображение босса.",
            )
            return

        bounds = opaque_bounds(self.sprite)

        if bounds is None:
            QMessageBox.information(
                self,
                "Пустой спрайт",
                "На изображении нет непрозрачных пикселей.",
            )
            return

        x0, y0, x1, y1 = bounds
        self.width.setValue(max(8, min(1024, x1 - x0 + 1)))
        self.height.setValue(max(8, min(1024, y1 - y0 + 1)))

    def refresh_sprite(self):
        if self.sprite.isNull():
            self.sprite_preview.setPixmap(QPixmap())
            self.sprite_preview.setText("Нет спрайта")
            self.sprite_info.setText("Спрайт не выбран")
            return

        pixmap = QPixmap.fromImage(self.sprite).scaled(
            240,
            240,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )

        self.sprite_preview.setPixmap(pixmap)
        self.sprite_preview.setText("")

        info = f"{self.sprite.width()} × {self.sprite.height()} px"
        bounds = opaque_bounds(self.sprite)

        if bounds is not None:
            x0, y0, x1, y1 = bounds
            info += f" · рисунок {x1 - x0 + 1} × {y1 - y0 + 1}"

        self.sprite_info.setText(info)


def _set_row_visible(form, widget, visible):
    """Скрывает строку формы целиком (или только поле в старом Qt)."""

    try:
        form.setRowVisible(widget, bool(visible))
    except (AttributeError, TypeError):
        widget.setVisible(bool(visible))
