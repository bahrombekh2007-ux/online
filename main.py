import asyncio
import logging
import threading

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import database as db
import admin_bot
from keeper import OnlineKeeperManager
from web_app import run_web_app
from config import BOT_TOKEN

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("main")


async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan!")

    await db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    async def notify(user_id: int, text: str):
        try:
            await bot.send_message(user_id, text)
        except Exception as e:
            logger.warning(f"Adminga xabar yuborib bo'lmadi: {e}")

    keeper_manager = OnlineKeeperManager(notify_callback=notify)
    admin_bot.keeper_manager = keeper_manager
    dp.include_router(admin_bot.router)

    # Avval saqlangan faol akkauntlarni qayta ishga tushirish
    await keeper_manager.start_all_active()

    # Web panel (Flask) alohida oqimda ishga tushiriladi
    web_thread = threading.Thread(target=run_web_app, daemon=True)
    web_thread.start()
    logger.info("Web panel ishga tushdi ✅")

    logger.info("Bot ishga tushdi ✅")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
