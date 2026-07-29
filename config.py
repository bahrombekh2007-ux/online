import os
from dotenv import load_dotenv

load_dotenv()

# Boshqaruv boti tokeni (@BotFather dan olinadi)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Botdan foydalanishga ruxsat berilgan adminlar (Telegram user ID lar, vergul bilan)
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

# my.telegram.org dan olinadigan API ma'lumotlari (barcha akkauntlar uchun umumiy ishlatiladi)
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")

# Ma'lumotlar bazasi fayli
DB_PATH = os.getenv("DB_PATH", "data.db")

# Online statusni yangilash oralig'i (soniya). Tabiiylik uchun random jitter qo'shiladi.
BASE_INTERVAL = int(os.getenv("BASE_INTERVAL", "50"))
JITTER = int(os.getenv("JITTER", "15"))  # +- soniya

# Sessiyalar zaxira papkasi (lokal backup uchun, asosiy manba - DB)
SESSIONS_DIR = os.getenv("SESSIONS_DIR", "sessions_backup")

# Web panel manzili (Render'ga deploy qilingandan keyingi https URL, masalan https://xxx.onrender.com)
WEBAPP_URL = os.getenv("WEBAPP_URL", "")
