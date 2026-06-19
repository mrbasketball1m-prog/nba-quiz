import os
import json
import sqlite3
from contextlib import closing
from datetime import datetime, date, timedelta

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes
)

# ---- Конфиг (всё через переменные окружения Railway) ----
TOKEN = os.environ.get("TOKEN")  # ТОКЕН КВИЗ-БОТА (не бота заявок!)
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://mrbasketball1m-prog.github.io/nba-quiz/")
# ВАЖНО: на Railway создай Volume, смонтируй на /data и задай DB_PATH=/data/quiz.db,
# иначе SQLite-файл стирается при каждом редеплое.
DB_PATH = os.environ.get("DB_PATH", "quiz.db")

# ---- Звания по суммарному XP ----
TITLES = [
    (0,    "🪑 Скамеечник"),
    (150,  "🏀 Ролевик"),
    (500,  "⭐ Матч Звёзд"),
    (1200, "👑 MVP"),
]

def title_for(total_xp: int) -> str:
    name = TITLES[0][1]
    for threshold, t in TITLES:
        if total_xp >= threshold:
            name = t
    return name

# ---- База данных ----
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with closing(db()) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS games(
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                username  TEXT,
                score     INTEGER,
                total     INTEGER,
                xp        INTEGER,
                played_at TEXT NOT NULL
            )""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users(
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                total_xp    INTEGER DEFAULT 0,
                streak      INTEGER DEFAULT 0,
                last_played TEXT
            )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_games_time ON games(played_at)")
        conn.commit()

# ---- /start: кнопка запуска Mini App (reply-keyboard!) ----
# sendData с фронта прилетает боту ТОЛЬКО если Mini App запущен с reply-кнопки.
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = [[KeyboardButton("🏀 Играть", web_app=WebAppInfo(url=WEBAPP_URL))]]
    markup = ReplyKeyboardMarkup(kb, resize_keyboard=True)
    await update.message.reply_text(
        "Жми «🏀 Играть» и проверь, насколько хорошо ты знаешь NBA.\n\n"
        "/top — топ игроков недели\n"
        "/me — твой профиль",
        reply_markup=markup
    )

# ---- Приём результата из Mini App ----
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

    uname = user.username or user.first_name or "player"
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    now = datetime.now().isoformat(timespec="seconds")
    week_ago = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")

    with closing(db()) as conn:
        # 1) пишем игру
        conn.execute(
            "INSERT INTO games(user_id, username, score, total, xp, played_at) VALUES(?,?,?,?,?,?)",
            (user.id, uname, score, total, xp, now)
        )
        # 2) обновляем профиль + серию дней
        row = conn.execute(
            "SELECT total_xp, streak, last_played FROM users WHERE user_id=?",
            (user.id,)
        ).fetchone()

        if row is None:
            total_xp, streak = xp, 1
            conn.execute(
                "INSERT INTO users(user_id, username, total_xp, streak, last_played) VALUES(?,?,?,?,?)",
                (user.id, uname, xp, 1, today)
            )
        else:
            total_xp = row["total_xp"] + xp
            streak = row["streak"]
            if row["last_played"] == today:
                pass                      # уже играл сегодня — серию не трогаем
            elif row["last_played"] == yesterday:
                streak += 1               # играл вчера — серия растёт
            else:
                streak = 1                # пропуск — серия сбрасывается
            conn.execute(
                "UPDATE users SET username=?, total_xp=?, streak=?, last_played=? WHERE user_id=?",
                (uname, total_xp, streak, today, user.id)
            )

        # 3) место в топе недели
        board = conn.execute(
            "SELECT user_id, SUM(xp) AS wx FROM games WHERE played_at>=? "
            "GROUP BY user_id ORDER BY wx DESC",
            (week_ago,)
        ).fetchall()
        conn.commit()

    rank = next((i + 1 for i, r in enumerate(board) if r["user_id"] == user.id), None)

    await update.message.reply_text(
        "🏁 Игра окончена!\n\n"
        f"Счёт: {score}/{total}   •   +{xp} XP\n"
        f"Звание: {title_for(total_xp)}\n"
        f"Серия дней: 🔥 {streak}\n"
        f"Место в топе недели: {rank if rank else '—'}\n\n"
        "/top — таблица недели"
    )

# ---- /top: Топ-10 недели ----
async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    week_ago = (datetime.now() - timedelta(days=7)).isoformat(timespec="seconds")
    with closing(db()) as conn:
        rows = conn.execute(
            "SELECT username, SUM(xp) AS wx FROM games WHERE played_at>=? "
            "GROUP BY user_id ORDER BY wx DESC LIMIT 10",
            (week_ago,)
        ).fetchall()

    if not rows:
        await update.message.reply_text("На этой неделе ещё никто не играл. Будь первым! /start")
        return

    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 ТОП-10 ИГРОКОВ НЕДЕЛИ\n"]
    for i, r in enumerate(rows):
        place = medals[i] if i < 3 else f"{i + 1}."
        lines.append(f"{place} @{r['username']} — {r['wx']} XP")
    await update.message.reply_text("\n".join(lines))

# ---- /me: личный профиль ----
async def me(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    with closing(db()) as conn:
        u = conn.execute(
            "SELECT total_xp, streak FROM users WHERE user_id=?", (user.id,)
        ).fetchone()
        stats = conn.execute(
            "SELECT MAX(score) AS best, COUNT(*) AS games FROM games WHERE user_id=?",
            (user.id,)
        ).fetchone()

    if u is None:
        await update.message.reply_text("Ты ещё не играл. Жми /start и поехали!")
        return

    await update.message.reply_text(
        "👤 Твой профиль\n\n"
        f"Звание: {title_for(u['total_xp'])}\n"
        f"Всего XP: {u['total_xp']}\n"
        f"Лучший результат: {stats['best']}\n"
        f"Игр сыграно: {stats['games']}\n"
        f"Серия дней: 🔥 {u['streak']}"
    )

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("top", top))
    app.add_handler(CommandHandler("me", me))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, on_webapp_data))
    app.run_polling()

if __name__ == "__main__":
    main()
