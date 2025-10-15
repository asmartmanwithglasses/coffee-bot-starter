from pathlib import Path
import aiosqlite
import logging
import os

db_logger = logging.getLogger("db")

DB_FILE = os.getenv("DB_FILE")
DB_PATH = Path(DB_FILE) if DB_FILE else (Path(__file__).parent / "data.sqlite3")

CREATE_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS orders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    chat_id    INTEGER NOT NULL,
    drink      TEXT    NOT NULL,
    size       TEXT    NOT NULL,
    milk       TEXT    NOT NULL,
    created_at INTEGER NOT NULL,
    deleted_at INTEGER,
    locale     TEXT
);

CREATE INDEX IF NOT EXISTS idx_orders_user_created ON orders(user_id, created_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_orders_drink ON orders(drink);
CREATE INDEX IF NOT EXISTS idx_orders_deleted ON orders(deleted_at);
"""

_DB: aiosqlite.Connection | None = None

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.executescript(CREATE_SQL)
        await conn.commit()
        db_logger.info("DB PATH: %s", DB_PATH.resolve())

async def open_db() -> aiosqlite.Connection:
    global _DB
    if _DB is None:
        _DB = await aiosqlite.connect(DB_PATH)
        await _DB.execute("PRAGMA foreign_keys=ON;")
    return _DB

def get_db() -> aiosqlite.Connection:
    if _DB is None:
        raise RuntimeError("DB is not opened. Call open_db() first.")
    return _DB

async def close_db() -> None:
    global _DB
    if _DB is not None:
        await _DB.close()
        _DB = None