# 🟢 Telegram Online Keeper

Telegram akkauntlarni 24/7 onlayn holatda avtomatik ushlab turadigan, ko'p akkauntli, boshqaruv botli tizim.

## ✨ Funksiyalar

- ➕ Cheksiz sonli akkaunt qo'shish (boshqaruv bot orqali, tugmalar bilan)
- 🟢 Har bir akkaunt uchun avtomatik onlayn status (tabiiy random interval bilan)
- 🌙 Kunduz/kecha rejimi (masalan faqat 08:00–24:00 onlayn, tunda tabiiy offline)
- 👁 Xabarlarni avtomatik "ko'rildi" qilib belgilash (auto-read)
- ⏸ Har bir akkauntni pauza/davom ettirish, o'chirish
- ⚠️ Akkaunt bloklansa yoki sessiya bekor bo'lsa — sizga darhol xabar keladi
- 🖥 **Telegram Web App panel** — barcha ulangan akkauntlar, ularning holati (onlayn/pauza/xatolik), oxirgi faollik vaqti va sozlamalari real vaqtda (har 5 soniyada yangilanadi)
- 🐳 Docker va Render.com uchun tayyor konfiguratsiya

## 🖥 Web panel haqida

Bot menyusida **"🖥 Web panel"** tugmasi Telegram ichida ochiladigan mini-ilova (Web App) hisoblanadi. U:
- Jami/onlayn/pauzadagi/xatolikdagi akkauntlar sonini ko'rsatadi
- Har bir akkaunt uchun jonli holat, telefon raqam, oxirgi faollik vaqtini chiqaradi
- Faqat `ADMIN_IDS`da ko'rsatilgan foydalanuvchilarga ochiladi (Telegram imzosi orqali tekshiriladi)

**Talab**: Telegram Web App ishlashi uchun **https manzil** shart. Shuning uchun `WEBAPP_URL` ni faqat loyihani (Render yoki boshqa hostingga) deploy qilib, ochiq https URL olgandan keyin `.env`ga qo'shing. Lokal kompyuterda ishlayotganda bu tugma ko'rinmaydi (avtomatik yashiriladi).

## ⚠️ Muhim ogohlantirish

Bu tizim shaxsiy Telegram akkauntingizning sessiyasidan foydalanadi (userbot). Telegram ToS'ida avtomatlashtirish cheklangan — shaxsiy, mo''tadil foydalanishda odatda muammo bo'lmaydi, lekin bir nechta akkauntni tinimsiz, tijorat maqsadida ishlatish akkauntni cheklashi (limit/ban) mumkin. O'z xavf-xatoingiz asosida foydalaning.

## 🚀 O'rnatish (lokal / VPS)

1. **API ma'lumotlarini oling**: https://my.telegram.org/apps ga kiring → yangi ilova yarating → `api_id` va `api_hash` ni oling.

2. **Boshqaruv boti yarating**: Telegram'da [@BotFather](https://t.me/BotFather) ga yozing → `/newbot` → tokenni oling.

3. **O'z Telegram ID'ingizni bilib oling**: [@userinfobot](https://t.me/userinfobot) ga yozing.

4. Loyihani ko'chiring va sozlang:

```bash
cd telegram-online-keeper
cp .env.example .env
# .env faylini oching va BOT_TOKEN, ADMIN_IDS, API_ID, API_HASH ni to'ldiring
```

5. Kutubxonalarni o'rnating va ishga tushiring:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

6. Telegram'da boshqaruv botingizga `/start` yozing va "➕ Akkaunt qo'shish" tugmasini bosing.

## 🐳 Docker orqali ishga tushirish

```bash
docker build -t online-keeper .
docker run -d --name online-keeper --env-file .env -v $(pwd)/data:/app/data online-keeper
```

## ☁️ Render.com'ga deploy qilish

> **Muhim**: Render'ning bepul tarifi (Free) uxlab qoladi va Background Worker'ni qo'llab-quvvatlamaydi. Kamida **Starter** tarif (pullik, ~$7/oy) va doimiy disk kerak — chunki bu 24/7 ishlaydigan fon jarayoni (web server emas).

1. Loyihani GitHub'ga yuklang.
2. Render Dashboard → **New** → **Blueprint** → repo'ni tanlang (`render.yaml` avtomatik aniqlanadi, xizmat turi — **Web Service**).
3. Environment tab'ida `BOT_TOKEN`, `ADMIN_IDS`, `API_ID`, `API_HASH` qiymatlarini kiriting.
4. Birinchi marta deploy qiling — Render sizga `https://xxxxx.onrender.com` ko'rinishidagi manzil beradi.
5. O'sha manzilni nusxalab, `WEBAPP_URL` environment o'zgaruvchisiga qo'ying va qayta deploy qiling (**Manual Deploy**).
6. Endi bot menyusida **"🖥 Web panel"** tugmasi paydo bo'ladi.

## 📁 Loyiha strukturasi

```
telegram-online-keeper/
├── main.py           # Ishga tushirish nuqtasi
├── admin_bot.py       # Boshqaruv boti (aiogram, FSM)
├── keeper.py           # Online-ushlab turish mantiqi (Telethon)
├── database.py         # SQLite bilan ishlash
├── config.py            # Sozlamalar
├── requirements.txt
├── Dockerfile
├── render.yaml
└── .env.example
```

## 🔒 Xavfsizlik bo'yicha maslahat

- `.env` va `data.db` fayllarini hech qachon GitHub'ga ochiq push qilmang (`.gitignore`da allaqachon bor).
- `ADMIN_IDS`ni albatta to'ldiring — aks holda bot hamma uchun ochiq bo'lib qoladi.
- Sessiya satrlari (`session_string`) akkauntga to'liq kirish huquqini beradi — ma'lumotlar bazasini ehtiyot qiling.
