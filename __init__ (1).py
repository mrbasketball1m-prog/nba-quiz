"""Репозитории — единственное место, где живёт SQL.

Хэндлеры и сервисы НЕ пишут SQL напрямую, а зовут эти методы.
Так при смене SQLite -> Postgres придётся править только этот файл.
"""
import json
from datetime import datetime, date, timedelta

from config import LEADERBOARD_WINDOW_DAYS
from db.database import get_conn
from services.scoring import compute_streak


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _window_start() -> str:
    return (datetime.now() - timedelta(days=LEADERBOARD_WINDOW_DAYS)).isoformat(timespec="seconds")


class GameRepo:
    @staticmethod
    def add(user_id: int, username: str, score: int, total: int, xp: int):
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO games(user_id, username, score, total, xp, played_at) "
                "VALUES(?,?,?,?,?,?)",
                (user_id, username, score, total, xp, _now()),
            )

    @staticmethod
    def best_and_count(user_id: int):
        with get_conn() as conn:
            return conn.execute(
                "SELECT MAX(score) AS best, COUNT(*) AS games FROM games WHERE user_id=?",
                (user_id,),
            ).fetchone()


class UserRepo:
    @staticmethod
    def get(user_id: int):
        with get_conn() as conn:
            return conn.execute(
                "SELECT total_xp, streak FROM users WHERE user_id=?", (user_id,)
            ).fetchone()

    @staticmethod
    def apply_game(user_id: int, username: str, xp: int):
        """Начисляет XP и пересчитывает серию дней. Возвращает (total_xp, streak)."""
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        with get_conn() as conn:
            row = conn.execute(
                "SELECT total_xp, streak, last_played FROM users WHERE user_id=?",
                (user_id,),
            ).fetchone()

            if row is None:
                total_xp, streak = xp, 1
                conn.execute(
                    "INSERT INTO users(user_id, username, total_xp, streak, last_played) "
                    "VALUES(?,?,?,?,?)",
                    (user_id, username, xp, 1, today),
                )
            else:
                total_xp = row["total_xp"] + xp
                streak = compute_streak(row["last_played"], today, yesterday, row["streak"])
                conn.execute(
                    "UPDATE users SET username=?, total_xp=?, streak=?, last_played=? "
                    "WHERE user_id=?",
                    (username, total_xp, streak, today, user_id),
                )

        return total_xp, streak


class LeaderboardRepo:
    @staticmethod
    def weekly(limit: int = 10):
        with get_conn() as conn:
            return conn.execute(
                "SELECT username, SUM(xp) AS wx FROM games WHERE played_at>=? "
                "GROUP BY user_id ORDER BY wx DESC LIMIT ?",
                (_window_start(), limit),
            ).fetchall()

    @staticmethod
    def weekly_rank(user_id: int):
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT user_id, SUM(xp) AS wx FROM games WHERE played_at>=? "
                "GROUP BY user_id ORDER BY wx DESC",
                (_window_start(),),
            ).fetchall()
        for i, r in enumerate(rows):
            if r["user_id"] == user_id:
                return i + 1
        return None


class QuestionRepo:
    """Вопросы квиза. Источник правды для фронта (через API) и сидов."""

    @staticmethod
    def count() -> int:
        with get_conn() as conn:
            return conn.execute("SELECT COUNT(*) AS c FROM questions").fetchone()["c"]

    @staticmethod
    def add(text: str, options: list, correct: int, difficulty: int = 0):
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO questions(text, options, correct, difficulty) VALUES(?,?,?,?)",
                (text, json.dumps(options, ensure_ascii=False), correct, difficulty),
            )

    @staticmethod
    def all_for_client():
        """Отдаёт вопросы в формате, который ждёт фронт: {q, options, correct, d}."""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT text, options, correct, difficulty FROM questions ORDER BY id"
            ).fetchall()
        return [
            {
                "q": r["text"],
                "options": json.loads(r["options"]),
                "correct": r["correct"],
                "d": r["difficulty"],
            }
            for r in rows
        ]
