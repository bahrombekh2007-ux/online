import asyncio
import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl

from flask import Flask, jsonify, request, send_from_directory

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneNumberInvalidError,
    FloodWaitError,
)

import database as db
from keeper import OnlineKeeperManager
from config import BOT_TOKEN, API_ID, API_HASH

app = Flask(__name__, static_folder="webapp_static", static_url_path="")

# main.py orqali inject qilinadi
keeper_manager: OnlineKeeperManager | None = None

# Har bir foydalanuvchi uchun akkaunt qo'shish jarayonining vaqtinchalik holati
# { user_id: {"phone":..., "phone_code_hash":..., "session_string":..., "needs_password": bool, "ts": float} }
pending_logins: dict[int, dict] = {}
PENDING_TTL = 10 * 60  # 10 daqiqa


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


def current_user_id():
    """Har qanday haqiqiy Telegram foydalanuvchisiga ruxsat beriladi (admin bo'lishi shart emas)."""
    if os.getenv("WEBAPP_DEV_MODE") == "1":
        return 0  # lokal test uchun soxta foydalanuvchi
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    user = validate_init_data(init_data)
    if not user:
        return None
    return user.get("id")


def _cleanup_pending():
    now = time.time()
    expired = [uid for uid, v in pending_logins.items() if now - v["ts"] > PENDING_TTL]
    for uid in expired:
        pending_logins.pop(uid, None)


# ---------- Statik fayllar ----------

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------- Akkauntlar ro'yxati ----------

@app.route("/api/accounts")
def api_accounts():
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401

    accounts = asyncio.run(db.get_accounts(user_id))
    total = len(accounts)
    online = sum(1 for a in accounts if a["status"] == "faol")
    paused = sum(1 for a in accounts if a["status"] == "pauza")
    error = sum(1 for a in accounts if a["status"] == "xatolik")

    safe_accounts = [{k: v for k, v in a.items() if k != "session_string"} for a in accounts]

    return jsonify({
        "accounts": safe_accounts,
        "stats": {"total": total, "online": online, "paused": paused, "error": error},
    })


def _get_owned_account(account_id: int, user_id: int):
    account = asyncio.run(db.get_account(account_id))
    if not account or account["owner_id"] != user_id:
        return None
    return account


# ---------- Akkaunt boshqarish (pauza/davom/ochirish/sozlamalar) ----------

@app.route("/api/accounts/<int:account_id>/pause", methods=["POST"])
def api_pause(account_id):
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    if not _get_owned_account(account_id, user_id):
        return jsonify({"error": "forbidden"}), 403
    asyncio.run(db.set_status(account_id, "pauza"))
    asyncio.run(keeper_manager.stop_account(account_id))
    return jsonify({"ok": True})


@app.route("/api/accounts/<int:account_id>/resume", methods=["POST"])
def api_resume(account_id):
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    if not _get_owned_account(account_id, user_id):
        return jsonify({"error": "forbidden"}), 403
    asyncio.run(db.set_status(account_id, "faol"))
    keeper_manager.start_account(account_id)
    return jsonify({"ok": True})


@app.route("/api/accounts/<int:account_id>/delete", methods=["POST"])
def api_delete(account_id):
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    if not _get_owned_account(account_id, user_id):
        return jsonify({"error": "forbidden"}), 403
    asyncio.run(keeper_manager.stop_account(account_id))
    asyncio.run(db.delete_account(account_id))
    return jsonify({"ok": True})


@app.route("/api/accounts/<int:account_id>/schedule", methods=["POST"])
def api_schedule(account_id):
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    if not _get_owned_account(account_id, user_id):
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json(force=True, silent=True) or {}
    enabled = bool(data.get("enabled"))
    start_hour = int(data.get("start_hour", 8))
    end_hour = int(data.get("end_hour", 24))
    asyncio.run(db.set_schedule(account_id, enabled, start_hour, end_hour))
    asyncio.run(keeper_manager.restart_account(account_id))
    return jsonify({"ok": True})


@app.route("/api/accounts/<int:account_id>/autoread", methods=["POST"])
def api_autoread(account_id):
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    if not _get_owned_account(account_id, user_id):
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json(force=True, silent=True) or {}
    enabled = bool(data.get("enabled"))
    asyncio.run(db.set_auto_read(account_id, enabled))
    asyncio.run(keeper_manager.restart_account(account_id))
    return jsonify({"ok": True})


# ---------- Akkaunt qo'shish (telefon -> kod -> [parol] -> nom) ----------

@app.route("/api/add/request-code", methods=["POST"])
def api_add_request_code():
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    _cleanup_pending()

    data = request.get_json(force=True, silent=True) or {}
    phone = (data.get("phone") or "").strip()
    if not phone.startswith("+") or not phone[1:].replace(" ", "").isdigit():
        return jsonify({"error": "Telefon raqam noto'g'ri formatda. Masalan: +998901234567"}), 400

    async def _run():
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.connect()
        try:
            sent = await client.send_code_request(phone)
            return {
                "phone": phone,
                "phone_code_hash": sent.phone_code_hash,
                "session_string": client.session.save(),
                "needs_password": False,
                "ts": time.time(),
            }, None
        except PhoneNumberInvalidError:
            return None, "Bu telefon raqami noto'g'ri."
        except FloodWaitError as e:
            return None, f"Juda ko'p urinish. {e.seconds} soniyadan keyin urining."
        finally:
            await client.disconnect()

    state, error = asyncio.run(_run())
    if error:
        return jsonify({"error": error}), 400

    pending_logins[user_id] = state
    return jsonify({"ok": True, "step": "code"})


@app.route("/api/add/verify-code", methods=["POST"])
def api_add_verify_code():
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401

    pending = pending_logins.get(user_id)
    if not pending:
        return jsonify({"error": "Jarayon boshlanmagan. Qaytadan telefon raqam kiriting."}), 400

    data = request.get_json(force=True, silent=True) or {}
    code = (data.get("code") or "").strip()

    async def _run():
        client = TelegramClient(StringSession(pending["session_string"]), API_ID, API_HASH)
        await client.connect()
        try:
            await client.sign_in(
                phone=pending["phone"],
                code=code,
                phone_code_hash=pending["phone_code_hash"],
            )
            return {"session_string": client.session.save(), "needs_password": False}, None
        except SessionPasswordNeededError:
            return {"session_string": client.session.save(), "needs_password": True}, None
        except PhoneCodeInvalidError:
            return None, "Kod noto'g'ri. Qaytadan kiriting."
        except PhoneCodeExpiredError:
            return None, "Kod muddati tugagan. Iltimos, jarayonni boshidan (telefon raqamdan) qaytadan boshlang."
        finally:
            await client.disconnect()

    result, error = asyncio.run(_run())
    if error:
        return jsonify({"error": error}), 400

    pending["session_string"] = result["session_string"]
    pending["needs_password"] = result["needs_password"]
    pending["ts"] = time.time()

    if result["needs_password"]:
        return jsonify({"ok": True, "step": "password"})
    return jsonify({"ok": True, "step": "name"})


@app.route("/api/add/verify-password", methods=["POST"])
def api_add_verify_password():
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401

    pending = pending_logins.get(user_id)
    if not pending or not pending.get("needs_password"):
        return jsonify({"error": "Jarayon boshlanmagan."}), 400

    data = request.get_json(force=True, silent=True) or {}
    password = data.get("password") or ""

    async def _run():
        client = TelegramClient(StringSession(pending["session_string"]), API_ID, API_HASH)
        await client.connect()
        try:
            await client.sign_in(password=password)
            return client.session.save(), None
        except Exception as e:
            return None, f"Parol noto'g'ri yoki xatolik: {e}"
        finally:
            await client.disconnect()

    session_string, error = asyncio.run(_run())
    if error:
        return jsonify({"error": error}), 400

    pending["session_string"] = session_string
    pending["ts"] = time.time()
    return jsonify({"ok": True, "step": "name"})


@app.route("/api/add/finish", methods=["POST"])
def api_add_finish():
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401

    pending = pending_logins.get(user_id)
    if not pending:
        return jsonify({"error": "Jarayon boshlanmagan."}), 400

    data = request.get_json(force=True, silent=True) or {}
    name = (data.get("name") or "").strip() or pending["phone"]

    account_id = asyncio.run(
        db.add_account(
            owner_id=user_id,
            phone=pending["phone"],
            name=name,
            session_string=pending["session_string"],
        )
    )
    pending_logins.pop(user_id, None)

    if keeper_manager:
        keeper_manager.start_account(account_id)

    return jsonify({"ok": True, "account_id": account_id})


@app.route("/api/add/cancel", methods=["POST"])
def api_add_cancel():
    user_id = current_user_id()
    if user_id is None:
        return jsonify({"error": "unauthorized"}), 401
    pending_logins.pop(user_id, None)
    return jsonify({"ok": True})


def run_web_app():
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, threaded=True)
