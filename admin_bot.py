import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    FloodWaitError,
)

import database as db
from config import API_ID, API_HASH, WEBAPP_URL

logger = logging.getLogger("admin_bot")
router = Router()

# keeper_manager va bot obyektlari main.py da inject qilinadi
keeper_manager = None


class AddAccount(StatesGroup):
    phone = State()
    code = State()
    password = State()
    name = State()


# ---------- Klaviaturalar ----------

def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Akkaunt qo'shish", callback_data="add_account")
    kb.button(text="📋 Akkauntlar ro'yxati", callback_data="list_accounts")
    if WEBAPP_URL:
        kb.button(text="🖥 Web panel", web_app=WebAppInfo(url=WEBAPP_URL))
    kb.button(text="ℹ️ Yordam", callback_data="help")
    kb.adjust(1)
    return kb.as_markup()


def account_menu_kb(account: dict):
    kb = InlineKeyboardBuilder()
    if account["status"] == "faol":
        kb.button(text="⏸ Pauza qilish", callback_data=f"pause_{account['id']}")
    else:
        kb.button(text="▶️ Davom ettirish", callback_data=f"resume_{account['id']}")

    sched_text = "🌙 Rejim: YOQILGAN" if account["schedule_enabled"] else "🌙 Kunduz/kecha rejimi"
    kb.button(text=sched_text, callback_data=f"schedule_{account['id']}")

    read_text = "👁 Auto-read: YOQILGAN ✅" if account["auto_read"] else "👁 Auto-read: O'CHIQ"
    kb.button(text=read_text, callback_data=f"autoread_{account['id']}")

    kb.button(text="🗑 O'chirish", callback_data=f"delete_{account['id']}")
    kb.button(text="⬅️ Orqaga", callback_data="list_accounts")
    kb.adjust(1)
    return kb.as_markup()


def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Bosh menyu", callback_data="main_menu")
    return kb.as_markup()


STATUS_EMOJI = {"faol": "🟢", "pauza": "⏸", "xatolik": "🔴"}


async def _get_owned_account(account_id: int, user_id: int):
    """Akkauntni faqat shu foydalanuvchiga tegishli bo'lsagina qaytaradi."""
    account = await db.get_account(account_id)
    if not account or account["owner_id"] != user_id:
        return None
    return account


# ---------- Umumiy komandalar ----------

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Telegram Online Keeper</b> boshqaruv paneliga xush kelibsiz!\n\n"
        "Bu bot orqali Telegram akkauntlaringizni 24/7 onlayn holatda ushlab turishingiz, "
        "kunduz/kecha rejimini sozlashingiz va xabarlarni avtomatik o'qilgan qilib belgilashingiz mumkin.\n\n"
        "🖥 Akkaunt qo'shish va boshqarishning eng qulay yo'li — pastdagi <b>Web panel</b>.",
        reply_markup=main_menu_kb(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "main_menu")
async def cb_main_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text("🏠 Bosh menyu", reply_markup=main_menu_kb())


@router.callback_query(F.data == "help")
async def cb_help(call: CallbackQuery):
    text = (
        "ℹ️ <b>Qanday ishlaydi?</b>\n\n"
        "1️⃣ \"Akkaunt qo'shish\" tugmasini bosing\n"
        "2️⃣ Telefon raqamingizni yuboring (masalan +998901234567)\n"
        "3️⃣ Telegram yuborgan SMS/ilova kodini kiriting\n"
        "4️⃣ Agar 2 bosqichli tekshiruv (2FA) yoqilgan bo'lsa — parolni kiriting\n\n"
        "Shundan so'ng akkaunt avtomatik ravishda 24/7 onlayn turadi. "
        "Har bir akkaunt uchun kunduz/kecha rejimi va auto-read'ni alohida yoqib/o'chirib qo'ysangiz bo'ladi.\n\n"
        "⚠️ Sessiya ma'lumotlari shifrlangan holda saqlanadi va faqat status yangilash uchun ishlatiladi."
    )
    await call.message.edit_text(text, reply_markup=back_kb(), parse_mode="HTML")


# ---------- Akkaunt qo'shish (FSM) ----------

@router.callback_query(F.data == "add_account")
async def cb_add_account(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddAccount.phone)
    await call.message.edit_text(
        "📱 Akkaunt telefon raqamini xalqaro formatda yuboring.\n\nMasalan: <code>+998901234567</code>",
        parse_mode="HTML",
    )


@router.message(AddAccount.phone)
async def process_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    if not phone.startswith("+") or not phone[1:].isdigit():
        await message.answer("❗️ Noto'g'ri format. Masalan: +998901234567 ko'rinishida yuboring.")
        return

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
    except PhoneNumberInvalidError:
        await message.answer("❗️ Bu telefon raqami noto'g'ri. Qaytadan urinib ko'ring.")
        await client.disconnect()
        return
    except FloodWaitError as e:
        await message.answer(f"⏳ Juda ko'p urinish. {e.seconds} soniyadan keyin qayta urining.")
        await client.disconnect()
        return

    await state.update_data(
        phone=phone,
        phone_code_hash=sent.phone_code_hash,
        session_string=client.session.save(),
    )
    await client.disconnect()
    await state.set_state(AddAccount.code)
    await message.answer("💬 Telegram yuborgan kodni kiriting (masalan: 12345):")


@router.message(AddAccount.code)
async def process_code(message: Message, state: FSMContext):
    data = await state.get_data()
    client = TelegramClient(StringSession(data["session_string"]), API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(
            phone=data["phone"],
            code=message.text.strip(),
            phone_code_hash=data["phone_code_hash"],
        )
    except PhoneCodeInvalidError:
        await message.answer("❗️ Kod noto'g'ri. Qaytadan kiriting:")
        await client.disconnect()
        return
    except SessionPasswordNeededError:
        await state.update_data(session_string=client.session.save())
        await client.disconnect()
        await state.set_state(AddAccount.password)
        await message.answer("🔐 Ikki bosqichli tekshiruv (2FA) parolini kiriting:")
        return

    session_string = client.session.save()
    await client.disconnect()
    await state.update_data(session_string=session_string)
    await state.set_state(AddAccount.name)
    await message.answer("🏷 Akkaunt uchun nom bering (masalan: \"Ishchi akkaunt\"):")


@router.message(AddAccount.password)
async def process_password(message: Message, state: FSMContext):
    data = await state.get_data()
    client = TelegramClient(StringSession(data["session_string"]), API_ID, API_HASH)
    await client.connect()
    try:
        await client.sign_in(password=message.text.strip())
    except Exception as e:
        await message.answer(f"❗️ Parol noto'g'ri yoki xatolik: {e}\nQaytadan kiriting:")
        await client.disconnect()
        return

    session_string = client.session.save()
    await client.disconnect()
    await state.update_data(session_string=session_string)
    await state.set_state(AddAccount.name)
    await message.answer("🏷 Akkaunt uchun nom bering (masalan: \"Ishchi akkaunt\"):")


@router.message(AddAccount.name)
async def process_name(message: Message, state: FSMContext):
    data = await state.get_data()
    account_id = await db.add_account(
        owner_id=message.from_user.id,
        phone=data["phone"],
        name=message.text.strip(),
        session_string=data["session_string"],
    )
    await state.clear()
    keeper_manager.start_account(account_id)
    await message.answer(
        f"✅ Akkaunt muvaffaqiyatli qo'shildi va 24/7 onlayn rejimga o'tkazildi!\n\n"
        f"📱 {data['phone']}",
        reply_markup=main_menu_kb(),
    )


# ---------- Akkauntlar ro'yxati va boshqaruv ----------

@router.callback_query(F.data == "list_accounts")
async def cb_list_accounts(call: CallbackQuery):
    accounts = await db.get_accounts(call.from_user.id)
    if not accounts:
        await call.message.edit_text(
            "📭 Hozircha hech qanday akkaunt qo'shilmagan.", reply_markup=main_menu_kb()
        )
        return

    kb = InlineKeyboardBuilder()
    for acc in accounts:
        emoji = STATUS_EMOJI.get(acc["status"], "⚪️")
        label = f"{emoji} {acc.get('name') or acc['phone']}"
        kb.button(text=label, callback_data=f"view_{acc['id']}")
    kb.button(text="➕ Yangi akkaunt", callback_data="add_account")
    kb.button(text="⬅️ Bosh menyu", callback_data="main_menu")
    kb.adjust(1)
    await call.message.edit_text("📋 Akkauntlaringiz:", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("view_"))
async def cb_view_account(call: CallbackQuery):
    account_id = int(call.data.split("_")[1])
    account = await _get_owned_account(account_id, call.from_user.id)
    if not account:
        await call.answer("Topilmadi", show_alert=True)
        return

    last_online = account.get("last_online") or "—"
    sched = (
        f"{account['online_start_hour']}:00 - {account['online_end_hour']}:00"
        if account["schedule_enabled"]
        else "O'chiq (doim onlayn)"
    )
    text = (
        f"📱 <b>{account.get('name') or account['phone']}</b>\n"
        f"Raqam: {account['phone']}\n"
        f"Holat: {STATUS_EMOJI.get(account['status'])} {account['status']}\n"
        f"Oxirgi faollik: {last_online}\n"
        f"Kunduz/kecha rejimi: {sched}\n"
        f"Auto-read: {'✅' if account['auto_read'] else '❌'}"
    )
    await call.message.edit_text(text, reply_markup=account_menu_kb(account), parse_mode="HTML")


@router.callback_query(F.data.startswith("pause_"))
async def cb_pause(call: CallbackQuery):
    account_id = int(call.data.split("_")[1])
    if not await _get_owned_account(account_id, call.from_user.id):
        await call.answer("Topilmadi", show_alert=True)
        return
    await db.set_status(account_id, "pauza")
    await keeper_manager.stop_account(account_id)
    await call.answer("⏸ Pauza qilindi")
    await cb_view_account(call)


@router.callback_query(F.data.startswith("resume_"))
async def cb_resume(call: CallbackQuery):
    account_id = int(call.data.split("_")[1])
    if not await _get_owned_account(account_id, call.from_user.id):
        await call.answer("Topilmadi", show_alert=True)
        return
    await db.set_status(account_id, "faol")
    keeper_manager.start_account(account_id)
    await call.answer("▶️ Davom ettirildi")
    await cb_view_account(call)


@router.callback_query(F.data.startswith("autoread_"))
async def cb_autoread(call: CallbackQuery):
    account_id = int(call.data.split("_")[1])
    account = await _get_owned_account(account_id, call.from_user.id)
    if not account:
        await call.answer("Topilmadi", show_alert=True)
        return
    new_val = not account["auto_read"]
    await db.set_auto_read(account_id, new_val)
    await keeper_manager.restart_account(account_id)
    await call.answer("Yangilandi")
    await cb_view_account(call)


@router.callback_query(F.data.startswith("schedule_"))
async def cb_schedule(call: CallbackQuery):
    account_id = int(call.data.split("_")[1])
    account = await _get_owned_account(account_id, call.from_user.id)
    if not account:
        await call.answer("Topilmadi", show_alert=True)
        return
    new_val = not account["schedule_enabled"]
    # standart: 08:00 - 24:00 oralig'ida onlayn
    await db.set_schedule(account_id, new_val, 8, 24)
    await keeper_manager.restart_account(account_id)
    await call.answer("Yangilandi (standart: 08:00-24:00 onlayn)")
    await cb_view_account(call)


@router.callback_query(F.data.startswith("delete_"))
async def cb_delete(call: CallbackQuery):
    account_id = int(call.data.split("_")[1])
    if not await _get_owned_account(account_id, call.from_user.id):
        await call.answer("Topilmadi", show_alert=True)
        return
    await keeper_manager.stop_account(account_id)
    await db.delete_account(account_id)
    await call.answer("🗑 O'chirildi")
    await cb_list_accounts(call)
