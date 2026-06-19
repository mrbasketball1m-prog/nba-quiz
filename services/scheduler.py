"""Фоновые задачи (этап 3): «вопрос дня» и «итоги недели».

Запускаются по расписанию через JobQueue (см. setup_jobs).
Рассылка идёт в личку каждому игроку с троттлингом под лимиты Telegram.

Функции broadcast_* отделены от job-колбэков, чтобы их можно было
дёрнуть вручную из админ-команд (/sendtoday, /sendweekly) для теста.
"""
import asyncio
from datetime import time, datetime, timezone, timedelta

import config
from db.repositories import QuestionRepo, UserRepo, LeaderboardRepo

LOCAL_TZ = timezone(timedelta(hours=config.TZ_OFFSET_HOURS))


def _utc_hour(local_hour: int) -> int:
    """Местный час -> час UTC (JobQueue работает в UTC)."""
    return (local_hour - config.TZ_OFFSET_HOURS) % 24


async def broadcast_daily_question(bot) -> int:
    """Шлёт «вопрос дня» нативным quiz-опросом всем игрокам. Возвращает число отправленных."""
    q = QuestionRepo.random_one()
    if q is None:
        return 0

    sent = 0
    for uid in UserRepo.all_ids():
        try:
            await bot.send_poll(
                chat_id=uid,
                question="🏀 Вопрос дня:\n" + q["q"],
                options=q["options"],
                type="quiz",
                correct_option_id=q["correct"],
                is_anonymous=True,
            )
            sent += 1
        except Exception:
            # юзер заблокировал бота или иная ошибка — просто пропускаем
            pass
        await asyncio.sleep(config.BROADCAST_DELAY)  # троттлинг
    return sent


async def broadcast_weekly_summary(bot) -> int:
    """Шлёт итоги недели (победитель + топ-10) всем игрокам."""
    rows = LeaderboardRepo.weekly(10)

    if not rows:
        text = "🏆 Итоги недели\n\nНа этой неделе ещё никто не играл. Новая неделя — твой шанс!"
    else:
        winner = rows[0]
        medals = ["🥇", "🥈", "🥉"]
        lines = [
            "🏆 ИТОГИ НЕДЕЛИ\n",
            f"👑 Победитель: @{winner['username']} — {winner['wx']} XP\n",
            "Топ недели:",
        ]
        for i, r in enumerate(rows):
            place = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{place} @{r['username']} — {r['wx']} XP")
        lines.append("\nНовая неделя пошла — погнали за титулом! /start")
        text = "\n".join(lines)

    sent = 0
    for uid in UserRepo.all_ids():
        try:
            await bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception:
            pass
        await asyncio.sleep(config.BROADCAST_DELAY)
    return sent


# ---- job-колбэки (их зовёт JobQueue по расписанию) ----
async def _daily_question_job(context):
    await broadcast_daily_question(context.bot)


async def _weekly_summary_job(context):
    # job стоит на каждый день; шлём только в нужный день недели (Python: Пн=0 .. Вс=6)
    if datetime.now(LOCAL_TZ).weekday() != config.WEEKLY_SUMMARY_WEEKDAY:
        return
    await broadcast_weekly_summary(context.bot)


def setup_jobs(application) -> bool:
    """Регистрирует задачи в JobQueue. Зовётся из bot.py после сборки приложения."""
    jq = application.job_queue
    if jq is None:
        print("[scheduler] JobQueue недоступен — нужен пакет python-telegram-bot[job-queue]")
        return False

    jq.run_daily(_daily_question_job, time=time(hour=_utc_hour(config.DAILY_QUESTION_HOUR)))
    jq.run_daily(_weekly_summary_job, time=time(hour=_utc_hour(config.WEEKLY_SUMMARY_HOUR)))
    print(
        f"[scheduler] вопрос дня в {config.DAILY_QUESTION_HOUR}:00, "
        f"итоги недели в {config.WEEKLY_SUMMARY_HOUR}:00 (местное), "
        f"день недели {config.WEEKLY_SUMMARY_WEEKDAY}"
    )
    return True
