"""Репозиторий мультиплеера: очередь и дуэли. Весь SQL по матчам тут.

Кирпич 1 — матчмейкинг:
    find_or_create_match(user_id, username) -> dict(match)
        Логика:
        - если в очереди уже кто-то ждёт (не я сам) -> создаём матч из нас двоих,
          чистим очередь, возвращаем матч со status='playing';
        - иначе кладём себя в очередь и возвращаем матч-заглушку status='waiting'.
"""
import json
import random
from datetime import datetime, timedelta

from config import MATCH_TIMEOUT_SEC
from db.database import get_conn
from db.repositories import QuestionRepo

MATCH_QUESTIONS = 10  # вопросов в дуэли


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _pick_questions(n: int = MATCH_QUESTIONS):
    """Берёт n случайных вопросов из общей базы для дуэли (одинаковые для обоих)."""
    allq = QuestionRepo.all_for_client()  # [{q, options, correct, d}, ...]
    if not allq:
        return []
    random.shuffle(allq)
    return allq[:n]


def _row_to_match(row) -> dict:
    if row is None:
        return None
    return {
        "id": row["id"],
        "p1_id": row["p1_id"],
        "p1_name": row["p1_name"],
        "p2_id": row["p2_id"],
        "p2_name": row["p2_name"],
        "p1_score": row["p1_score"],
        "p2_score": row["p2_score"],
        "p1_answered": row["p1_answered"],
        "p2_answered": row["p2_answered"],
        "status": row["status"],
        "questions": json.loads(row["questions"]),
    }


class MatchRepo:
    @staticmethod
    def get(match_id: int) -> dict:
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
        return _row_to_match(row)

    @staticmethod
    def active_for_user(user_id: int) -> dict:
        """Текущий незавершённый матч игрока (если есть)."""
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM matches WHERE status!='finished' AND (p1_id=? OR p2_id=?) "
                "ORDER BY id DESC LIMIT 1",
                (user_id, user_id),
            ).fetchone()
        return _row_to_match(row)

    @staticmethod
    def find_or_create_match(user_id: int, username: str) -> dict:
        now = _now()
        stale_before = (datetime.now() - timedelta(seconds=MATCH_TIMEOUT_SEC)).isoformat(timespec="seconds")
        with get_conn() as conn:
            # чистим протухшие записи очереди (кто-то закрыл поиск и ушёл)
            conn.execute("DELETE FROM match_queue WHERE joined_at < ? AND user_id != ?", (stale_before, user_id))

            # 0) уже в матче? вернём его (защита от двойного поиска)
            existing = conn.execute(
                "SELECT * FROM matches WHERE status!='finished' AND (p1_id=? OR p2_id=?) "
                "ORDER BY id DESC LIMIT 1",
                (user_id, user_id),
            ).fetchone()
            if existing is not None:
                return _row_to_match(existing)

            # 1) есть ли соперник в очереди (не я сам)?
            waiting = conn.execute(
                "SELECT user_id, username FROM match_queue WHERE user_id!=? "
                "ORDER BY joined_at ASC LIMIT 1",
                (user_id,),
            ).fetchone()

            if waiting is not None:
                # 2) создаём матч из нас двоих, чистим очередь
                opponent_id = waiting["user_id"]
                opponent_name = waiting["username"]
                questions = json.dumps(_pick_questions(), ensure_ascii=False)
                conn.execute("DELETE FROM match_queue WHERE user_id IN (?,?)", (user_id, opponent_id))
                cur = conn.execute(
                    "INSERT INTO matches(p1_id,p1_name,p2_id,p2_name,questions,status,created_at,updated_at) "
                    "VALUES(?,?,?,?,?,?,?,?)",
                    (opponent_id, opponent_name, user_id, username, questions, "playing", now, now),
                )
                match_id = cur.lastrowid
                row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
                return _row_to_match(row)

            # 3) соперника нет — встаём в очередь, ждём
            conn.execute(
                "INSERT OR REPLACE INTO match_queue(user_id, username, joined_at) VALUES(?,?,?)",
                (user_id, username, now),
            )
            return {"status": "waiting", "id": None}

    @staticmethod
    def leave_queue(user_id: int):
        with get_conn() as conn:
            conn.execute("DELETE FROM match_queue WHERE user_id=?", (user_id,))

    @staticmethod
    def queue_size() -> int:
        with get_conn() as conn:
            return conn.execute("SELECT COUNT(*) AS c FROM match_queue").fetchone()["c"]

    @staticmethod
    def submit_answer(match_id: int, user_id: int, q_index: int, is_correct: bool, seconds_left: float) -> dict:
        """Засчитывает ответ игрока на вопрос q_index.

        Очки: правильный = 100 + бонус за скорость (до +100, по 10 за сек из 10).
        Защита: нельзя ответить на тот же вопрос дважды (сверяем по *_answered).
        Когда оба прошли все вопросы — матч помечается finished.
        Возвращает актуальный матч (dict).
        """
        now = _now()
        gained = 0
        if is_correct:
            bonus = max(0, min(100, int(seconds_left * 10)))
            gained = 100 + bonus

        with get_conn() as conn:
            row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
            if row is None:
                return None

            total_q = len(json.loads(row["questions"]))
            is_p1 = (row["p1_id"] == user_id)
            answered_col = "p1_answered" if is_p1 else "p2_answered"
            score_col = "p1_score" if is_p1 else "p2_score"
            answered = row[answered_col]

            # принимаем ответ только если он на текущий (ещё не пройденный) вопрос
            if q_index != answered:
                return _row_to_match(row)  # дубль/рассинхрон — игнорируем, отдаём как есть

            new_answered = answered + 1
            new_score = row[score_col] + gained

            # пересчёт статуса: оба прошли все вопросы -> finished
            other_answered = row["p2_answered"] if is_p1 else row["p1_answered"]
            new_status = row["status"]
            if new_answered >= total_q and other_answered >= total_q:
                new_status = "finished"

            conn.execute(
                f"UPDATE matches SET {answered_col}=?, {score_col}=?, status=?, updated_at=? WHERE id=?",
                (new_answered, new_score, new_status, now, match_id),
            )
            row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()

        return _row_to_match(row)

    @staticmethod
    def leave_match(match_id: int, user_id: int) -> dict:
        """Игрок явно вышел из матча → матч завершается немедленно.
        Победитель определится по текущему счёту (вышедший обычно отстаёт)."""
        now = _now()
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
            if row is None:
                return None
            if row["status"] != "finished":
                conn.execute(
                    "UPDATE matches SET status='finished', updated_at=? WHERE id=?",
                    (now, match_id),
                )
                row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
        return _row_to_match(row)

    @staticmethod
    def check_timeout(match_id: int) -> dict:
        """Если матч завис (нет обновлений дольше MATCH_TIMEOUT_SEC) — завершаем его.
        Вызывается при опросе статуса, чтобы второй игрок не ждал вечно."""
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
            if row is None:
                return None
            if row["status"] != "finished":
                idle = (datetime.now() - _parse(row["updated_at"])).total_seconds()
                if idle > MATCH_TIMEOUT_SEC:
                    conn.execute(
                        "UPDATE matches SET status='finished', updated_at=? WHERE id=?",
                        (_now(), match_id),
                    )
                    row = conn.execute("SELECT * FROM matches WHERE id=?", (match_id,)).fetchone()
        return _row_to_match(row)
