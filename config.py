"""Конфигурация бота. Всё чувствительное — из переменных окружения Railway."""
import os

TOKEN = os.environ.get("TOKEN")  # токен квиз-бота от @BotFather

WEBAPP_URL = os.environ.get(
    "WEBAPP_URL",
    "https://mrbasketball1m-prog.github.io/nba-quiz/"
)

# Путь к базе. На Railway создай Volume на /data и задай DB_PATH=/data/quiz.db,
# иначе база стирается при каждом редеплое.
DB_PATH = os.environ.get("DB_PATH", "quiz.db")

# ID админов через запятую в переменной ADMIN_IDS (понадобится на этапе админки).
# Пример: ADMIN_IDS="123456789,987654321"
ADMIN_IDS = {
    int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x
}

# Окно недельного лидерборда (в днях)
LEADERBOARD_WINDOW_DAYS = 7
