"""Админские команды: добавление вопросов и ручной запуск рассылок.
Доступ только для ID из ADMIN_IDS (config.py / переменная окружения)."""
from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_IDS
from db.repositories import QuestionRepo
from services.scheduler import broadcast_daily_question, broadcast_weekly_summary

FORMAT = (
    "📝 Добавление вопроса:\n\n"
    "/addq сложность | вопрос | вар1 | вар2 | вар3 | вар4 | правильный\n\n"
    "• сложность: 0 (лёгкий), 1 (средний), 2 (хардкор)\n"
    "• правильный: номер верного варианта, 0–3 (0 = первый)\n\n"
    "Пример:\n"
    "/addq 1 | Сколько титулов у Джордана? | 3 | 5 | 6 | 8 | 2"
)


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


async def addq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Команда только для админа.")
        return

    raw = update.message.text.partition(" ")[2].strip()
    if not raw:
        await update.message.reply_text(FORMAT)
        return

    parts = [p.strip() for p in raw.split("|")]
    if len(parts) != 7:
        await update.message.reply_text(
            f"Нужно ровно 7 частей через | , а пришло {len(parts)}.\n\n{FORMAT}"
        )
        return

    try:
        difficulty = int(parts[0])
        correct = int(parts[6])
        question = parts[1]
        options = parts[2:6]
        if difficulty not in (0, 1, 2):
            raise ValueError("difficulty")
        if correct not in (0, 1, 2, 3):
            raise ValueError("correct")
        if not question or not all(options):
            raise ValueError("empty")
    except ValueError:
        await update.message.reply_text(
            "Неверные данные: сложность 0–2, правильный 0–3, поля не пустые.\n\n" + FORMAT
        )
        return

    QuestionRepo.add(question, options, correct, difficulty)
    await update.message.reply_text(
        f"✅ Вопрос добавлен (сложность {difficulty}). Всего в базе: {QuestionRepo.count()}"
    )


async def qcount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Команда только для админа.")
        return
    await update.message.reply_text(f"📊 Вопросов в базе: {QuestionRepo.count()}")


async def sendtoday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ручной запуск «вопроса дня» — для теста, не дожидаясь расписания."""
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Команда только для админа.")
        return
    n = await broadcast_daily_question(context.bot)
    await update.message.reply_text(f"📤 Вопрос дня отправлен игрокам: {n}")


async def sendweekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ручной запуск «итогов недели» — для теста."""
    if not _is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Команда только для админа.")
        return
    n = await broadcast_weekly_summary(context.bot)
    await update.message.reply_text(f"📤 Итоги недели отправлены игрокам: {n}")
