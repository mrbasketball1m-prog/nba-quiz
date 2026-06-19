"""Команда /top — топ-10 игроков недели."""
from telegram import Update
from telegram.ext import ContextTypes

from db.repositories import LeaderboardRepo

_MEDALS = ["🥇", "🥈", "🥉"]


async def top(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = LeaderboardRepo.weekly(10)
    if not rows:
        await update.message.reply_text("На этой неделе ещё никто не играл. Будь первым! /start")
        return

    lines = ["🏆 ТОП-10 ИГРОКОВ НЕДЕЛИ\n"]
    for i, r in enumerate(rows):
        place = _MEDALS[i] if i < 3 else f"{i + 1}."
        lines.append(f"{place} @{r['username']} — {r['wx']} XP")
    await update.message.reply_text("\n".join(lines))
