"""Подключение к SQLite и инициализация схемы."""
import sqlite3
from contextlib import contextmanager

from config import DB_PATH


@contextmanager
def get_conn():
    """Контекст-менеджер: открывает соединение, коммитит, закрывает.

    Использование:
        with get_conn() as conn:
            conn.execute(...)
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # доступ к колонкам по имени: row["xp"]
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Создаёт таблицы, если их ещё нет. Безопасно вызывать при каждом старте."""
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users(
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                total_xp    INTEGER DEFAULT 0,
                streak      INTEGER DEFAULT 0,
                last_played TEXT
            );

            CREATE TABLE IF NOT EXISTS games(
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id   INTEGER NOT NULL,
                username  TEXT,
                score     INTEGER,
                total     INTEGER,
                xp        INTEGER,
                played_at TEXT NOT NULL
            );

            -- Фундамент под этап 2 (вопросы из базы + админка). Пока не используется.
            CREATE TABLE IF NOT EXISTS questions(
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                text       TEXT NOT NULL,
                options    TEXT NOT NULL,   -- JSON-массив строк
                correct    INTEGER NOT NULL,-- индекс правильного варианта
                difficulty INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_games_time ON games(played_at);
            CREATE INDEX IF NOT EXISTS idx_games_user ON games(user_id);
            """
        )
