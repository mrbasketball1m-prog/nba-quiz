"""Чистая бизнес-логика: звания, серии. Без SQL и без Telegram — легко тестировать."""

# Пороги званий по суммарному XP (по возрастанию)
TITLES = [
    (0,    "🪑 Скамеечник"),
    (150,  "🏀 Ролевик"),
    (500,  "⭐ Матч Звёзд"),
    (1200, "👑 MVP"),
]


def title_for(total_xp: int) -> str:
    """Возвращает звание по суммарному XP."""
    name = TITLES[0][1]
    for threshold, t in TITLES:
        if total_xp >= threshold:
            name = t
    return name


def compute_streak(last_played: str, today: str, yesterday: str, current: int) -> int:
    """Пересчёт серии дней.

    - играл сегодня      -> серия не меняется
    - играл вчера        -> серия +1
    - был пропуск        -> серия сбрасывается в 1
    """
    if last_played == today:
        return current
    if last_played == yesterday:
        return current + 1
    return 1
