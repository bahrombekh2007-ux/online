import aiosqlite
from datetime import datetime
from config import DB_PATH

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    phone TEXT NOT NULL,
    name TEXT,
    session_string TEXT NOT NULL,
    status TEXT DEFAULT 'faol',        -- faol, pauza, xatolik
    schedule_enabled INTEGER DEFAULT 0,
    online_start_hour INTEGER DEFAULT 8,
    online_end_hour INTEGER DEFAULT 24,
    auto_read INTEGER DEFAULT 0,
    last_online TEXT,
    added_at TEXT,
    UNIQUE(phone)
);
"""


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_TABLE_SQL)
        await db.commit()


async def add_account(owner_id: int, phone: str, name: str, session_string: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """INSERT INTO accounts (owner_id, phone, name, session_string, added_at, last_online)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (owner_id, phone, name, session_string, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()),
        )
        await db.commit()
        return cursor.lastrowid


async def get_accounts(owner_id: int | None = None):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if owner_id is not None:
            cursor = await db.execute("SELECT * FROM accounts WHERE owner_id = ? ORDER BY id", (owner_id,))
        else:
            cursor = await db.execute("SELECT * FROM accounts ORDER BY id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_account(account_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def set_status(account_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE accounts SET status = ? WHERE id = ?", (status, account_id))
        await db.commit()


async def update_last_online(account_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE accounts SET last_online = ? WHERE id = ?",
            (datetime.utcnow().isoformat(), account_id),
        )
        await db.commit()


async def set_schedule(account_id: int, enabled: bool, start_hour: int = 8, end_hour: int = 24):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE accounts SET schedule_enabled = ?, online_start_hour = ?, online_end_hour = ? WHERE id = ?",
            (int(enabled), start_hour, end_hour, account_id),
        )
        await db.commit()


async def set_auto_read(account_id: int, enabled: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE accounts SET auto_read = ? WHERE id = ?", (int(enabled), account_id))
        await db.commit()


async def delete_account(account_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        await db.commit()
