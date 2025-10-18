from __future__ import annotations
from typing import Any, Optional
import aiosqlite, time
import logging
from contextlib import contextmanager
import os
from .db import get_db, DB_PATH


# ---------- helpers ----------

def _row_factory(cursor, row):
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

# ---------- contextmanagers ----------

@contextmanager
def use_dicts(db):
    prev = db.row_factory
    db.row_factory = _row_factory
    try:
        yield
    finally:
        db.row_factory = prev

@contextmanager
def use_tuples(db):
    prev = db.row_factory
    db.row_factory = None
    try:
        yield
    finally:
        db.row_factory = prev

# ---------- commands ----------

async def create_order(
    *,
    user_id: int,
    chat_id: int,
    drink: str,
    size: str,
    milk: str,
    created_at: Optional[int] = None,
    locale: Optional[str] = None,
) -> int:
    db: aiosqlite.Connection = get_db()
    ts = created_at or int(time.time())
    cur = await db.execute(
        """
        INSERT INTO orders(user_id, chat_id, drink, size, milk, created_at, locale)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, chat_id, drink, size, milk, ts, locale),
    )
    await db.commit()
    logging.getLogger("repo").info("[DB] insert",
        dict(user_id=user_id, chat_id=chat_id, drink=drink, size=size, milk=milk))
    return cur.lastrowid


# ---------- queries for History / Repeat ----------

async def get_orders_page(*, user_id: int, drink: str | None, offset: int, limit: int):
    db = get_db()
    sql = (
        "SELECT id, drink, size, milk, created_at "
        "FROM orders "
        "WHERE user_id = ? AND deleted_at IS NULL "
    )
    params = [user_id]
    if drink and drink != "all":
        sql += "AND drink = ? "
        params.append(drink)

    sql += "ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]

    logging.getLogger("repo").debug("get_orders_page uid=%s drink=%s offset=%s limit=%s",
                                    user_id, drink, offset, limit)

    with use_dicts(db):
        cur = await db.execute(sql, params)
        rows = await cur.fetchall()
        return rows

async def count_orders(*, user_id: int, drink: str | None = None) -> int:
    db = get_db()
    db.row_factory = None
    sql = "SELECT COUNT(*) FROM orders WHERE user_id=? AND deleted_at IS NULL"
    params: list[Any] = [user_id]
    if drink and drink != "all":
        sql += " AND drink=?"
        params.append(drink)
    cur = await db.execute(sql, params)
    (n,) = await cur.fetchone()
    return int(n)


async def get_order_by_id(*, user_id: int, order_id: int):
    db = get_db()
    db.row_factory = None
    cur = await db.execute(
        "SELECT id, drink, size, milk, created_at "
        "FROM orders WHERE user_id = ? AND id = ? AND deleted_at IS NULL",
        (user_id, order_id),
    )
    return await cur.fetchone()


# ---------- soft delete / undo ----------

async def soft_delete(*, user_id: int, order_id: int) -> bool:
    db = get_db()
    now = int(time.time())
    cur = await db.execute(
        "UPDATE orders SET deleted_at=? "
        "WHERE id=? AND user_id=? AND deleted_at IS NULL",
        (now, order_id, user_id),
    )
    await db.commit()
    return cur.rowcount > 0


async def undo_delete(*, user_id: int, order_id: int) -> bool:
    db = get_db()
    cur = await db.execute(
        "UPDATE orders SET deleted_at=NULL "
        "WHERE id=? AND user_id=? AND deleted_at IS NOT NULL",
        (order_id, user_id),
    )
    await db.commit()
    return cur.rowcount > 0


# ---------- extra (top / export) ----------

async def top_drinks_last_30d(*, user_id: int, limit: int = 5):
    db = get_db()
    since = int(time.time()) - 30 * 24 * 60 * 60
    sql = (
        "SELECT drink, COUNT(*) AS cnt "
        "FROM orders "
        "WHERE user_id = ? AND deleted_at IS NULL AND created_at >= ? "
        "GROUP BY drink "
        "ORDER BY cnt DESC "
        "LIMIT ?"
    )
    with use_tuples(db):
        cur = await db.execute(sql, (user_id, since, limit))
        return await cur.fetchall()

async def orders_for_period(
    *,
    user_id: int,
    since: int,
    until: int,
    drink: str | None = None
):
    db = get_db()
    sql = (
        "SELECT id, drink, size, milk, created_at "
        "FROM orders "
        "WHERE user_id = ? "
        "  AND deleted_at IS NULL "
        "  AND created_at >= ? "
        "  AND created_at <  ? "
    )
    params = [user_id, since, until]

    if drink and drink != "all":
        sql += "AND drink = ? "
        params.append(drink)

    sql += "ORDER BY created_at ASC, id ASC"
    with use_tuples(db):
        cur = await db.execute(sql, params)
        return await cur.fetchall()

async def drink_counts_between(*, user_id: int, since: int, until: int):
    db = get_db()
    db.row_factory = None
    sql = """
    SELECT drink, COUNT(*) AS cnt
    FROM orders
    WHERE user_id = ?
      AND deleted_at IS NULL
      AND created_at >= ?
      AND created_at <  ?
    GROUP BY drink
    ORDER BY cnt DESC
    """

    cur = await db.execute(sql, (user_id, since, until))
    rows = await cur.fetchall()
    return rows

async def count_total_orders() -> int:
    db = get_db()
    db.row_factory = None
    cur = await db.execute("SELECT COUNT(*) FROM orders WHERE deleted_at IS NULL")
    (n,) = await cur.fetchone()
    return int(n)

async def ping_db() -> bool:
    db = get_db()
    try:
        cur = await db.execute("SELECT 1")
        await cur.fetchone()
        return True
    except aiosqlite.Error:
        return False

async def count_deleted() -> int:
    db = get_db()
    cur = await db.execute("SELECT COUNT(*) FROM orders WHERE deleted_at IS NOT NULL")
    row = await cur.fetchone()
    return int(row[0] or 0)

async def last_order_ts_global() -> int | None:
    db = get_db()
    db.row_factory = None
    cur = await db.execute(
        "SELECT MAX(created_at) FROM orders WHERE deleted_at IS NULL"
    )
    (ts,) = await cur.fetchone()
    return int(ts) if ts is not None else None

async def last_order_ts_for(user_id: int) -> int | None:
    db = get_db()
    db.row_factory = None
    cur = await db.execute(
        "SELECT MAX(created_at) FROM orders WHERE user_id=? AND deleted_at IS NULL",
        (user_id,),
    )
    (ts,) = await cur.fetchone()
    return int(ts) if ts is not None else None

def db_size_bytes() -> int:
    try:
        return os.path.getsize(DB_PATH)
    except (FileNotFoundError, OSError):
        return 0

def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.0f} PB"

async def last_order_at(user_id: int | None = None) -> int | None:
    db = get_db()
    if user_id is None:
        sql = "SELECT MAX(created_at) FROM orders WHERE deleted_at IS NULL"
        args = ()
    else:
        sql = "SELECT MAX(created_at) FROM orders WHERE user_id = ? AND deleted_at IS NULL"
        args = (user_id,)
    cur = await db.execute(sql, args)
    row = await cur.fetchone()
    return int(row[0]) if row and row[0] is not None else None

async def user_order_number(user_id: int, created_at: int) -> int:
    db = get_db()
    db.row_factory = None
    cur = await db.execute(
        """
        SELECT COUNT(*)
        FROM orders
        WHERE user_id = ?
          AND deleted_at IS NULL
          AND created_at <= ?
        """,
        (user_id, created_at),
    )
    (cnt,) = await cur.fetchone()
    return int(cnt or 0)