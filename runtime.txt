"""Точка входа. Собирает приложение, поднимает API-сервер и регистрирует хэндлеры.

Структура:
    config.py            — настройки из окружения
    db/database.py       — подключение к SQLite + схема
    db/repositories.py   — весь SQL
    services/scoring.py  — звания и серии (чистая логика)
    services/seed.py     — стартовый набор вопросов
    web/server.py        — HTTP API для фронта (фоновый поток)
    handlers/            — обработчики команд и сообщений
"""
import threading

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import TOKEN
from db.database import init_db
from services.seed import seed_if_empty
from web.server import run_api
from handlers import common, leaderboard, webapp, admin


def main():
    init_db()
    added = seed_if_empty()
    if added:
        print(f"[seed] залито вопросов: {added}")

    # API-сервер крутится в фоновом потоке: bot и web живут в одном процессе,
    # делят одну базу. run_polling должен остаться в главном потоке.
    threading.Thread(target=run_api, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", common.start))
    app.add_handler(CommandHandler("me", common.me))
    app.add_handler(CommandHandler("top", leaderboard.top))
    app.add_handler(CommandHandler("addq", admin.addq))
    app.add_handler(CommandHandler("qcount", admin.qcount))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, webapp.on_webapp_data))

    app.run_polling()


if __name__ == "__main__":
    main()
