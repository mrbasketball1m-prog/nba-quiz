"""Мини веб-сервер на Flask. Крутится в фоновом потоке рядом с ботом
и отдаёт вопросы фронту (Mini App на GitHub Pages) по HTTP.

Эндпоинты:
    GET /health          — проверка живости + число вопросов
    GET /api/questions   — список вопросов в формате фронта [{q, options, correct, d}]
"""
import os

from flask import Flask, jsonify, request
from werkzeug.serving import make_server

from db.repositories import QuestionRepo
from db.match_repo import MatchRepo

flask_app = Flask(__name__)


@flask_app.after_request
def _add_cors(resp):
    # Фронт живёт на github.io, API — на railway.app: это разные домены (CORS).
    # Для POST с JSON браузер шлёт preflight и требует разрешить заголовок Content-Type.
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


@flask_app.route("/api/<path:_any>", methods=["OPTIONS"])
def _cors_preflight(_any):
    # Ответ на preflight-запрос браузера (заголовки добавит _add_cors выше).
    return ("", 204)


@flask_app.get("/health")
def health():
    return {"status": "ok", "questions": QuestionRepo.count()}


@flask_app.get("/api/questions")
def api_questions():
    return jsonify(QuestionRepo.all_for_client())


# ===== Мультиплеер (этап 4) =====

def _public_match(m: dict, me_id: int) -> dict:
    """Готовит состояние матча для конкретного игрока: кто из них «я», кто «соперник».
    Вопросы НЕ отдаём целиком на каждый poll — только их количество и тек. индекс «меня».
    """
    if m is None or m.get("id") is None:
        return {"status": m.get("status", "waiting") if m else "waiting", "match_id": None}

    i_am_p1 = (m["p1_id"] == me_id)
    me = {
        "score": m["p1_score"] if i_am_p1 else m["p2_score"],
        "answered": m["p1_answered"] if i_am_p1 else m["p2_answered"],
        "name": m["p1_name"] if i_am_p1 else m["p2_name"],
    }
    opp = {
        "score": m["p2_score"] if i_am_p1 else m["p1_score"],
        "answered": m["p2_answered"] if i_am_p1 else m["p1_answered"],
        "name": m["p2_name"] if i_am_p1 else m["p1_name"],
    }
    return {
        "status": m["status"],
        "match_id": m["id"],
        "total": len(m["questions"]),
        "me": me,
        "opponent": opp,
    }


@flask_app.post("/api/match/find")
def api_match_find():
    """Поиск соперника. Тело: {user_id, username}.
    Ответ: матч (со status playing) или {status:'waiting'} + при playing — вопросы.
    """
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data["user_id"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "bad user_id"}), 400
    username = str(data.get("username") or "player")

    m = MatchRepo.find_or_create_match(user_id, username)
    resp = _public_match(m, user_id)
    # вопросы отдаём один раз при старте матча (фронт их запомнит)
    if resp.get("match_id"):
        resp["questions"] = m["questions"]
    return jsonify(resp)


@flask_app.get("/api/match/state")
def api_match_state():
    """Статус матча для поллинга. Параметры: ?match_id=&user_id="""
    try:
        match_id = int(request.args["match_id"])
        user_id = int(request.args["user_id"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "bad params"}), 400

    m = MatchRepo.get(match_id)
    if m is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_public_match(m, user_id))


@flask_app.post("/api/match/answer")
def api_match_answer():
    """Ответ на вопрос. Тело: {match_id, user_id, q_index, correct(bool), seconds_left}."""
    data = request.get_json(silent=True) or {}
    try:
        match_id = int(data["match_id"])
        user_id = int(data["user_id"])
        q_index = int(data["q_index"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "bad params"}), 400
    is_correct = bool(data.get("correct"))
    try:
        seconds_left = float(data.get("seconds_left", 0))
    except (ValueError, TypeError):
        seconds_left = 0.0

    m = MatchRepo.submit_answer(match_id, user_id, q_index, is_correct, seconds_left)
    if m is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(_public_match(m, user_id))


@flask_app.post("/api/match/cancel")
def api_match_cancel():
    """Выйти из очереди (если передумал искать). Тело: {user_id}."""
    data = request.get_json(silent=True) or {}
    try:
        user_id = int(data["user_id"])
    except (KeyError, ValueError, TypeError):
        return jsonify({"error": "bad user_id"}), 400
    MatchRepo.leave_queue(user_id)
    return jsonify({"status": "left"})


def run_api():
    """Запускается в отдельном потоке из bot.py. Railway сам подставит PORT."""
    port = int(os.environ.get("PORT", 8080))
    make_server("0.0.0.0", port, flask_app, threaded=True).serve_forever()
