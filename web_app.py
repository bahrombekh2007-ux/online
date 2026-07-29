import asyncio
import hashlib
import hmac
import json
import os
from urllib.parse import parse_qsl

from flask import Flask, jsonify, request, send_from_directory

import database as db
from config import BOT_TOKEN, ADMIN_IDS

app = Flask(__name__, static_folder="webapp_static", static_url_path="")


def validate_init_data(init_data: str):
    """Telegram WebApp yuborgan initData imzosini tekshiradi va foydalanuvchini qaytaradi."""
    if not init_data:
        return None
    try:
        parsed = dict(parse_qsl(init_data, strict_parsing=True))
        received_hash = parsed.pop("hash", None)
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash or ""):
            return None
        return json.loads(parsed.get("user", "{}"))
    except Exception:
        return None


def _authorized_user():
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user = validate_init_data(init_data)
    if not user:
        return None
    if ADMIN_IDS and user.get("id") not in ADMIN_IDS:
        return None
    return user


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/accounts")
def api_accounts():
    # Lokal ishlab chiqishda tekshiruvni yumshatish uchun DEV_MODE ishlatilishi mumkin
    if os.getenv("WEBAPP_DEV_MODE") != "1":
        user = _authorized_user()
        if not user:
            return jsonify({"error": "unauthorized"}), 401

    accounts = asyncio.run(db.get_accounts())
    total = len(accounts)
    online = sum(1 for a in accounts if a["status"] == "faol")
    paused = sum(1 for a in accounts if a["status"] == "pauza")
    error = sum(1 for a in accounts if a["status"] == "xatolik")

    # Maxfiy session_string'ni frontendga hech qachon yubormaymiz
    safe_accounts = [{k: v for k, v in a.items() if k != "session_string"} for a in accounts]

    return jsonify({
        "accounts": safe_accounts,
        "stats": {"total": total, "online": online, "paused": paused, "error": error},
    })


def run_web_app():
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
