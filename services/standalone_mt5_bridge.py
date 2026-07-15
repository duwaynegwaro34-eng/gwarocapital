import os
import json
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from flask import Flask, jsonify, request
import MetaTrader5 as mt5

app = Flask(__name__)
logger = logging.getLogger("gwaro.mt5_bridge")
logging.basicConfig(level=logging.INFO)

HOST = os.getenv("MT5_BRIDGE_HOST", "0.0.0.0")
PORT = int(os.getenv("MT5_BRIDGE_PORT", "5001"))
LOGIN = os.getenv("MT5_LOGIN")
PASSWORD = os.getenv("MT5_PASSWORD")
SERVER = os.getenv("MT5_SERVER")
API_KEY = os.getenv("MT5_BRIDGE_API_KEY", "").strip()
RETRY_DELAY_SECONDS = float(os.getenv("MT5_BRIDGE_RETRY_DELAY_SECONDS", "2"))
RETRY_LIMIT = int(os.getenv("MT5_BRIDGE_RETRIES", "3"))
SESSION_TTL_SECONDS = int(os.getenv("MT5_BRIDGE_SESSION_TTL_SECONDS", "3600"))

_session_lock = threading.RLock()
_sessions: Dict[str, Dict[str, Any]] = {}


def _api_key_required():
    if not API_KEY:
        return None
    provided = request.headers.get("X-API-Key", "")
    if provided != API_KEY:
        return jsonify({"ok": False, "status": "unauthorized", "message": "Missing or invalid API key"}), 401
    return None


def _now():
    return datetime.now(timezone.utc).isoformat()


def _ensure_session(session_id: Optional[str]):
    if not session_id:
        return None
    with _session_lock:
        existing = _sessions.get(session_id)
        if existing:
            existing["last_seen"] = time.time()
            return existing
        return None


def _register_session(session_id: Optional[str], context: Optional[Dict[str, Any]] = None):
    if not session_id:
        return None
    with _session_lock:
        entry = {"session_id": session_id, "created_at": _now(), "last_seen": time.time(), **(context or {})}
        _sessions[session_id] = entry
        return entry


def _cleanup_sessions():
    cutoff = time.time() - SESSION_TTL_SECONDS
    with _session_lock:
        expired = [sid for sid, entry in _sessions.items() if entry.get("last_seen", 0) < cutoff]
        for sid in expired:
            _sessions.pop(sid, None)


def _connect_mt5(login, password, server):
    attempts = 0
    while attempts < RETRY_LIMIT:
        attempts += 1
        try:
            if not mt5.initialize(login=int(login), password=password, server=server):
                raise RuntimeError("MT5 initialize failed")
            account = mt5.account_info()
            return {"ok": bool(account), "status": "connected" if account else "disconnected", "account": account._asdict() if account else None}
        except Exception as exc:
            if attempts >= RETRY_LIMIT:
                raise
            time.sleep(RETRY_DELAY_SECONDS)
    raise RuntimeError("MT5 connection retries exhausted")


def _health_payload():
    try:
        if not mt5.initialize():
            return {"ok": False, "status": "offline", "message": "MetaTrader5 initialization failed"}
        terminal = mt5.terminal_info()
        account = mt5.account_info()
        return {
            "ok": bool(terminal and account),
            "status": "ok" if terminal and account else "disconnected",
            "message": "Bridge healthy" if terminal and account else "Bridge running but MT5 account is not connected",
            "details": {"terminal": terminal is not None, "account": account is not None},
        }
    except Exception as exc:
        return {"ok": False, "status": "offline", "message": str(exc)}


@app.before_request
def _check_auth():
    if request.path in {"/health", "/health/"}:
        return None
    auth_error = _api_key_required()
    if auth_error is not None:
        return auth_error


@app.get("/health")
def health():
    payload = _health_payload()
    code = 200 if payload.get("ok") else 503
    return jsonify(payload), code


@app.post("/connect")
def connect():
    payload = request.get_json(silent=True) or {}
    login = payload.get("login") or LOGIN
    password = payload.get("password") or PASSWORD
    server = payload.get("server") or SERVER
    session_id = payload.get("session_id")

    try:
        result = _connect_mt5(login, password, server)
        if session_id:
            _register_session(session_id, {"login": login, "server": server})
        return jsonify({"ok": bool(result.get("ok")), **result})
    except Exception as exc:
        logger.exception("MT5 connect failed")
        return jsonify({"ok": False, "status": "offline", "message": str(exc)}), 503


@app.get("/account")
def account():
    try:
        _cleanup_sessions()
        account_info = mt5.account_info()
        if account_info is None:
            return jsonify({"ok": False, "status": "disconnected", "message": "No MT5 account info"}), 503
        return jsonify({"ok": True, "account": account_info._asdict()})
    except Exception as exc:
        logger.exception("Account lookup failed")
        return jsonify({"ok": False, "status": "offline", "message": str(exc)}), 503


@app.get("/positions")
def positions():
    try:
        positions = mt5.positions_get()
        return jsonify({"ok": True, "positions": [p._asdict() for p in positions]})
    except Exception as exc:
        logger.exception("Positions lookup failed")
        return jsonify({"ok": False, "status": "offline", "message": str(exc)}), 503


@app.get("/orders")
def orders():
    try:
        orders = mt5.orders_get()
        return jsonify({"ok": True, "orders": [o._asdict() for o in orders]})
    except Exception as exc:
        logger.exception("Orders lookup failed")
        return jsonify({"ok": False, "status": "offline", "message": str(exc)}), 503


@app.post("/command")
def command():
    payload = request.get_json(silent=True) or {}
    command_name = (payload.get("command") or "").strip().lower()
    session_id = payload.get("session_id")
    if session_id:
        _ensure_session(session_id)
    if command_name not in {"start", "stop", "close_all", "break_even"}:
        return jsonify({"ok": False, "status": "bad_request", "message": "Unsupported command"}), 400
    return jsonify({"ok": True, "status": "queued", "message": f"{command_name} command accepted"})


@app.post("/disconnect")
def disconnect():
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    if session_id:
        _ensure_session(session_id)
    try:
        mt5.shutdown()
        return jsonify({"ok": True, "status": "disconnected", "message": "MT5 disconnected"})
    except Exception as exc:
        logger.exception("Disconnect failed")
        return jsonify({"ok": False, "status": "offline", "message": str(exc)}), 503


@app.after_request
def _after_request(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
