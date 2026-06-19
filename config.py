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

# ID админов через запятую в переменной ADMIN_IDS.
# Пример: ADMIN_IDS="123456789,987654321"
ADMIN_IDS = {
    int(x) for x in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(",") if x
}

# Окно недельного лидерборда (в днях)
LEADERBOARD_WINDOW_DAYS = 7

# ---- Планировщик (этап 3) ----
# Минск = UTC+3 без перехода на летнее время.
TZ_OFFSET_HOURS = int(os.environ.get("TZ_OFFSET_HOURS", "3"))
# Часы указываются в МЕСТНОМ времени, в код переведём в UTC.
DAILY_QUESTION_HOUR = int(os.environ.get("DAILY_QUESTION_HOUR", "12"))   # вопрос дня в 12:00
WEEKLY_SUMMARY_HOUR = int(os.environ.get("WEEKLY_SUMMARY_HOUR", "20"))   # итоги недели в 20:00
WEEKLY_SUMMARY_WEEKDAY = int(os.environ.get("WEEKLY_SUMMARY_WEEKDAY", "6"))  # 6 = воскресенье

# Пауза между сообщениями при рассылке (троттлинг под лимиты Telegram ~30/сек)
BROADCAST_DELAY = float(os.environ.get("BROADCAST_DELAY", "0.05"))
