import asyncio
import logging
import random
from datetime import datetime

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateStatusRequest
from telethon.errors import AuthKeyUnregisteredError, UserDeactivatedBanError, SessionRevokedError

import database as db
from config import API_ID, API_HASH, BASE_INTERVAL, JITTER

logger = logging.getLogger("keeper")


class OnlineKeeperManager:
    """Har bir akkaunt uchun alohida async vazifa (task) boshqaradi."""

    def __init__(self, notify_callback=None):
        self.clients: dict[int, TelegramClient] = {}
        self.tasks: dict[int, asyncio.Task] = {}
        self.notify_callback = notify_callback  # xatolik bo'lsa adminga xabar yuborish uchun

    def _is_within_schedule(self, account: dict) -> bool:
        if not account["schedule_enabled"]:
            return True
        hour = datetime.now().hour
        start, end = account["online_start_hour"], account["online_end_hour"]
        if start <= end:
            return start <= hour < end
        # masalan 22:00 dan 06:00 gacha kabi kechani kesib o'tuvchi oraliq
        return hour >= start or hour < end

    async def _run_account_loop(self, account_id: int):
        account = await db.get_account(account_id)
        if not account:
            return

        client = TelegramClient(StringSession(account["session_string"]), API_ID, API_HASH)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                await db.set_status(account_id, "xatolik")
                await self._notify(account, "Sessiya haqiqiy emas. Akkauntni qayta qo'shing.")
                return

            self.clients[account_id] = client

            # Auto-read: kelgan xabarlarni avtomatik "ko'rildi" qilib belgilash
            if account["auto_read"]:
                @client.on(events.NewMessage(incoming=True))
                async def _mark_read(event):
                    try:
                        await client.send_read_acknowledge(event.chat_id)
                    except Exception:
                        pass

            logger.info(f"[{account['phone']}] online-keeper ishga tushdi")

            while True:
                fresh = await db.get_account(account_id)
                if not fresh or fresh["status"] != "faol":
                    break

                if self._is_within_schedule(fresh):
                    try:
                        await client(UpdateStatusRequest(offline=False))
                        await db.update_last_online(account_id)
                    except (AuthKeyUnregisteredError, UserDeactivatedBanError, SessionRevokedError):
                        await db.set_status(account_id, "xatolik")
                        await self._notify(fresh, "Akkaunt bloklangan yoki sessiya bekor qilingan.")
                        break
                    except Exception as e:
                        logger.warning(f"[{account['phone']}] xatolik: {e}")

                # Tabiiy ko'rinishi uchun random interval
                wait_time = BASE_INTERVAL + random.randint(-JITTER, JITTER)
                await asyncio.sleep(max(10, wait_time))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{account.get('phone')}] kutilmagan xatolik: {e}")
            await db.set_status(account_id, "xatolik")
            await self._notify(account, f"Kutilmagan xatolik: {e}")
        finally:
            if client.is_connected():
                await client.disconnect()
            self.clients.pop(account_id, None)

    async def _notify(self, account: dict, text: str):
        if self.notify_callback:
            try:
                await self.notify_callback(account["owner_id"], f"⚠️ {account['phone']} ({account.get('name') or ''}): {text}")
            except Exception:
                pass

    def start_account(self, account_id: int):
        if account_id in self.tasks and not self.tasks[account_id].done():
            return  # allaqachon ishlayapti
        task = asyncio.create_task(self._run_account_loop(account_id))
        self.tasks[account_id] = task

    async def stop_account(self, account_id: int):
        task = self.tasks.pop(account_id, None)
        if task and not task.done():
            task.cancel()
        client = self.clients.pop(account_id, None)
        if client and client.is_connected():
            await client.disconnect()

    async def restart_account(self, account_id: int):
        await self.stop_account(account_id)
        self.start_account(account_id)

    async def start_all_active(self):
        accounts = await db.get_accounts()
        for acc in accounts:
            if acc["status"] == "faol":
                self.start_account(acc["id"])
