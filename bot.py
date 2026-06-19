"""Точка входа. Здесь только сборка приложения и регистрация хэндлеров.

Вся логика вынесена в модули:
    config.py            — настройки из окружения
    db/database.py       — подключение к SQLite + схема
    db/repositories.py   — весь SQL (users / games / leaderboard / questions)
    services/scoring.py  — звания и серии (чистая логика)
    handlers/            — обработчики команд и сообщений
"""
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import TOKEN
from db.database import init_db
from handlers import common, leaderboard, webapp


def main():
    init_db()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", common.start))
    app.add_handler(CommandHandler("me", common.me))
    app.add_handler(CommandHandler("top", leaderboard.top))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp.on_webapp_data))

    app.run_polling()


if __name__ == "__main__":
    main()
