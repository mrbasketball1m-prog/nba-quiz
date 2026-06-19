"""Базовые команды: /start и /me."""
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import ContextTypes

from config import WEBAPP_URL
from db.repositories import UserRepo, GameRepo
from services.scoring import title_for


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ВАЖНО: web_app именно в reply-кнопке — только так фронт может вернуть боту sendData.
    keyboard = [[KeyboardButton("🏀 Играть", web_app=WebAppInfo(url=WEBAPP_URL))]]
    markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Жми «🏀 Играть» и проверь, насколько хорошо ты знаешь NBA.\n\n"
        "/top — топ игроков недели\n"
        "/me — твой профиль",
        reply_markup=markup,
    )


async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    u = UserRepo.get(user.id)
    if u is None:
        await update.message.reply_text("Ты ещё не играл. Жми /start и поехали!")
        return

    stats = GameRepo.best_and_count(user.id)
    await update.message.reply_text(
        "👤 Твой профиль\n\n"
        f"Звание: {title_for(u['total_xp'])}\n"
        f"Всего XP: {u['total_xp']}\n"
        f"Лучший результат: {stats['best']}\n"
        f"Игр сыграно: {stats['games']}\n"
        f"Серия дней: 🔥 {u['streak']}"
    )
