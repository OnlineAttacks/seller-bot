import aiosqlite
import datetime
from config import DB_PATH, DEFAULT_QR, DEFAULT_PDF

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY,
            username TEXT,
            join_date TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS payments(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            utr TEXT UNIQUE,
            status TEXT,
            timestamp TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings(
            price INTEGER,
            upi_id TEXT,
            qr_path TEXT,
            pdf_path TEXT
        )
        """)

        cur = await db.execute("SELECT COUNT(*) FROM settings")
        if (await cur.fetchone())[0] == 0:
            await db.execute(
                "INSERT INTO settings VALUES (99, 'upi@id', ?, ?)",
                (DEFAULT_QR, DEFAULT_PDF)
            )

        await db.commit()


async def add_user(user_id, username):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users VALUES(?,?,?)",
            (user_id, username, datetime.datetime.now().isoformat())
        )
        await db.commit()


async def get_settings():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM settings")
        return await cur.fetchone()


async def update_setting(field, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE settings SET {field}=?", (value,))
        await db.commit()


async def add_payment(user_id, utr):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO payments(user_id,utr,status,timestamp) VALUES(?,?,?,?)",
            (user_id, utr, "pending", datetime.datetime.now().isoformat())
        )
        await db.commit()


async def update_payment(utr, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE payments SET status=? WHERE utr=?",
            (status, utr)
        )
        await db.commit()


async def payment_exists(utr):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM payments WHERE utr=?",
            (utr,)
        )
        return await cur.fetchone()


async def user_pending(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM payments WHERE user_id=? AND status='pending'",
            (user_id,)
        )
        return await cur.fetchone()


async def get_user_payments(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT status, timestamp FROM payments WHERE user_id=? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        return await cur.fetchone()


async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM users")
        return await cur.fetchall()


async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        stats = {}
        stats["total_users"] = (await (await db.execute("SELECT COUNT(*) FROM users")).fetchone())[0]
        stats["total_payments"] = (await (await db.execute("SELECT COUNT(*) FROM payments")).fetchone())[0]
        stats["approved"] = (await (await db.execute("SELECT COUNT(*) FROM payments WHERE status='approved'")).fetchone())[0]
        stats["rejected"] = (await (await db.execute("SELECT COUNT(*) FROM payments WHERE status='rejected'")).fetchone())[0]
        stats["pending"] = (await (await db.execute("SELECT COUNT(*) FROM payments WHERE status='pending'")).fetchone())[0]
        return stats