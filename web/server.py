"""Мини веб-сервер на Flask. Крутится в фоновом потоке рядом с ботом
и отдаёт вопросы фронту (Mini App на GitHub Pages) по HTTP.

Эндпоинты:
    GET /health          — проверка живости + число вопросов
    GET /api/questions   — список вопросов в формате фронта [{q, options, correct, d}]
"""
import os

from flask import Flask, jsonify
from werkzeug.serving import make_server

from db.repositories import QuestionRepo

flask_app = Flask(__name__)


@flask_app.after_request
def _add_cors(resp):
    # Фронт живёт на github.io, API — на railway.app: это разные домены (CORS).
    # Без этих заголовков браузер не даст фронту прочитать ответ.
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return resp


@flask_app.get("/health")
def health():
    return {"status": "ok", "questions": QuestionRepo.count()}


@flask_app.get("/api/questions")
def api_questions():
    return jsonify(QuestionRepo.all_for_client())


def run_api():
    """Запускается в отдельном потоке из bot.py. Railway сам подставит PORT."""
    port = int(os.environ.get("PORT", 8080))
    make_server("0.0.0.0", port, flask_app, threaded=True).serve_forever()
