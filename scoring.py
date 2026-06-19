"""Приём результата из Mini App (Telegram WebApp sendData)."""
import json

from telegram import Update
from telegram.ext import ContextTypes

from db.repositories import GameRepo, UserRepo, LeaderboardRepo
from services.scoring import title_for


async def on_webapp_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    try:
        data = json.loads(update.message.web_app_data.data)
        score = int(data.get("score", 0))
        total = int(data.get("total", 0))
        xp = int(data.get("xp", 0))
    except (ValueError, TypeError, json.JSONDecodeError):
        await update.message.reply_text("⚠️ Не удалось прочитать результат игры.")
        return

    username = user.username or user.first_name or "player"

    GameRepo.add(user.id, username, score, total, xp)
    total_xp, streak = UserRepo.apply_game(user.id, username, xp)
    rank = LeaderboardRepo.weekly_rank(user.id)

    await update.message.reply_text(
        "🏁 Игра окончена!\n\n"
        f"Счёт: {score}/{total}   •   +{xp} XP\n"
        f"Звание: {title_for(total_xp)}\n"
        f"Серия дней: 🔥 {streak}\n"
        f"Место в топе недели: {rank if rank else '—'}\n\n"
        "/top — таблица недели"
    )
